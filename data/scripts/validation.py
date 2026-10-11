"""
Hagen-Poiseuille validation — ANSYS Fluent vs. theory
=====================================================
Reads the XY exports from Fluent (data/*.xy) and produces:
  - images/11_validation_profile.png   : CFD profile at x = 0.8 m vs. Poiseuille parabola
  - images/12_validation_axis.png      : centerline velocity + entrance length
  - images/09b_profile_development.png : clean version of the profile development plot

Usage (from the repository root):
    pip install numpy matplotlib
    python scripts/validation.py
"""

from pathlib import Path
import re
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Case parameters
# ---------------------------------------------------------------------------
R = 0.01            # pipe radius [m]
D = 2 * R           # diameter [m]
U_MEAN = 0.0251     # inlet (= mean) velocity [m/s]
RHO = 998.2         # density [kg/m3]
MU = 1.003e-3       # dynamic viscosity [Pa.s]

RE = RHO * U_MEAN * D / MU
U_MAX_TH = 2 * U_MEAN                     # Poiseuille centerline velocity
LE_DURST = D * (0.619**1.6 + (0.0567 * RE)**1.6) ** (1 / 1.6)


# ---------------------------------------------------------------------------
# Fluent .xy reader
# ---------------------------------------------------------------------------
def read_fluent_xy(path):
    """Return {label: (x, y)} for every curve in a Fluent XY export file.
    Points are sorted by x (Fluent does not always write them in order)."""
    curves, label, pts = {}, None, []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        m = re.match(r'\(\(xy/key/label\s+"(.+)"\)', line)
        if m:
            label, pts = m.group(1), []
            continue
        if line.startswith(")") and label is not None:
            arr = np.array(pts)
            order = np.argsort(arr[:, 0])
            curves[label] = (arr[order, 0], arr[order, 1])
            label = None
            continue
        if label is not None and line:
            try:
                x, y = map(float, line.split()[:2])
                pts.append((x, y))
            except ValueError:
                pass
    return curves


def first_curve(path):
    return next(iter(read_fluent_xy(path).values()))


# ---------------------------------------------------------------------------
# Plot style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 11,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


# ---------------------------------------------------------------------------
# Figure 11 — velocity profile at x = 0.8 m
# ---------------------------------------------------------------------------
r_cfd, u_cfd = first_curve(DATA / "profil_x08.xy")
r_th = np.linspace(0, R, 200)
u_th = U_MAX_TH * (1 - (r_th / R) ** 2)

err_umax = abs(u_cfd.max() - U_MAX_TH) / U_MAX_TH * 100
u_th_at_cfd = U_MAX_TH * (1 - (r_cfd / R) ** 2)
err_rms = np.sqrt(np.mean((u_cfd - u_th_at_cfd) ** 2)) / U_MAX_TH * 100

fig, ax = plt.subplots(figsize=(7, 5))
ax.plot(u_th * 1e3, r_th * 1e3, "k-", lw=2, label="Analytical (Poiseuille)")
ax.plot(u_cfd[::2] * 1e3, r_cfd[::2] * 1e3, "o", ms=5, mfc="none",
        color="tab:red", label="CFD (Fluent), x = 0.8 m")
ax.set_xlabel("Axial velocity u [mm/s]")
ax.set_ylabel("Radial position r [mm]")
ax.set_title(f"Fully developed profile — Re = {RE:.0f}")
ax.text(0.03, 0.05,
        f"u_max error: {err_umax:.2f} %\nRMS error: {err_rms:.2f} % of u_max",
        transform=ax.transAxes,
        bbox=dict(boxstyle="round", fc="white", ec="0.7"))
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(IMG / "11_validation_profile.png")
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 12 — centerline velocity and entrance length
# ---------------------------------------------------------------------------
x_ax, u_ax = first_curve(DATA / "vitesse_axe.xy")
threshold = 0.99 * U_MAX_TH
i = np.argmax(u_ax >= threshold)          # first point above the 99 % threshold
le_cfd = np.interp(threshold, u_ax[i - 1:i + 1], x_ax[i - 1:i + 1])
err_le = abs(le_cfd - LE_DURST) / LE_DURST * 100

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(x_ax, u_ax * 1e3, color="tab:blue", lw=2, label="CFD centerline velocity")
ax.axhline(U_MAX_TH * 1e3, color="k", ls="--", label="Fully developed: 2Ū")
ax.axhline(threshold * 1e3, color="0.5", ls=":", label="99 % threshold")
ax.axvline(le_cfd, color="tab:blue", ls="-.", lw=1.2,
           label=f"L_e CFD = {le_cfd:.3f} m")
ax.axvline(LE_DURST, color="tab:red", ls="-.", lw=1.2,
           label=f"L_e Durst et al. = {LE_DURST:.3f} m")
ax.set_xlabel("Axial position x [m]")
ax.set_ylabel("Centerline velocity [mm/s]")
ax.set_title(f"Entrance length — error {err_le:.1f} %")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(IMG / "12_validation_axis.png")
plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 09b — profile development (clean labels)
# ---------------------------------------------------------------------------
LABELS = {"le-x002": 0.02, "le-x01": 0.1, "le-x02": 0.2,
          "le-x04": 0.4, "profil-x08": 0.8}
dev_file = DATA / "profils_developpement.xy"
if dev_file.exists():
    curves = read_fluent_xy(dev_file)
    fig, ax = plt.subplots(figsize=(7, 5))
    cmap = plt.get_cmap("viridis")
    items = sorted(curves.items(), key=lambda kv: LABELS.get(kv[0], 99))
    for k, (name, (r, u)) in enumerate(items):
        x_pos = LABELS.get(name)
        lab = f"x = {x_pos} m" if x_pos is not None else name
        ax.plot(u * 1e3, r * 1e3, lw=2, color=cmap(k / max(len(items) - 1, 1)),
                label=lab)
    ax.plot(u_th * 1e3, r_th * 1e3, "k--", lw=1.2, label="Poiseuille")
    ax.set_xlabel("Axial velocity u [mm/s]")
    ax.set_ylabel("Radial position r [mm]")
    ax.set_title("Development of the velocity profile")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(IMG / "09b_profile_development.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print(f"Re                     = {RE:.1f}")
print(f"u_max  CFD / theory    = {u_cfd.max():.5f} / {U_MAX_TH:.5f} m/s"
      f"  ({err_umax:.2f} %)")
print(f"Profile RMS error      = {err_rms:.2f} % of u_max")
print(f"L_e    CFD / Durst     = {le_cfd:.3f} / {LE_DURST:.3f} m"
      f"  ({err_le:.1f} %)")
print(f"Figures saved in {IMG}")
