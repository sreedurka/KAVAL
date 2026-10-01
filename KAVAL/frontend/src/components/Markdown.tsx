import type { ReactNode } from 'react'

/**
 * Minimal Markdown for analyst answers. LLMs answer in Markdown; shown raw, a reader
 * sees literal **asterisks**. This renders the subset they use — paragraphs, ### headings,
 * bullet and numbered lists, pipe tables, **bold**, *italic*, `code` — by building React
 * elements. It never injects HTML, so a model's output cannot inject markup either.
 */

/** Models sometimes answer in LaTeX despite being told not to. Degrade inline math to
 *  readable text rather than showing `$\\text{…}$` source: \\text{x} → x, drop $. */
function unlatex(text: string): string {
  return text.replace(/\$([^$\n]+)\$/g, (_m, body: string) =>
    body
      .replace(/\\(?:text|mathrm|mathit|operatorname)\{([^}]*)\}/g, '$1')
      .replace(/\\times/g, '×').replace(/\\cdot/g, '·').replace(/\\le(q)?/g, '≤')
      .replace(/\\ge(q)?/g, '≥').replace(/\\approx/g, '≈').replace(/\\%/g, '%')
      .replace(/\\[a-zA-Z]+/g, '').replace(/[{}]/g, '').trim())
}

function inline(raw: string, key: string): ReactNode[] {
  const text = unlatex(raw)
  const out: ReactNode[] = []
  // API paths the analyst hands back (export_layer URLs, summaries) become links
  // through the UI's /api proxy, so "download it" is one click.
  const re = /(\*\*[^*]+\*\*|`\/(?:export|summary|audit|parcels)[^`]*`|`[^`]+`|\*[^*\s][^*]*\*|(?<![\w/])\/(?:export|summary)\?[^\s)`'",]+)/g
  let last = 0
  let m: RegExpExecArray | null
  let i = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const t = m[0]
    const k = `${key}-${i++}`
    const path = t.replace(/^`|`$/g, '')
    if (/^\/(export|summary|audit|parcels)/.test(path))
      out.push(
        <a key={k} href={`/api${path}`} target="_blank" rel="noreferrer">
          <code>{path}</code>
        </a>,
      )
    else if (t.startsWith('**')) out.push(<strong key={k}>{t.slice(2, -2)}</strong>)
    else if (t.startsWith('`')) out.push(<code key={k}>{t.slice(1, -1)}</code>)
    else out.push(<em key={k}>{t.slice(1, -1)}</em>)
    last = m.index + t.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

const cells = (row: string) =>
  row.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())

export function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, '').split('\n')
  const blocks: ReactNode[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const k = `b${i}`
    if (!line.trim()) {
      i++
      continue
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(line)
    if (h) {
      blocks.push(<div key={k} className="md-h">{inline(h[2], k)}</div>)
      i++
      continue
    }
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const head = cells(line)
      const rows: string[][] = []
      i += 2
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(cells(lines[i++]))
      blocks.push(
        <table key={k} className="data md-table">
          <thead>
            <tr>{head.map((c, j) => <th key={j}>{inline(c, `${k}h${j}`)}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c, `${k}r${ri}c${j}`)}</td>)}</tr>
            ))}
          </tbody>
        </table>,
      )
      continue
    }
    const bullet = /^\s*([-*•]|\d+[.)])\s+/
    if (bullet.test(line)) {
      const ordered = /^\s*\d/.test(line)
      const items: ReactNode[] = []
      while (i < lines.length && bullet.test(lines[i])) {
        items.push(<li key={i}>{inline(lines[i].replace(bullet, ''), `${k}l${i}`)}</li>)
        i++
      }
      blocks.push(ordered ? <ol key={k}>{items}</ol> : <ul key={k}>{items}</ul>)
      continue
    }
    const para: string[] = []
    while (i < lines.length && lines[i].trim() && !bullet.test(lines[i]) && !/^#{1,6}\s/.test(lines[i]) && !/^\s*\|/.test(lines[i]))
      para.push(lines[i++])
    blocks.push(<p key={k}>{inline(para.join(' '), k)}</p>)
  }
  return <div className="md">{blocks}</div>
}
