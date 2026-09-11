"""
Identidad visual Ajinomoto para el dashboard: rojo institucional #ED1C24
sobre blanco. Aquí viven la paleta y el CSS que comparten app.py y las
tres pestañas.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Paleta
# --------------------------------------------------------------------------- #
AJI_RED = "#ED1C24"          # rojo institucional
AJI_RED_DARK = "#B3151B"     # hover / texto sobre fondo claro
AJI_RED_SOFT = "rgba(237,28,36,0.10)"
WHITE = "#FFFFFF"
INK = "#1A1A1A"
INK_SOFT = "#6B6B6B"
GRID = "rgba(26,26,26,0.12)"

# Serie categórica derivada del rojo institucional + neutros (para desgloses).
PALETTE = ["#ED1C24", "#F4767B", "#B3151B", "#F7A8AC", "#7A0E12", "#2B2B2B", "#9E9E9E"]
ACCENT = AJI_RED

# --------------------------------------------------------------------------- #
# CSS global
# --------------------------------------------------------------------------- #
CSS = """
<style>
  .stApp { background: #FFFFFF; }
  .block-container { padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1400px; }
  h1, h2, h3 { font-weight: 800; letter-spacing: -0.01em; color: #1A1A1A; }
  h1 { color: #ED1C24; }

  /* Franja de marca bajo el encabezado */
  .aji-rule { height: 4px; background: #ED1C24; border-radius: 2px; margin: .4rem 0 1.2rem; }

  /* Tarjetas de KPI */
  div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid rgba(26,26,26,0.12);
    border-left: 4px solid #ED1C24;
    border-radius: 12px;
    padding: 14px 16px 12px;
    box-shadow: 0 1px 3px rgba(26,26,26,0.06);
  }
  div[data-testid="stMetric"] label p {
    font-size: .76rem; color: #6B6B6B; font-weight: 700;
    text-transform: uppercase; letter-spacing: .03em;
  }
  div[data-testid="stMetricValue"] { font-size: 1.6rem; color: #1A1A1A; }

  /* Pestañas */
  button[data-baseweb="tab"] { font-weight: 700; color: #6B6B6B; }
  button[data-baseweb="tab"][aria-selected="true"] { color: #ED1C24; }
  div[data-baseweb="tab-highlight"] { background-color: #ED1C24 !important; }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: #FAFAFA; border-right: 1px solid rgba(26,26,26,0.08);
  }
  section[data-testid="stSidebar"] h1 { font-size: 1.05rem; color: #ED1C24; }

  /* Botones primarios */
  button[kind="primary"] { background: #ED1C24; border-color: #ED1C24; }
  button[kind="primary"]:hover { background: #B3151B; border-color: #B3151B; }

  /* Chip */
  .chip {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    background: rgba(237,28,36,.10); color: #B3151B; font-size: .78rem; font-weight: 700;
    border: 1px solid rgba(237,28,36,.30);
  }
  hr { margin: 1.1rem 0; opacity: .10; }

  /* Leaderboard (Top promotores) */
  .aji-lb { display: flex; flex-direction: column; gap: 10px; }
  .aji-lb-row {
    display: flex; align-items: center; gap: 12px;
    background: #FFFFFF; border: 1px solid rgba(26,26,26,0.10); border-radius: 10px;
    padding: 8px 12px;
  }
  .aji-lb-rank {
    flex: 0 0 20px; font-size: .78rem; font-weight: 800; color: #B0B0B0; text-align: center;
  }
  .aji-lb-avatar {
    flex: 0 0 34px; width: 34px; height: 34px; border-radius: 50%;
    background: #ED1C24; color: #FFFFFF; font-size: .74rem; font-weight: 800;
    display: flex; align-items: center; justify-content: center; letter-spacing: .02em;
  }
  .aji-lb-info { flex: 1 1 auto; min-width: 0; }
  .aji-lb-name {
    font-size: .86rem; font-weight: 700; color: #1A1A1A;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .aji-lb-bar { height: 5px; border-radius: 3px; background: rgba(26,26,26,0.08); margin-top: 5px; }
  .aji-lb-fill { height: 100%; border-radius: 3px; background: #ED1C24; }
  .aji-lb-value {
    flex: 0 0 auto; text-align: right; font-size: .92rem; font-weight: 800; color: #1A1A1A;
    white-space: nowrap;
  }
  .aji-lb-sub { font-size: .74rem; font-weight: 600; color: #6B6B6B; }
</style>
"""
