"""Scenario projection of water rights prices on SPI-12.

Replaces the original projection, which had three defects: the model was fitted
on maximum *monthly* precipitation and fed *annual* precipitation, the projected
drought index was a plain z-score while the fitted one came from a gamma
transform, and the prediction omitted the spatial multiplier entirely.

Here the estimated index and the projected index are the same quantity, produced
by the same transform against the same 1979-2020 climatology, and prices are
solved as the long-run equilibrium of the dynamic spatial Durbin model.

Two corrections matter for interpretation.

Delta change. Both scenarios sit about 32% below the observed climatology
already in 2030, and they agree with each other there, which is GCM dry bias
rather than a climate signal. Scoring raw model output against an observed
gamma would read that bias as permanent drought. Projections are therefore
expressed as fractional change relative to the 2030 reference and applied to
the observed basin climatology.

Uncertainty. The projection rests on estimated coefficients, so the full
parameter covariance is propagated by Monte Carlo rather than treating point
estimates as known.

Run:  python wr_projection.py
"""
import warnings

import numpy as np
import pandas as pd
from scipy.stats import gamma, norm
from spreg import ML_Lag

from wr_spatial_corrected import COVARS, PRECIP, load_panel, stack

warnings.filterwarnings("ignore")

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIGURES = ROOT / "figures"


FUTURE = str(DATA / "datos_mensual_mediterraneo_clima_futuro.csv")
REF_YEAR = 2030
NDRAW = 4000
RNG = np.random.default_rng(20260808)


def annual_gamma(path):
    """Fit a gamma to each basin's annual precipitation totals, 1979-2020.

    This is the SPI-12 reference distribution evaluated at the December
    accumulation, which is exactly what an annual total is.
    """
    h = pd.read_csv(path, index_col=0)
    ann = h.groupby(["cuenca", "year"]).pp_mes.sum()
    fits, clim = {}, {}
    for c, s in ann.groupby(level=0):
        pos = s[s > 0]
        q = 1.0 - len(pos) / len(s)
        shape, loc, scl = gamma.fit(pos, floc=0)
        fits[c] = (q, shape, scl)
        clim[c] = s.mean()
    return fits, pd.Series(clim)


def to_spi(value, fit):
    q, shape, scl = fit
    cdf = q + (1 - q) * gamma.cdf(value, shape, loc=0, scale=scl)
    return float(norm.ppf(np.clip(cdf, 1e-6, 1 - 1e-6)))


def projected_spi(fits, clim, basins):
    """Delta-corrected SPI-12 for each basin, scenario and period."""
    f = pd.read_csv(FUTURE, sep=";", decimal=",")
    f = f[(f.escenario != "base") & (f.cuenca.isin(basins))]
    pp = f.groupby(["cuenca", "escenario", "year"]).pp_max.mean()
    ref = pp.groupby(level=[0, 2]).mean().xs(REF_YEAR, level=1)

    rows = []
    for (c, s, y), v in pp.items():
        delta = v / ref[c]                      # fractional change vs 2030
        corrected = delta * clim[c]             # applied to observed climatology
        rows.append({"cuenca": c, "escenario": s, "year": y,
                     "delta": delta,
                     "spi12": to_spi(corrected, fits[c]),
                     "spi12_naive": to_spi(v, fits[c])})
    return pd.DataFrame(rows)


def equilibrium(beta, names, Wd, Xbar, cols, spi_vec):
    """Long-run equilibrium price vector of the dynamic spatial Durbin model.

    In steady state y = y_lag, so
        y = rho W y + a + tau y + theta_tau W y + Z
    which solves as
        y* = [(1-tau) I - (rho + theta_tau) W]^-1 (a + Z)
    with Z collecting every covariate other than the lagged price.
    """
    b = dict(zip(names, beta))
    n = Wd.shape[0]
    X = Xbar.copy()
    X[:, cols.index("spi12")] = spi_vec

    tau = b["log_puf_mean_lag"]
    th_tau = b.get("W_log_puf_mean_lag", 0.0)
    rho = b["W_dep_var"]

    Z = np.full(n, b["CONSTANT"])
    for k, c in enumerate(cols):
        if c == "log_puf_mean_lag":
            continue
        Z += b[c] * X[:, k] + b.get("W_" + c, 0.0) * (Wd @ X[:, k])

    M = (1 - tau) * np.eye(n) - (rho + th_tau) * Wd
    return np.linalg.solve(M, Z)


