"""
Figures du rapport MTI820 — marché de l'emploi TI à Montréal.
Données : entrepôt PostgreSQL (backup.sql), 2 671 offres, 30 avril – 21 juillet 2026.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# --- Palette (instance de référence, mode clair) ---
SURFACE   = "#fcfcfb"
SERIES1   = "#2a78d6"   # slot categoriel 1 (bleu)
DEEMPH    = "#c3c2b7"   # gris de mise en retrait
INK       = "#0b0b0b"
INK_2     = "#52514e"
MUTED     = "#898781"
GRID      = "#e1e0d9"
TOTAL     = 2671

plt.rcParams.update({
    "font.family":      ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "figure.facecolor": SURFACE,
    "axes.facecolor":   SURFACE,
    "savefig.facecolor": SURFACE,
    "text.color":       INK,
    "axes.labelcolor":  INK_2,
    "xtick.color":      MUTED,
    "ytick.color":      INK_2,
    "axes.edgecolor":   GRID,
})


def style_axes(ax, xmax):
    """Grille en filet solide, axes récessifs, pas de cadre."""
    ax.set_xlim(0, xmax)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-", zorder=0)
    ax.set_axisbelow(True)
    ax.yaxis.grid(False)
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["left"].set_linewidth(0.8)
    ax.tick_params(axis="both", length=0, labelsize=10)


def fr(x, dec=1):
    """Formatage francais : espace fine pour les milliers, virgule decimale."""
    if isinstance(x, int):
        return f"{x:,}".replace(",", " ")
    return f"{x:.{dec}f}".replace(".", ",")


def add_note(ax, note):
    """Note de bas de figure ancree en points sous les axes.

    Ancrer en coordonnees figure fait chevaucher la note et les libelles
    d'axe ; un decalage en points depuis le bas des axes passe dessous.
    """
    ax.annotate(note, xy=(0, 0), xycoords="axes fraction",
                xytext=(0, -48), textcoords="offset points",
                fontsize=9, color=MUTED, ha="left", va="top",
                annotation_clip=False)


def add_titles(ax, title, subtitle):
    """Titre + sous-titre ancres en points depuis le haut des axes.

    Un decalage en fraction d'axes varie avec la hauteur de la figure et finit
    par faire chevaucher les deux lignes ; un decalage en points est stable.
    """
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction",
                xytext=(0, 34), textcoords="offset points",
                fontsize=14.5, fontweight="bold", color=INK,
                ha="left", va="baseline", annotation_clip=False)
    ax.annotate(subtitle, xy=(0, 1), xycoords="axes fraction",
                xytext=(0, 14), textcoords="offset points",
                fontsize=10.5, color=INK_2,
                ha="left", va="baseline", annotation_clip=False)


def barh_figure(fname, title, subtitle, labels, values, colors,
                note=None, fmt=fr):
    n = len(labels)
    fig, ax = plt.subplots(figsize=(9, 0.46 * n + 2.1))
    y = range(n)
    ax.barh(y, values, height=0.62, color=colors, zorder=2)
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=10.5)
    ax.invert_yaxis()

    xmax = max(values) * 1.16
    style_axes(ax, xmax)

    # Etiquettes directes en bout de barre (aucune infobulle sur une figure imprimee)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.012, yi, fmt(v), va="center", ha="left",
                fontsize=10, color=INK_2)

    add_titles(ax, title, subtitle)
    if note:
        add_note(ax, note)

    fig.savefig(OUT / fname, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("ecrit:", fname)


# --- Figure 1 : competences -------------------------------------------------
skills = [("Java", 87), ("Azure", 49), ("AWS", 39), ("Python", 38),
          ("SQL", 22), ("React", 21), ("Power BI", 10), ("Spark", 9),
          ("Kubernetes", 6), ("Tableau", 4), ("Docker", 1)]
barh_figure(
    "fig1_competences.png",
    "Compétences technologiques les plus demandées",
    "Nombre d'offres mentionnant la compétence (n = 2 671 offres)",
    [s for s, _ in skills], [v for _, v in skills],
    [SERIES1] * len(skills),
    note="Source : entrepôt Adzuna, 30 avril – 21 juillet 2026. Seules 236 offres (8,8 %) "
         "mentionnent au moins une des 11 compétences suivies,\nen raison de la troncature "
         "des descriptions par l'API (~500 caractères).",
)

# --- Figure 2 : biais de concentration (emphase) ----------------------------
comps = [("Jose Merciline", 313), ("TEHORA", 80), ("Ubisoft", 69),
         ("Targeted Talent", 67), ("Genetec", 63), ("CGI", 47),
         ("Alithya", 42), ("Bombardier", 41)]
barh_figure(
    "fig2_biais_recruteur.png",
    "Un seul recruteur concentre 11,7 % du corpus",
    "Nombre d'offres publiées, 8 principaux annonceurs",
    [c for c, _ in comps], [v for _, v in comps],
    [SERIES1] + [DEEMPH] * (len(comps) - 1),
    note="L'agence « Jose Merciline » publie à elle seule 313 des 2 671 offres, dont une part "
         "majoritaire de postes Java :\nla position de tête de Java résulte donc en partie d'une "
         "stratégie de multi-diffusion, non d'une demande répartie sur le marché.",
)

# --- Figure 3 : modalites de contrat ----------------------------------------
contracts = [("Inconnu / Inconnu", 1406), ("Temps plein / Inconnu", 667),
             ("Inconnu / Permanent", 222), ("Inconnu / Contractuel", 165),
             ("Temps plein / Permanent", 131), ("Temps plein / Contractuel", 60),
             ("Temps partiel (toutes)", 20)]
barh_figure(
    "fig3_contrats.png",
    "Plus de la moitié des offres ne précisent aucune modalité de contrat",
    "Répartition des 2 671 offres par temps de travail et type de contrat",
    [c for c, _ in contracts], [v for _, v in contracts],
    [SERIES1] + [DEEMPH] * (len(contracts) - 1),
    fmt=lambda v: f"{fr(v)}  ({fr(v / TOTAL * 100)} %)",
    note="La catégorie « temps plein / permanent » ne représente que 4,9 % du corpus : il serait "
         "incorrect d'affirmer\nque la majorité des postes sont permanents à temps plein.",
)

# --- Figure 4 : couverture des donnees (jauges) -----------------------------
fig, ax = plt.subplots(figsize=(9, 3.1))
metrics = [("Offres avec salaire renseigné", 206, 7.7),
           ("Offres avec ≥ 1 compétence détectée", 236, 8.8)]
for i, (label, n, pct) in enumerate(metrics):
    y = 1 - i
    ax.barh(y, 100, height=0.30, color=GRID, zorder=2)          # piste
    ax.barh(y, pct, height=0.30, color=SERIES1, zorder=3)       # remplissage
    ax.text(0, y + 0.30, label, va="bottom", ha="left", fontsize=11, color=INK)
    ax.text(100, y + 0.30, f"{fr(pct)} %   ({fr(n)} / {fr(TOTAL)} offres)",
            va="bottom", ha="right", fontsize=11, color=INK_2)

ax.set_xlim(0, 100)
ax.set_ylim(-0.62, 1.72)
ax.set_yticks([])
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0 %", "25 %", "50 %", "75 %", "100 %"], fontsize=10)
ax.xaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-", zorder=0)
ax.set_axisbelow(True)
for side in ("top", "right", "left", "bottom"):
    ax.spines[side].set_visible(False)
ax.tick_params(length=0)
add_titles(ax, "Couverture réelle des données analysables",
           "Part des 2 671 offres exploitables pour chaque type d'analyse")
add_note(ax,
         "Ces deux taux constituent la principale limite du prototype : les analyses salariales et "
         "de compétences\nportent sur moins de 9 % du corpus et doivent être lues comme des "
         "tendances indicatives.")
fig.savefig(OUT / "fig4_couverture_donnees.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print("ecrit: fig4_couverture_donnees.png")
print("\nDossier:", OUT)
