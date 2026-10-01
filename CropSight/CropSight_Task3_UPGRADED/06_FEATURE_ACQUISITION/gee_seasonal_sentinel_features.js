// CropSight Task 3 - seasonal Sentinel-2 NDVI + Sentinel-1 VV/VH features
// Run in Google Earth Engine Code Editor after confirming the input asset and export folder.
var POINTS = ee.FeatureCollection('projects/gen-lang-client-0918025315/assets/ground_truth_gee_export');
var YEAR = 2024;
var BUFFER_M = 30; // small field-edge/noise buffer; keep fixed across all experiments
var EXPORT_FOLDER = 'CropSight_Task3';

var seasons = [
  {name:'S1', start: YEAR+'-01-01', end: YEAR+'-03-31'},
  {name:'S2', start: YEAR+'-04-01', end: YEAR+'-06-30'},
  {name:'S3', start: YEAR+'-07-01', end: YEAR+'-09-30'},
  {name:'S4', start: YEAR+'-10-01', end: YEAR+'-12-31'}
];

function maskS2(image) {
  var qa = image.select('QA60');
  var cloud = qa.bitwiseAnd(1 << 10).eq(0);
  var cirrus = qa.bitwiseAnd(1 << 11).eq(0);
  return image.updateMask(cloud.and(cirrus)).divide(10000);
}

function s2Season(season) {
  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(POINTS)
    .filterDate(season.start, season.end)
    .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2);
  var median = col.median();
  var ndvi = median.normalizedDifference(['B8','B4']).rename(season.name+'_NDVI');
  return ndvi;
}

function s1Season(season) {
  var col = ee.ImageCollection('COPERNICUS/S1_GRD')
    .filterBounds(POINTS)
    .filterDate(season.start, season.end)
    .filter(ee.Filter.eq('instrumentMode','IW'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation','VV'))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation','VH'))
    .select(['VV','VH']);
  return col.median().rename([season.name+'_VV', season.name+'_VH']);
}

var seasonal = ee.Image([]);
seasons.forEach(function(s) {
  seasonal = seasonal.addBands(s2Season(s)).addBands(s1Season(s));
});
seasonal = seasonal.select(seasonal.bandNames());

var buffered = POINTS.map(function(f) { return f.buffer(BUFFER_M); });
var sampled = seasonal.reduceRegions({
  collection: buffered,
  reducer: ee.Reducer.mean(),
  scale: 10,
  tileScale: 4
});

// Restore key point properties for joining with the existing embedding table.
var output = sampled.map(function(f) {
  return f.set({
    observation_id: f.get('observation_id'),
    buffer_m: BUFFER_M,
    feature_year: YEAR
  });
});

print('Feature bands', seasonal.bandNames());
print('Sample output', output.limit(5));
Map.centerObject(POINTS, 11);
Map.addLayer(seasonal.select('S2_NDVI'), {min:0, max:0.9, palette:['brown','yellow','green']}, 'S1 NDVI');

Export.table.toDrive({
  collection: output,
  description: 'CropSight_Seasonal_S2_S1_2024_Buffer30m',
  folder: EXPORT_FOLDER,
  fileNamePrefix: 'cropsight_seasonal_s2_s1_2024_buffer30m',
  fileFormat: 'CSV'
});
