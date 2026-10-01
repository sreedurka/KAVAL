"""
KAVAL — attention-based Multiple-Instance Learning over survey capture events.

A survey photograph supplies one crop label to up to 43 parcels. Those are not 43
independent labelled examples; they are a BAG with one bag-level label, and some
members are passengers — land the surveyor never actually looked at.

Gated-attention MIL (Ilse, Tolstikhin & Welling, 2018) is the natural fit. It
learns a weight per bag member, pools them into a bag representation, and is
trained against the bag label. Two things come out:

  1. a classifier that stops treating copied labels as independent evidence
  2. an attention weight per parcel — how much this parcel actually supports the
     crop the surveyor declared. That weight is the `bag_support` audit signal,
     and it is arguably worth more than any accuracy gain.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import SEED


class GatedAttentionMIL(nn.Module):
    """
    Instance encoder -> gated attention pooling -> bag classifier.

    The same classifier head is applied to pooled bags during training and to
    individual instances at inference, so the model yields per-parcel predictions
    as well as bag-level ones. That matters because KAVAL's deliverable is
    per-parcel, even though supervision is per-bag.
    """

    def __init__(self, n_features, n_classes, hidden=128, attn_dim=64, dropout=0.25):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(n_features, hidden), nn.LayerNorm(hidden), nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.LayerNorm(hidden), nn.ReLU(),
        )
        # Gated attention: a tanh branch for magnitude, a sigmoid gate for
        # selectivity. The gate is what lets the model suppress a passenger
        # parcel rather than merely down-weighting everything uniformly.
        self.attn_V = nn.Linear(hidden, attn_dim)
        self.attn_U = nn.Linear(hidden, attn_dim)
        self.attn_w = nn.Linear(attn_dim, 1)
        self.classifier = nn.Linear(hidden, n_classes)

    def instance_logits(self, x):
        return self.classifier(self.encoder(x))

    def forward(self, x, bag_ptr):
        """
        x       : (N_instances, n_features) for a batch of concatenated bags
        bag_ptr : (N_bags + 1,) offsets into x, CSR-style

        Returns bag logits and per-instance attention weights (each bag's weights
        sum to 1, so they are comparable across bags of different sizes).
        """
        h = self.encoder(x)
        a = self.attn_w(torch.tanh(self.attn_V(h)) * torch.sigmoid(self.attn_U(h)))

        bag_logits, attn = [], torch.empty_like(a)
        for i in range(len(bag_ptr) - 1):
            s, e = bag_ptr[i], bag_ptr[i + 1]
            w = torch.softmax(a[s:e], dim=0)
            attn[s:e] = w
            bag_logits.append(self.classifier((w * h[s:e]).sum(0)))
        return torch.stack(bag_logits), attn.squeeze(-1)


def make_bags(bag_ids, order=None):
    """Group row indices by bag id, returning (concatenated index, CSR offsets)."""
    if order is None:
        order = np.argsort(bag_ids, kind="stable")
    sorted_ids = np.asarray(bag_ids)[order]
    boundaries = np.flatnonzero(np.r_[True, sorted_ids[1:] != sorted_ids[:-1], True])
    return order, boundaries, sorted_ids[boundaries[:-1]]


def train_mil(X, y_idx, bag_ids, n_classes, *, epochs=60, lr=1e-3,
              batch_bags=64, device="cpu", seed=SEED, verbose=False,
              class_weight=None):
    """
    Train on bags. One label per bag, taken from its first member — bags are
    single-label by construction and Phase 1 asserts it.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    order, ptr, uniq = make_bags(bag_ids)
    Xs = torch.tensor(X[order], dtype=torch.float32, device=device)
    bag_y = torch.tensor(
        [y_idx[order[ptr[i]]] for i in range(len(ptr) - 1)],
        dtype=torch.long, device=device)

    model = GatedAttentionMIL(X.shape[1], n_classes).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    w = (torch.tensor(class_weight, dtype=torch.float32, device=device)
         if class_weight is not None else None)

    n_bags = len(ptr) - 1
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n_bags)
        total = 0.0
        for k in range(0, n_bags, batch_bags):
            chunk = perm[k:k + batch_bags]
            idx, offs, cur = [], [0], 0
            for b in chunk:
                s, e = ptr[b], ptr[b + 1]
                idx.extend(range(s, e))
                cur += e - s
                offs.append(cur)
            logits, _ = model(Xs[idx], offs)
            loss = F.cross_entropy(logits, bag_y[chunk], weight=w)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            total += loss.item() * len(chunk)
        sched.step()
        if verbose and (ep + 1) % 20 == 0:
            print(f"    epoch {ep+1:3d}  loss {total/n_bags:.4f}")
    return model


@torch.no_grad()
def predict(model, X, bag_ids, device="cpu"):
    """
    Per-instance class probabilities and per-bag-normalised attention weights.

    Instance probabilities come from applying the shared classifier head to each
    instance, which is what makes a bag-trained model usable for the per-parcel
    prediction KAVAL actually ships.
    """
    model.eval()
    order, ptr, _ = make_bags(bag_ids)
    Xs = torch.tensor(X[order], dtype=torch.float32, device=device)

    inst_logits = model.instance_logits(Xs)
    inst_proba = torch.softmax(inst_logits, dim=1).cpu().numpy()

    h = model.encoder(Xs)
    a = model.attn_w(torch.tanh(model.attn_V(h)) * torch.sigmoid(model.attn_U(h)))
    attn = np.empty(len(Xs), dtype=np.float32)
    bag_proba, bag_index = [], []
    for i in range(len(ptr) - 1):
        s, e = ptr[i], ptr[i + 1]
        w = torch.softmax(a[s:e], dim=0)
        attn[s:e] = w.squeeze(-1).cpu().numpy()
        bag_proba.append(torch.softmax(model.classifier((w * h[s:e]).sum(0)), 0).cpu().numpy())
        bag_index.append(i)

    # Unsort back to the caller's row order.
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    return inst_proba[inv], attn[inv], np.array(bag_proba), ptr, order


def bag_support(attn, bag_ids):
    """
    Rescale attention so it is comparable across bag sizes.

    Raw attention sums to 1 per bag, so a member of a 43-parcel bag is mechanically
    ~43x smaller than a singleton's. We divide by the uniform weight 1/n, giving
    1.0 for "exactly average support", <1 for a passenger, >1 for a parcel carrying
    the bag. Without this the signal would just be measuring bag size.
    """
    attn = np.asarray(attn, dtype=float)
    df_sizes = {}
    for b in bag_ids:
        df_sizes[b] = df_sizes.get(b, 0) + 1
    n = np.array([df_sizes[b] for b in bag_ids], dtype=float)
    return attn * n
