"""
Figure 5 du rapport MTI820 — volume hebdomadaire des offres.

Cette figure documente un ARTEFACT DE COLLECTE, pas une tendance de marche :
l'API Adzuna ne retourne que les offres encore actives, si bien que les semaines
anciennes sont sous-representees (offres expirees). La pente croissante mesure la
recence de la collecte, non une croissance de l'embauche.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

SURFACE, SERIES1, DEEMPH = "#fcfcfb", "#2a78d6", "#c3c2b7"
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
})

# (libelle, total, dont depot massif, semaine complete ?)
weeks = [
    ("27 avr.", 35, 0, False),   # debut partiel : donnees a partir du 30 avril
    ("4 mai",   40, 0, True),
    ("11 mai", 435, 313, True),  # depot massif d'une seule agence le 12 mai
    ("18 mai", 148, 0, True),
    ("25 mai", 107, 0, True),
    ("1er juin", 110, 0, True),
    ("8 juin",  88, 0, True),
    ("15 juin", 88, 0, True),
    ("22 juin", 307, 0, True),
    ("29 juin", 371, 0, True),
    ("6 juil.", 392, 0, True),
    ("13 juil.", 467, 0, True),
    ("20 juil.", 83, 0, False),  # fin partielle : donnees jusqu'au 21 juillet
]

labels = [w[0] for w in weeks]
base   = [w[1] - w[2] for w in weeks]   # hors depot massif
bulk   = [w[2] for w in weeks]          # depot massif isole
full   = [w[3] for w in weeks]
x = range(len(weeks))

fig, ax = plt.subplots(figsize=(11, 5.2))

colors = [SERIES1 if f else DEEMPH for f in full]
ax.bar(x, base, width=0.64, color=colors, zorder=3)
# Le depot massif est empile a part : il ne reflete pas l'activite du marche.
ax.bar(x, bulk, bottom=base, width=0.64, color=DEEMPH, zorder=3)

ax.set_xticks(list(x))
ax.set_xticklabels(labels, fontsize=10)
ax.set_ylim(0, 580)   # marge haute : la legende occupe le haut du cadre
ax.yaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-", zorder=0)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(length=0, labelsize=10)
ax.set_ylabel("Offres publiées", fontsize=10.5, color=INK_2)

# Annotation du depot massif
ax.annotate("313 offres déposées le même jour\npar une seule agence",
            xy=(2.38, 437), xytext=(3.15, 395),
            fontsize=9.5, color=INK_2, ha="left", va="top",
            arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1))

# Semaines partielles
for i in (0, 12):
    ax.annotate("semaine\nincomplète", xy=(i, weeks[i][1] + 12),
                fontsize=8.5, color=MUTED, ha="center", va="bottom")

ax.annotate("Volume hebdomadaire des offres : un artefact de collecte",
            xy=(0, 1), xycoords="axes fraction", xytext=(0, 40),
            textcoords="offset points", fontsize=14.5, fontweight="bold",
            color=INK, ha="left", va="baseline", annotation_clip=False)
ax.annotate("Nombre d'offres par semaine de publication (n = 2 671)",
            xy=(0, 1), xycoords="axes fraction", xytext=(0, 18),
            textcoords="offset points", fontsize=10.5, color=INK_2,
            ha="left", va="baseline", annotation_clip=False)

ax.legend(handles=[Patch(facecolor=SERIES1, label="Semaine complète"),
                   Patch(facecolor=DEEMPH,
                         label="Semaine incomplète ou dépôt massif isolé")],
          loc="upper left", frameon=False, fontsize=9.5, ncol=2,
          bbox_to_anchor=(0.0, 1.0))

ax.annotate(
    "Cette progression ne mesure PAS une croissance de l'embauche : l'API Adzuna ne retourne que les offres encore actives,\n"
    "si bien que les semaines les plus anciennes sont amputées des annonces déjà expirées. La pente reflète la récence de la\n"
    "collecte. Répondre à la question de la saisonnalité exigera plusieurs mois d'extractions horodatées successives.",
    xy=(0, 0), xycoords="axes fraction", xytext=(0, -46),
    textcoords="offset points", fontsize=9, color=MUTED,
    ha="left", va="top", annotation_clip=False)

fig.savefig(OUT / "fig5_volume_hebdomadaire.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("ecrit: fig5_volume_hebdomadaire.png")
