import logging
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

D = Path(__file__).resolve().parent / "results"
h = np.load(D / "seed_h.npy")
cw = {k: np.load(D / f"cw_{k}.npy")[:, 6] for k in ["HSL", "OKLCH", "CA-OKLCH"]}  # step 600

plt.rcParams.update({"font.family": ["Times New Roman", "Liberation Serif", "DejaVu Serif"], "font.size": 8,
                     "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(108 / 25.4, 60 / 25.4), dpi=300)
ink2, grid = "#52514e", "#d9d8d4"
ax.grid(axis="y", color=grid, lw=0.5); ax.set_axisbelow(True)
for s in ["left", "bottom"]:
    ax.spines[s].set_color(ink2); ax.spines[s].set_linewidth(0.6)
ax.tick_params(colors=ink2, width=0.6, length=3)

ax.scatter(h, cw["HSL"], s=3, marker="o", color="#eb6834", alpha=0.55, lw=0)
ax.scatter(h, cw["OKLCH"], s=3, marker="^", color="#2a78d6", alpha=0.55, lw=0)
order = np.argsort(h)
ax.plot(h[order], cw["CA-OKLCH"][order], color="#1baf7a", lw=1.6)
ax.axhline(4.5, color="#0b0b0b", lw=0.8, ls=(0, (4, 2)))

ax.text(362, 4.5, " 4.5:1\n (AA)", va="center", ha="left", fontsize=7, color="#0b0b0b")
from matplotlib.lines import Line2D
hs=[Line2D([],[],marker="o",ls="",color="#eb6834",ms=4,label="A: HSL ladder"),
    Line2D([],[],marker="^",ls="",color="#2a78d6",ms=4,label="B: OKLCH ladder"),
    Line2D([],[],color="#1baf7a",lw=1.6,label="C: CA-OKLCH (target 4.8:1)")]
ax.legend(handles=hs, loc="upper left", bbox_to_anchor=(0.06,1.0), frameon=False, fontsize=7, handletextpad=0.4, borderaxespad=0.2)

ax.set_xlim(0, 360); ax.set_ylim(0, 11.5)
ax.set_xticks(range(0, 361, 60))
ax.set_xlabel("Hue of the seed brand color, OKLCH h (°)", color=ink2)
ax.set_ylabel("Contrast of step 600 vs white", color=ink2)
fig.tight_layout(pad=0.3)
fig.subplots_adjust(right=0.88)
fig.savefig(D / "fig1.png", dpi=300)
print("ok")
