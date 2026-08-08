"""Corrected analysis: water rights prices, Mediterranean Chile.

Fixes four defects in the original pipeline.

1. The weight matrix was built from the full monthly panel, so every basin's
   coordinates repeated once per month and all four "nearest neighbours" sat at
   distance zero. Every link connected a basin to itself in another month. W is
   rebuilt at basin level and blocked across periods.
2. The SPI was produced by fitting a gamma distribution to the *year* column,
   with dry months dropped and then zero-filled. It is recomputed from monthly
   precipitation with Thom's mixed-distribution correction for zeros.
3. The model was estimated as a spatial autoregression but reported as a Durbin
   model. Both are estimated and compared by likelihood ratio.
4. Impacts were computed by slicing the diagonal of the multiplier matrix. They
   are recomputed by the LeSage and Pace formulas, per variable.

Run:  python wr_spatial_corrected.py
"""
import warnings

import libpysal
import numpy as np
import pandas as pd
from libpysal.weights import KNN
from scipy.sparse import csr_matrix, identity, kron
from scipy.stats import chi2, gamma, norm
from spreg import ML_Lag

warnings.filterwarnings("ignore")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIGURES = ROOT / "figures"


PANEL = str(DATA / "datos_mensual_mediterraneo_revb.csv")
PRECIP = str(DATA / "pp_historica_mensual.csv")
MED = [43, 44, 45, 47, 48, 51, 52, 53, 54, 55, 57, 60, 71, 81, 83, 101, 103]
COVARS = ["caudal_transado", "estival", "dummy_mina", "n_transacciones",
          "caudal_dummy_escasez", "log_puf_mean_lag", "dummy_dec_esc_lag"]


def spi(series, scale):
    """SPI after McKee et al. (1993), with Thom's correction for zero months.

    Precipitation is accumulated over `scale` months. A two-parameter gamma is
    fitted to the strictly positive accumulations of each calendar month
    separately, and H(x) = q + (1 - q) G(x) is mapped onto the standard normal,
    where q is the empirical probability of zero. Fitting per calendar month is
    what makes the index comparable across a strongly seasonal climate.
    """
    acc = series.rolling(scale).sum()
    out = pd.Series(np.nan, index=acc.index)
    for m in range(1, 13):
        idx = acc.index[acc.index.get_level_values("month") == m]
        vals = acc.loc[idx].dropna()
        pos = vals[vals > 0]
        if len(vals) < 10 or len(pos) < 10:
            continue
        q = 1.0 - len(pos) / len(vals)
        shape, loc, scl = gamma.fit(pos, floc=0)
        cdf = q + (1 - q) * gamma.cdf(vals, shape, loc=loc, scale=scl)
        out.loc[vals.index] = norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6))
    return out


def build_spi(path, scales=(3, 6, 12)):
    p = pd.read_csv(path, index_col=0)
    p = p[p.cuenca.isin(MED)].sort_values(["cuenca", "year", "month"])
    frames = []
    for c, g in p.groupby("cuenca"):
        g = g.set_index(["year", "month"]).sort_index()
        f = pd.DataFrame(index=g.index)
        for k in scales:
            f[f"spi{k}"] = spi(g.pp_mes, k)
        f["cuenca"] = c
        frames.append(f.reset_index())
    return pd.concat(frames, ignore_index=True)


def load_panel():
    sp = build_spi(PRECIP)
    d = (pd.read_csv(PANEL, sep=";", decimal=",")
           .sort_values(["cuenca", "year", "month"])
           .merge(sp, on=["cuenca", "year", "month"], how="left"))
    d["log_puf_mean_lag"] = d.groupby("cuenca").log_puf_mean.shift(1)
    d["dummy_dec_esc_lag"] = d.groupby("cuenca").dummy_escasez.shift(1)
    d["caudal_dummy_escasez"] = d.caudal_transado * d.dummy_escasez
    d["t"] = (d.year - 2005) * 12 + d.month
    return d


