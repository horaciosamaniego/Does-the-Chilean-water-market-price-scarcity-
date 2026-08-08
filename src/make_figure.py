"""Figure: projected change in water rights prices under two SSP scenarios.

Replaces Figures 2 and 3 of the original manuscript. Plots the median change in
long-run equilibrium price relative to each scenario's own 2021-2040 value, with
a 90% band propagating the full coefficient covariance of the spatial Durbin
model.

Anchoring on the first projected period rather than on the 2005-2014 sample is
deliberate: it removes MIROC6's dry bias, which both scenarios share before they
diverge, and it avoids reading the 2005-2014 decade's own negative SPI anomaly
as part of the future signal.

Depends on wr_spatial_corrected.py and wr_projection.py in the same directory.

Run:  python make_figure.py
"""
import warnings

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from spreg import ML_Lag

from wr_projection import (NDRAW, REF_YEAR, annual_gamma, equilibrium,
                           projected_spi)
from wr_spatial_corrected import COVARS, FIGURES, PRECIP, load_panel, stack

warnings.filterwarnings("ignore")

PERIODS = [2030, 2050, 2070, 2090]
LABELS = ["2021–2040", "2041–2060", "2061–2080", "2081–2100"]
STYLE = {"SSP126": ("#2c7fb8", "o", "SSP1-2.6"),
         "SSP585": ("#cb4b16", "s", "SSP5-8.5")}
SEED = 20260808


def fit_model():
    d = load_panel()
    cols = COVARS + ["spi12"]
    Y, X, WX, wp, Wd, basins = stack(d.dropna(subset=cols), cols)
    dur = [i for i, c in enumerate(cols) if not np.allclose(WX[:, i], X[:, i])]
    m = ML_Lag(Y, np.hstack([X, WX[:, dur]]), w=wp,
               name_x=cols + ["W_" + cols[i] for i in dur])
    # Covariates other than the drought index are held at basin means.
    Xbar = X.reshape(-1, len(basins), len(cols)).mean(axis=0)
    return m, Wd, Xbar, cols, basins


def simulate(m, Wd, Xbar, cols, basins):
    """Posterior draws of the equilibrium log price for each scenario-period."""
    names, bhat, V = m.name_x, np.ravel(m.betas), m.vm
    draws = np.random.default_rng(SEED).multivariate_normal(bhat, V, size=NDRAW)
    stable = (draws[:, names.index("log_puf_mean_lag")]
              + draws[:, names.index("W_dep_var")]
              + draws[:, names.index("W_log_puf_mean_lag")]) < 1
    draws = draws[stable]

    fits, clim = annual_gamma(PRECIP)
    proj = projected_spi(fits, clim, basins)
    out = {}
    for (s, y), g in proj.groupby(["escenario", "year"]):
        spi_vec = g.set_index("cuenca").reindex(basins).spi12.values
        out[(s, y)] = np.array([
            equilibrium(b, names, Wd, Xbar, cols, spi_vec).mean() for b in draws])
    return out


def draw(yhat, path="figure_projection"):
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for s, (colour, marker, label) in STYLE.items():
        pct = np.array([100 * (np.exp(yhat[(s, y)] - yhat[(s, REF_YEAR)]) - 1)
                        for y in PERIODS])
        ax.fill_between(PERIODS, np.percentile(pct, 5, axis=1),
                        np.percentile(pct, 95, axis=1),
                        color=colour, alpha=0.16, lw=0)
        ax.plot(PERIODS, np.median(pct, axis=1), color=colour, marker=marker,
                lw=2, ms=6, label=label)
    ax.axhline(0, color="0.4", lw=0.8, ls="--")
    ax.set_xlabel("Period")
    ax.set_ylabel("Change in equilibrium price (%)")
    ax.set_xticks(PERIODS)
    ax.set_xticklabels(LABELS)
    ax.legend(frameon=False, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(f"{path}.pdf")
    fig.savefig(f"{path}.png", dpi=200)
    print(f"wrote {path}.pdf and {path}.png")


if __name__ == "__main__":
    draw(simulate(*fit_model()), path=str(FIGURES / "figure_projection"))
