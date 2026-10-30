"""
Computational experiment for APKN-2026 theses.
Compares three methods of generating a 10-step tonal scale (50..900)
from a single brand colour and checks the accessibility "contract"
of a design system built on that scale (WCAG 2.2 contrast ratios).

Methods:
  A  HSL      - keep seed H,S; fixed HSL lightness ladder
  B  OKLCH    - keep seed h, relative chroma; uniform OKLCH lightness ladder
  C  CA-OKLCH - proposed contrast-anchored OKLCH: per step, solve OKLCH L
                (bisection) so the colour hits a target WCAG contrast vs white;
                chroma = seed's relative chroma * max in-gamut chroma at (L,h)
"""
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)

rng = np.random.default_rng(2026)
N = 2000
STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

# ---------------- colour maths ----------------
def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def lin_to_srgb(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.clip(c, 0, None), 1 / 2.4) - 0.055)

def rel_lum(rgb):  # WCAG 2.x relative luminance, rgb in 0..1 (gamma-encoded)
    lin = srgb_to_lin(np.clip(rgb, 0, 1))
    return 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]

def contrast(y1, y2):
    hi, lo = np.maximum(y1, y2), np.minimum(y1, y2)
    return (hi + 0.05) / (lo + 0.05)

M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
               [0.2119034982, 0.6806995451, 0.1073969566],
               [0.0883024619, 0.2817188376, 0.6299787005]])
M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
               [1.9779984951, -2.4285922050, 0.4505937099],
               [0.0259040371, 0.7827717662, -0.8086757660]])
M1i = np.linalg.inv(M1)
M2i = np.linalg.inv(M2)

def srgb_to_oklab(rgb):
    lms = srgb_to_lin(rgb) @ M1.T
    return np.cbrt(lms) @ M2.T

def oklab_to_lin(lab):
    lms = (np.asarray(lab) @ M2i.T) ** 3
    return lms @ M1i.T

def oklab_to_srgb(lab):
    return lin_to_srgb(oklab_to_lin(lab))

def lch_to_lab(L, C, h):
    hr = np.radians(h)
    return np.stack([L, C * np.cos(hr), C * np.sin(hr)], axis=-1)

def lab_to_lch(lab):
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    return L, np.hypot(a, b), np.degrees(np.arctan2(b, a)) % 360

def in_gamut(lab, eps=1e-6):
    lin = oklab_to_lin(lab)
    return np.all((lin >= -eps) & (lin <= 1 + eps), axis=-1)

def max_chroma(L, h, iters=30):
    lo, hi = 0.0, 0.5
    for _ in range(iters):
        mid = (lo + hi) / 2
        if in_gamut(lch_to_lab(np.array(L), np.array(mid), np.array(h))):
            lo = mid
        else:
            hi = mid
    return lo

def hsl_to_rgb(h, s, l):
    c = (1 - abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(hp) % 6]
    m = l - c / 2
    return np.array([r + m, g + m, b + m])

def rgb_to_hsl(rgb):
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    l = (mx + mn) / 2
    d = mx - mn
    if d == 0:
        return 0.0, 0.0, l
    s = d / (1 - abs(2 * l - 1))
    if mx == r:
        h = 60 * (((g - b) / d) % 6)
    elif mx == g:
        h = 60 * ((b - r) / d + 2)
    else:
        h = 60 * ((r - g) / d + 4)
    return h, s, l

# ---------------- seed brand colours ----------------
def sample_seed():
    while True:
        h = rng.uniform(0, 360)
        L = rng.uniform(0.45, 0.80)
        cmax = max_chroma(L, h)
        if cmax < 0.06:
            continue
        C = rng.uniform(0.55, 1.0) * cmax          # brand colours are fairly saturated
        rgb = np.clip(oklab_to_srgb(lch_to_lab(np.array(L), np.array(C), np.array(h))), 0, 1)
        return rgb

seeds = [sample_seed() for _ in range(N)]

# ---------------- scale generators ----------------
HSL_LADDER = [0.97, 0.93, 0.86, 0.76, 0.64, 0.52, 0.42, 0.34, 0.26, 0.18]
OK_LADDER = np.linspace(0.97, 0.30, 10)
# target contrast against white for each step (proposed method)
CA_TARGETS = [1.06, 1.15, 1.35, 1.75, 2.4, 3.2, 4.8, 6.5, 9.5, 13.5]

def scale_hsl(seed):
    h, s, _ = rgb_to_hsl(seed)
    return np.array([hsl_to_rgb(h, s, l) for l in HSL_LADDER])

def rel_chroma(seed):
    L, C, h = lab_to_lch(srgb_to_oklab(seed))
    cm = max_chroma(float(L), float(h))
    return float(h), float(C / cm if cm > 0 else 0)

