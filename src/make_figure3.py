"""Figure 3: direct and indirect effects with Monte Carlo uncertainty.

Table 3 reports effects as point estimates only. This version adds 90%
intervals obtained by drawing from the estimated coefficient distribution and
recomputing the LeSage-Pace multiplier matrix for each draw, so the figure
carries strictly more information than the table it replaces.

Inference on effects is not the same as inference on coefficients. The raw
W x SPI-12 coefficient sits at p = 0.075, but the SPI-12 *indirect effect*
interval excludes zero, because the effect combines rho and theta and the two
covary. That is the substantive reason LeSage and Pace argue inference belongs
on effects.

Run:  python make_figure3.py
"""
import warnings

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from spreg import ML_Lag

from wr_spatial_corrected import COVARS, FIGURES, load_panel, stack

warnings.filterwarnings("ignore")

WET, DRY, INK, RULE, BG = "#14657a", "#9a6b14", "#10222c", "#c2cdd1", "#ffffff"
NDRAW, SEED = 4000, 20260808

# Plotted top to bottom. Effects are in log price units, so the near-zero rows
# are kept for completeness but carry little interpretive content.
LABELS = {
    "log_puf_mean_lag": "Lagged price",
    "dummy_dec_esc_lag": "Lagged scarcity decree",
    "spi12": "SPI-12",
    "dummy_mina": "Mining presence",
    "n_transacciones": "Number of transactions",
    "estival": "Summer",
    "caudal_dummy_escasez": "Flow \u00d7 scarcity decree",
    "caudal_transado": "Transaction flow",
}


def simulate():
    """Posterior draws of direct and indirect effects for every covariate."""
    d = load_panel()
    cols = COVARS + ["spi12"]
    Y, X, WX, wp, Wd, basins = stack(d.dropna(subset=cols), cols)
    dur = [i for i, c in enumerate(cols) if not np.allclose(WX[:, i], X[:, i])]
    m = ML_Lag(Y, np.hstack([X, WX[:, dur]]), w=wp,
               name_x=cols + ["W_" + cols[i] for i in dur])

    names, bhat, V = m.name_x, np.ravel(m.betas), m.vm
    draws = np.random.default_rng(SEED).multivariate_normal(bhat, V, size=NDRAW)
    ix = {n: i for i, n in enumerate(names)}
    I = np.eye(len(basins))

    out = {}
    for c in cols:
        vals = np.empty((len(draws), 2))
        for j, b in enumerate(draws):
            A = np.linalg.inv(I - b[ix["W_dep_var"]] * Wd)
            theta = b[ix["W_" + c]] if "W_" + c in ix else 0.0
            S = A @ (b[ix[c]] * I + theta * Wd)
            direct = np.mean(np.diag(S))
            total = np.mean(S.sum(axis=1))
            vals[j] = (direct, total - direct)
        out[c] = vals
    return out


def draw(eff, path):
    keys = [k for k in LABELS if k in eff]
    y = np.arange(len(keys))[::-1]
    off = 0.19

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for i, k in enumerate(keys):
        for col, colour, sign in ((0, WET, +1), (1, DRY, -1)):
            v = eff[k][:, col]
            lo, md, hi = np.percentile(v, [5, 50, 95])
            pos = y[i] + sign * off
            # Interval excluding zero drawn solid, otherwise open.
            solid = (lo > 0) or (hi < 0)
            ax.plot([lo, hi], [pos, pos], color=colour, lw=2.2,
                    solid_capstyle="butt", alpha=1.0 if solid else 0.45)
            ax.plot(md, pos, "o", ms=6, color=colour if solid else BG,
                    markeredgecolor=colour, markeredgewidth=1.6, zorder=3)

    ax.axvline(0, color=INK, lw=1.0, zorder=1)
    ax.set_yticks(y)
    ax.set_yticklabels([LABELS[k] for k in keys])
    ax.set_ylim(-0.7, len(keys) - 0.3)
    ax.set_xlabel("Effect on log price")
    ax.grid(axis="x", color=RULE, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)

    ax.legend(handles=[
        Line2D([0], [0], color=WET, lw=2.2, marker="o", ms=6, label="Direct"),
        Line2D([0], [0], color=DRY, lw=2.2, marker="o", ms=6, label="Indirect"),
        Line2D([0], [0], color=INK, lw=0, marker="o", ms=6, mfc=BG,
               mec=INK, mew=1.6, label="Interval spans zero")],
        frameon=False, loc="lower right", fontsize=9)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{path}.{ext}", dpi=200, facecolor=BG)
    print(f"wrote {path}.pdf and {path}.png")


def report(eff):
    print(f"\n{'variable':24s}{'direct':>9s}{'90% interval':>22s}"
          f"{'indirect':>11s}{'90% interval':>22s}")
    for k in LABELS:
        if k not in eff:
            continue
        d, i = eff[k][:, 0], eff[k][:, 1]
        qd, qi = np.percentile(d, [5, 50, 95]), np.percentile(i, [5, 50, 95])
        star = "  *" if (qi[0] > 0 or qi[2] < 0) else ""
        print(f"{LABELS[k]:24s}{qd[1]:9.4f}  [{qd[0]:7.4f},{qd[2]:7.4f}]"
              f"{qi[1]:11.4f}  [{qi[0]:7.4f},{qi[2]:7.4f}]{star}")
    print("\n* indirect interval excludes zero")


if __name__ == "__main__":
    e = simulate()
    report(e)
    draw(e, str(FIGURES / "figure_effects"))