def main():
    d = load_panel()
    cols = COVARS + ["spi12"]
    Y, X, WX, wp, Wd, basins = stack(d.dropna(subset=cols), cols)
    dur = [i for i, c in enumerate(cols) if not np.allclose(WX[:, i], X[:, i])]
    m = ML_Lag(Y, np.hstack([X, WX[:, dur]]), w=wp,
               name_x=cols + ["W_" + cols[i] for i in dur])
    names, bhat, V = m.name_x, np.ravel(m.betas), m.vm

    # Covariates held at estimation-sample basin means.
    n = len(basins)
    Xbar = X.reshape(-1, n, len(cols)).mean(axis=0)
    base_spi = Xbar[:, cols.index("spi12")].copy()

    fits, clim = annual_gamma(PRECIP)
    proj = projected_spi(fits, clim, basins)

    print("Delta-corrected SPI-12, basin mean by scenario and period")
    print(proj.pivot_table(index="year", columns="escenario",
                           values="spi12").round(2).to_string())
    print("\nWithout the delta correction the same basins would score")
    print(proj.pivot_table(index="year", columns="escenario",
                           values="spi12_naive").round(2).to_string())
    print("(i.e. permanent extreme drought, which is GCM bias, not signal)")

    draws = RNG.multivariate_normal(bhat, V, size=NDRAW)
    tau = draws[:, names.index("log_puf_mean_lag")]
    rho = draws[:, names.index("W_dep_var")]
    tht = draws[:, names.index("W_log_puf_mean_lag")]
    stable = (tau + rho + tht) < 1          # steady state must exist
    print(f"\nDraws discarded as dynamically explosive: {int((~stable).sum())} "
          f"of {NDRAW}")

    def logprice(spi_vec):
        return np.array([equilibrium(b, names, Wd, Xbar, cols, spi_vec).mean()
                         for b in draws[stable]])

    y_base = logprice(base_spi)
    key = {(s, y): g.set_index("cuenca").reindex(basins).spi12.values
           for (s, y), g in proj.groupby(["escenario", "year"])}
    yhat = {k: logprice(v) for k, v in key.items()}

    out = []
    for (s, y), yv in yhat.items():
        a = 100 * (np.exp(yv - y_base) - 1)                  # vs 2005-2014
        b = 100 * (np.exp(yv - yhat[(s, REF_YEAR)]) - 1)     # vs own 2030
        out.append({
            "scenario": s, "period": y,
            "dSPI_vs_2030": proj.query("escenario==@s and year==@y").spi12.mean()
                            - proj.query("escenario==@s and year==@REF_YEAR").spi12.mean(),
            "vs2030_med": np.median(b), "vs2030_p05": np.percentile(b, 5),
            "vs2030_p95": np.percentile(b, 95), "P(fall)": float((b < 0).mean()),
            "vs_baseline_med": np.median(a)})

    r = pd.DataFrame(out).sort_values(["scenario", "period"])
    print("\n\nProjected change in long-run equilibrium price, %")
    print("(90% interval propagating the full coefficient covariance)")
    print(r.round(2).to_string(index=False))
    print("\nThe 'vs2030' columns are the defensible ones: anchoring on 2030")
    print("removes both the GCM bias and the fact that 2005-2014 was itself a")
    print("dry decade relative to the 1979-2020 climatology.")


if __name__ == "__main__":
    main()
