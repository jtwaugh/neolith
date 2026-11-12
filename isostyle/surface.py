"""Kernel presence and evidence surfaces on the grid, with a bootstrap.

  E[c, j] = sum_i w[i, j] K(d[i, c])
  f[c, j] = (sum_i w[i, j] K y[i] + alpha f0[j]) / (E[c, j] + alpha)
  K(d)    = exp(-d^2 / 2 sigma^2) for d <= cutoff * sigma, else 0

Distances are great-circle. Units at one point are pooled first, so the
kernel matrix is cells x places.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree

from .observe import R_EARTH, chord, unit_xyz


def kernel_rows(tree_places, xyz_cells, sigma, cutoff, chunk=1500):
    """Yield (row slice, sparse K) for chunks of cells."""
    n = tree_places.n
    for s in range(0, len(xyz_cells), chunk):
        part = xyz_cells[s:s + chunk]
        m = cKDTree(part).sparse_distance_matrix(tree_places, chord(cutoff * sigma), output_type="coo_matrix")
        d = 2 * R_EARTH * np.arcsin(np.clip(m.data / 2, 0, 1))
        yield slice(s, s + len(part)), csr_matrix((np.exp(-d ** 2 / (2 * sigma ** 2)), (m.row, m.col)),
                                                  shape=(len(part), n)), d, m


def pool(lon, lat):
    """Place index per unit and the places' coordinates."""
    key = np.round(np.column_stack([lon, lat]), 5)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.ravel(), uniq


def cross_validate(lon, lat, W, y, sigmas, cutoff, alpha):
    """Leave-one-place-out log loss of predicting presence, per sigma."""
    inv, places = pool(lon, lat)
    P, S = len(places), W.shape[1]
    D = np.zeros((P, S))
    N = np.zeros((P, S))
    np.add.at(D, inv, W)
    np.add.at(N, inv, W * y[:, None])
    f0 = N.sum(axis=0) / np.maximum(D.sum(axis=0), 1e-12)
    xyz = unit_xyz(places[:, 0], places[:, 1])
    tree = cKDTree(xyz)
    out = {}
    for sg in sigmas:
        loss = 0.0
        covered = 0.0
        for rows, K, d, m in kernel_rows(tree, xyz, sg, cutoff):
            K = K.tolil()
            K.setdiag(0, k=rows.start)       # leave the place itself out
            K = K.tocsr()
            num, den = K @ N, K @ D
            p = np.clip((num + alpha * f0) / (den + alpha), 1e-3, 1 - 1e-3)
            loss += -(N[rows] * np.log(p) + (D[rows] - N[rows]) * np.log(1 - p)).sum()
            covered += (D[rows] * (den > 0)).sum()
        out[sg] = {"log_loss": float(loss / D.sum()), "share_with_neighbours": float(covered / D.sum())}
    return out


def surfaces(grid_lon, grid_lat, lon, lat, W, y, label, W_all, lon_all, lat_all,
             sigma, cutoff, alpha, e_min, n_boot, seed, threshold=0.5):
    """Main and bootstrap surfaces for one material.

    lon, lat, W, y, label: the units with known y (label: True if label-derived).
    W_all, lon_all, lat_all: every unit, for the recorded-share layer.
    """
    rng = np.random.default_rng(seed)
    S, n = W.shape[1], len(y)
    inv, places = pool(lon, lat)
    P = len(places)

    def pooled(weights):
        a = np.zeros((P, weights.shape[1]), dtype=np.float32)
        np.add.at(a, inv, weights)
        return a

    D, N, L = pooled(W), pooled(W * y[:, None]), pooled(W * label[:, None])
    Rec = pooled(W * (y * ~label)[:, None])
    f0 = N.sum(axis=0) / np.maximum(D.sum(axis=0), 1e-12)

    # Bootstrap replicates: resample units, draw one slice from each p_i(t).
    cum = np.cumsum(W, axis=1)
    Db = np.zeros((P, S * n_boot), dtype=np.float32)
    Nb = np.zeros((P, S * n_boot), dtype=np.float32)
    f0b = np.zeros((n_boot, S))
    for b in range(n_boot):
        pick = rng.integers(0, n, n)
        u = rng.random(n)
        j = (u[:, None] > cum[pick]).sum(axis=1)       # S means "outside every slice"
        ok = j < S
        np.add.at(Db, (inv[pick[ok]], b * S + j[ok]), 1.0)
        np.add.at(Nb, (inv[pick[ok]], b * S + j[ok]), y[pick[ok]])
        d0 = np.bincount(j[ok], minlength=S)
        f0b[b] = np.bincount(j[ok], weights=y[pick[ok]], minlength=S) / np.maximum(d0, 1)

    inv_a, places_a = pool(lon_all, lat_all)
    Da = np.zeros((len(places_a), S), dtype=np.float32)
    np.add.at(Da, inv_a, W_all)

    C = len(grid_lon)
    xyz_c = unit_xyz(grid_lon, grid_lat)
    E, num, lab, Eall, rec = (np.zeros((C, S)) for _ in range(5))
    above, valid = np.zeros((C, S)), np.zeros((C, S))
    tree = cKDTree(unit_xyz(places[:, 0], places[:, 1]))
    for rows, K, _, _ in kernel_rows(tree, xyz_c, sigma, cutoff):
        E[rows], num[rows], lab[rows], rec[rows] = K @ D, K @ N, K @ L, K @ Rec
        eb = (K @ Db).reshape(-1, n_boot, S)
        nb = (K @ Nb).reshape(-1, n_boot, S)
        fb = (nb + alpha * f0b[None]) / (eb + alpha)
        v = eb >= e_min
        valid[rows] = v.mean(axis=1)
        above[rows] = (v & (fb >= threshold)).sum(axis=1) / np.maximum(v.sum(axis=1), 1)
    tree_a = cKDTree(unit_xyz(places_a[:, 0], places_a[:, 1]))
    for rows, K, _, _ in kernel_rows(tree_a, xyz_c, sigma, cutoff):
        Eall[rows] = K @ Da
    f = (num + alpha * f0) / (E + alpha)
    return {"E": E, "f": f, "label_share": lab / np.maximum(E, 1e-12), "E_all": Eall,
            "recorded_share": rec / np.maximum(Eall, 1e-12),
            "boot_above": above, "boot_valid": valid, "f0": f0}