def stack(d, cols, k=4):
    """Balance the panel, build a basin-level W, and stack period by period."""
    nb = d.cuenca.nunique()
    keep = d.groupby("t").cuenca.nunique().pipe(lambda s: s[s == nb].index)
    d = d[d.t.isin(keep)]
    coords = d.groupby("cuenca")[["lon", "lat"]].first().sort_index()
    basins = coords.index.tolist()
    w = KNN.from_array(coords.values, k=k)
    w.transform = "r"
    Wd = w.full()[0]
    per = sorted(d.t.unique())
    di = d.set_index(["t", "cuenca"]).sort_index()
    Y, X, WX = [], [], []
    for tt in per:
        s = di.loc[tt].reindex(basins)
        Y.append(s.log_puf_mean.values)
        Xi = s[cols].values
        X.append(Xi)
        WX.append(Wd @ Xi)
    wp = libpysal.weights.WSP(
        kron(identity(len(per)), csr_matrix(Wd), format="csr")).to_W()
    return (np.concatenate(Y).reshape(-1, 1), np.vstack(X), np.vstack(WX),
            wp, Wd, basins)


def table(model, title):
    b, se = np.ravel(model.betas), np.sqrt(np.diagonal(model.vm))
    print(f"\n{title}")
    for i, n in enumerate(model.name_x):
        z = b[i] / se[i]
        print(f"  {n:24s}{b[i]:11.5f}{z:8.2f}{' *' if abs(z) > 1.96 else ''}")


def impacts(sdm, Wd, cols, basins):
    """Direct, indirect and total effects (LeSage and Pace, 2009, ch. 2).

    S_k(W) = (I - rho W)^-1 (beta_k I + theta_k W). The direct effect is the
    mean diagonal of S_k, the total effect the mean row sum, and the indirect
    effect the difference. In a pure SAR the indirect/direct ratio collapses to
    rho/(1-rho) for every variable; if it varies here, the Durbin terms matter.
    """
    b = np.ravel(sdm.betas)
    rho = float(np.ravel(sdm.rho)[0])
    A = np.linalg.inv(np.eye(len(basins)) - rho * Wd)
    beta = {n: b[i] for i, n in enumerate(sdm.name_x) if not n.startswith("W_")}
    theta = {n[2:]: b[i] for i, n in enumerate(sdm.name_x)
             if n.startswith("W_") and n != "W_dep_var"}
    print(f"\nImpacts (rho = {rho:.4f})")
    print(f"  {'variable':22s}{'direct':>10s}{'indirect':>11s}"
          f"{'total':>10s}{'ind/dir':>10s}")
    for c in cols:
        S = A @ (beta[c] * np.eye(len(basins)) + theta.get(c, 0.0) * Wd)
        dr = float(np.mean(np.diag(S)))
        tot = float(np.mean(S.sum(axis=1)))
        print(f"  {c:22s}{dr:10.4f}{tot - dr:11.4f}{tot:10.4f}{(tot - dr) / dr:10.3f}")


def run(d, cols, label, show=True):
    Y, X, WX, wp, Wd, basins = stack(d.dropna(subset=cols), cols)
    # A variable constant across basins within a period equals its own spatial
    # lag under a row-standardised W, so it cannot enter the Durbin block.
    dur = [i for i, c in enumerate(cols) if not np.allclose(WX[:, i], X[:, i])]
    sar = ML_Lag(Y, X, w=wp, name_x=cols)
    sdm = ML_Lag(Y, np.hstack([X, WX[:, dur]]), w=wp,
                 name_x=cols + ["W_" + cols[i] for i in dur])
    lr = 2 * (float(sdm.logll) - float(sar.logll))
    p = 1 - chi2.cdf(lr, len(dur))
    print(f"\n{'=' * 66}\n{label}   N={sar.n}, {len(basins)} basins")
    print(f"LR test SDM vs SAR: {lr:.2f} (df={len(dur)}), p={p:.4f}"
          f"  -> {'Durbin terms retained' if p < 0.05 else 'reduces to SAR'}")
    if show:
        table(sar, "SAR")
        table(sdm, "SDM")
        impacts(sdm, Wd, cols, basins)
    return sar, sdm


def main():
    d = load_panel()
    print("SPI from the 1979-2020 record (42 years):")
    print(d[["spi3", "spi6", "spi12"]].describe().T[
        ["count", "mean", "std", "min", "max"]].round(3).to_string())
    print("\nBasins 43 and 55 have no precipitation record and drop out.")

    # Timescale comparison: which accumulation window does the market track?
    for k in (3, 6, 12):
        run(d, COVARS + [f"spi{k}"], f"SPI-{k}", show=(k == 12))


if __name__ == "__main__":
    main()