def colour_at(L, h, rc):
    C = rc * max_chroma(L, h)
    return np.clip(oklab_to_srgb(lch_to_lab(np.array(L), np.array(C), np.array(h))), 0, 1)

def scale_oklch(seed):
    h, rc = rel_chroma(seed)
    return np.array([colour_at(L, h, rc) for L in OK_LADDER])

def scale_ca(seed):
    h, rc = rel_chroma(seed)
    out = []
    for c_t in CA_TARGETS:
        y_t = 1.05 / c_t - 0.05            # luminance giving contrast c_t vs white
        lo, hi = 0.0, 1.0
        for _ in range(28):                # Y is monotonic in L at fixed h, rel. chroma
            mid = (lo + hi) / 2
            if rel_lum(colour_at(mid, h, rc)) > y_t:
                hi = mid
            else:
                lo = mid
        out.append(colour_at(lo, h, rc))   # lo side => contrast >= target
    return np.array(out)

METHODS = {"HSL": scale_hsl, "OKLCH": scale_oklch, "CA-OKLCH": scale_ca}

# ---------------- design-system accessibility contract ----------------
# (foreground step, background step or 'white', min ratio, WCAG SC)
I = {s: i for i, s in enumerate(STEPS)}
CONTRACT = [
    ("white", 600, 4.5, "1.4.3 white text on primary button (600)"),
    (700, "white", 4.5, "1.4.3 link/body text 700 on white"),
    (700, 50, 4.5, "1.4.3 text 700 on tinted surface 50"),
    (500, "white", 3.0, "1.4.11 UI component / focus ring 500 on white"),
    (100, 800, 4.5, "1.4.3 dark theme: text 100 on surface 800"),
]

def lum_of(scale_y, ref):
    return 1.0 if ref == "white" else scale_y[I[ref]]

def evaluate(scale):
    y = rel_lum(scale)
    res = []
    for fg, bg, need, _ in CONTRACT:
        res.append(contrast(lum_of(y, fg), lum_of(y, bg)) >= need)
    lab = srgb_to_oklab(scale)
    d = np.linalg.norm(np.diff(lab, axis=0), axis=1)
    cv = d.std() / d.mean()                      # unevenness of adjacent steps
    L, C, hh = lab_to_lch(lab)
    return np.array(res), cv, lab, C, hh

results = {}
hue_bins = np.arange(0, 361, 30)
for name, fn in METHODS.items():
    passes, cvs, drift, fid, seed_h, cw = [], [], [], [], [], []
    for s in seeds:
        sc = fn(s)
        cw.append(contrast(1.0, rel_lum(sc)))
        p, cv, lab, C, hh = evaluate(sc)
        _, _, h0 = lab_to_lch(srgb_to_oklab(s))
        mask = C > 0.02
        dh = np.abs((hh[mask] - h0 + 180) % 360 - 180)
        passes.append(p); cvs.append(cv); drift.append(dh.mean() if mask.any() else 0)
        fid.append(np.min(np.linalg.norm(lab - srgb_to_oklab(s), axis=1)))
        seed_h.append(float(h0))
    passes = np.array(passes)
    seed_h = np.array(seed_h)
    cw = np.array(cw)
    np.save(OUT / f"cw_{name}.npy", cw)
    np.save(OUT / "seed_h.npy", seed_h)
    per_bin = []
    for a, b in zip(hue_bins[:-1], hue_bins[1:]):
        m = (seed_h >= a) & (seed_h < b)
        per_bin.append(float(passes[m, 0].mean() * 100) if m.any() else None)
    results[name] = {
        "contract_full_pass_pct": float(passes.all(axis=1).mean() * 100),
        "per_pair_pass_pct": [float(v) for v in passes.mean(axis=0) * 100],
        "step_unevenness_cv_mean": float(np.mean(cvs)),
        "hue_drift_deg_mean": float(np.mean(drift)),
        "hue_drift_deg_p95": float(np.percentile(drift, 95)),
        "brand_fidelity_dE_ok_mean": float(np.mean(fid)),
        "white_on_600_pass_by_hue_pct": per_bin,
        "contrast_vs_white_min": [float(v) for v in cw.min(axis=0)],
        "contrast_vs_white_median": [float(v) for v in np.median(cw, axis=0)],
        "contrast_vs_white_max": [float(v) for v in cw.max(axis=0)],
    }

results["_meta"] = {"N": N, "seed": 2026, "contract": [c[3] for c in CONTRACT],
                    "hue_bins": hue_bins.tolist(), "ca_targets": CA_TARGETS}
with open(OUT / "results.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "white_on_600_pass_by_hue_pct"}
                  for k, v in results.items() if k != "_meta"}, indent=2))
for k in METHODS:
    print(k, [None if v is None else round(v) for v in results[k]["white_on_600_pass_by_hue_pct"]])
