"""
Dashboard "Formulario Faurus" + lanzador de la carga automática a Google Forms.

Fuente única de datos: el Google Sheet vinculado al Google Form.
  - El dashboard lo lee para analizar.
  - La automatización itera esas mismas filas (ya filtradas) para cargarlas
    al Google Form.

Ejecutar:
    streamlit run app.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import config
import data_loader

# --------------------------------------------------------------------------- #
# Página + estilos
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Dashboard Formulario Faurus",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta categórica segura para daltonismo (Okabe–Ito).
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442"]
ACCENT = PALETTE[0]
INK_SOFT = "#8a8a8a"
GRID = "rgba(140,140,140,0.16)"

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.1rem; padding-bottom: 3rem; max-width: 1400px; }
      h1, h2, h3 { font-weight: 700; letter-spacing: -0.01em; }
      /* Tarjetas de KPI */
      div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.06);
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 14px;
        padding: 14px 16px 12px;
      }
      div[data-testid="stMetric"] label p { font-size: .80rem; opacity: .70; font-weight: 600; }
      div[data-testid="stMetricValue"] { font-size: 1.55rem; }
      /* Pestañas */
      button[data-baseweb="tab"] { font-weight: 600; }
      /* Chip */
      .chip {
        display:inline-block; padding:2px 10px; border-radius:999px;
        background:rgba(0,114,178,.12); color:#0a7; font-size:.78rem; font-weight:600;
        border:1px solid rgba(0,114,178,.25);
      }
      hr { margin: 1.1rem 0; opacity: .12; }
      section[data-testid="stSidebar"] h1 { font-size: 1.05rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=config.DASHBOARD_CACHE_TTL_S, show_spinner="Leyendo Google Sheet …")
def cargar() -> pd.DataFrame:
    return data_loader.load_responses()


def style_chart(ch: alt.Chart, height: int = 300) -> alt.Chart:
    """Estética común: sin marco, ejes tenues, grilla suave sólo en Y."""
    return (
        ch.properties(height=height)
        .configure_view(strokeWidth=0)
        .configure_axis(
            labelColor=INK_SOFT,
            titleColor=INK_SOFT,
            titleFontWeight="normal",
            domainColor=GRID,
            tickColor=GRID,
            grid=False,
        )
        .configure_axisY(grid=True, gridColor=GRID)
        .configure_legend(labelColor=INK_SOFT, titleColor=INK_SOFT, orient="top")
    )


def kpis(d: pd.DataFrame) -> dict:
    n = len(d)
    canjes = int(d["_canje_bool"].sum()) if "_canje_bool" in d else n
    return {
        "n": n,
        "canjes": canjes,
        "tasa": (canjes / n * 100) if n else 0.0,
        "cant": float(d["Canatidad de Canje"].sum()) if "Canatidad de Canje" in d else 0.0,
        "merc": d["Mercado"].nunique() if "Mercado" in d else 0,
        "zonas": d["Zona"].nunique() if "Zona" in d else 0,
    }


def delta(cur: float, prev: float | None, pp: bool = False) -> str | None:
    if prev is None:
        return None
    d = cur - prev
    return f"{d:+.1f} pp" if pp else f"{d:+,.0f}"


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
h_izq, h_der = st.columns([5, 2], vertical_alignment="center")
with h_izq:
    st.title("Formulario Ajinomoto")
    st.caption("Análisis de canjes en vivo desde el Google Sheet + carga automatizada al Form.")
with h_der:
    if st.button("🔄 Actualizar", width="stretch"):
        cargar.clear()
        st.rerun()
    st.markdown(
        f"<div style='text-align:right'><span class='chip'>Actualizado "
        f"{datetime.now():%H:%M:%S}</span></div>",
        unsafe_allow_html=True,
    )

try:
    df = cargar()
except data_loader.DataLoadError as exc:
    st.error(str(exc))
    st.stop()

if missing := df.attrs.get("missing_columns"):
    st.warning(f"El Sheet no tiene estas columnas esperadas: {', '.join(missing)}")

# --------------------------------------------------------------------------- #
# Sidebar — filtros
# --------------------------------------------------------------------------- #
st.sidebar.title("Filtros")

if st.sidebar.button("Limpiar filtros", width="stretch"):
    for k in ("f_zona", "f_mercado", "f_tipo", "f_fechas"):
        st.session_state.pop(k, None)
    st.rerun()

zonas_sel = st.sidebar.multiselect(
    "Zona", data_loader.unique_sorted(df["Zona"]) if "Zona" in df else [], key="f_zona"
)
mercados_sel = st.sidebar.multiselect(
    "Mercado", data_loader.unique_sorted(df["Mercado"]) if "Mercado" in df else [], key="f_mercado"
)
tipos_sel = st.sidebar.multiselect(
    "Tipo", data_loader.unique_sorted(df["Tipo"]) if "Tipo" in df else [], key="f_tipo"
)

# Filtros categóricos aplicados (sin fecha) — base para el período anterior.
df_cat = data_loader.apply_filters(df, zonas=zonas_sel, mercados=mercados_sel, tipos=tipos_sel)

desde = hasta = None
if "Fecha" in df and df["Fecha"].notna().any():
    fmin, fmax = df["Fecha"].min().date(), df["Fecha"].max().date()
    rango = st.sidebar.date_input(
        "Rango de fechas", value=(fmin, fmax), min_value=fmin, max_value=fmax, key="f_fechas"
    )
    if isinstance(rango, tuple) and len(rango) == 2:
        desde, hasta = rango

df_f = data_loader.slice_period(df_cat, desde, hasta) if desde else df_cat

# Período inmediatamente anterior, de igual longitud (para los deltas).
df_prev = None
if desde and hasta:
    span = hasta - desde
    prev_hasta = desde - timedelta(days=1)
    df_prev = data_loader.slice_period(df_cat, prev_hasta - span, prev_hasta)

n_filtros = sum(bool(x) for x in (zonas_sel, mercados_sel, tipos_sel))
st.sidebar.divider()
st.sidebar.caption(
    f"**{len(df_f):,}** de {len(df):,} respuestas"
    + (f"  ·  {n_filtros} filtro(s) activo(s)" if n_filtros else "")
)
_origen = config.RESPONSES_LOCAL_OVERRIDE or "Google Sheet vinculado al Form"
st.sidebar.caption(f"Fuente: {_origen}")

# --------------------------------------------------------------------------- #
# Estado vacío
# --------------------------------------------------------------------------- #
if df.empty:
    st.info(
        "El Google Sheet todavía no tiene respuestas. En cuanto la automatización "
        "cargue filas al Form aparecerán acá — usá **🔄 Actualizar** para releer."
    )
    st.stop()

tab_resumen, tab_detalle, tab_carga = st.tabs(["📈 Resumen", "🗂️ Detalle", "🤖 Carga al Form"])

# =========================================================================== #
# TAB 1 — RESUMEN
# =========================================================================== #
with tab_resumen:
    k, kp = kpis(df_f), (kpis(df_prev) if df_prev is not None and len(df_prev) else None)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Respuestas", f"{k['n']:,}", delta(k["n"], kp["n"] if kp else None))
    c2.metric("Canjes realizados", f"{k['canjes']:,}", delta(k["canjes"], kp["canjes"] if kp else None))
    c3.metric("Tasa de canje", f"{k['tasa']:.0f}%", delta(k["tasa"], kp["tasa"] if kp else None, pp=True))
    c4.metric("Cantidad total", f"{k['cant']:,.0f}", delta(k["cant"], kp["cant"] if kp else None))
    c5.metric("Mercados / Zonas", f"{k['merc']} / {k['zonas']}")
    if kp:
        st.caption("Los deltas comparan contra el período inmediatamente anterior de igual duración.")

    st.divider()

    # --- Evolución temporal ------------------------------------------------ #
    serie = data_loader.daily_canjes(df_f)
    st.subheader("Evolución diaria de canjes")
    if serie.empty:
        st.info("Sin fechas válidas para graficar con los filtros actuales.")
    else:
        barras = alt.Chart(serie).mark_bar(color=ACCENT, opacity=0.35, size=6).encode(
            x=alt.X("Fecha:T", title=None),
            y=alt.Y("Canjes:Q", title="Canjes por día"),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha"),
                alt.Tooltip("Canjes:Q", title="Canjes"),
                alt.Tooltip("Media7:Q", title="Media 7d", format=".1f"),
            ],
        )
        linea = alt.Chart(serie).mark_line(color=ACCENT, strokeWidth=2.5).encode(
            x="Fecha:T", y="Media7:Q"
        )
        st.altair_chart(style_chart(barras + linea, 300), width="stretch")
        st.caption("Barras = canjes por día · línea = media móvil de 7 días.")

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Cantidad de canje acumulada**")
            area = alt.Chart(serie).mark_area(
                color=ACCENT, opacity=0.18, line={"color": ACCENT, "strokeWidth": 2}
            ).encode(
                x=alt.X("Fecha:T", title=None),
                y=alt.Y("Acumulado:Q", title="Acumulado"),
                tooltip=[alt.Tooltip("Fecha:T"), alt.Tooltip("Acumulado:Q", format=",.0f")],
            )
            st.altair_chart(style_chart(area, 260), width="stretch")
        with g2:
            st.markdown("**Distribución de la cantidad por registro**")
            if "Canatidad de Canje" in df_f and df_f["Canatidad de Canje"].notna().any():
                hist = alt.Chart(df_f.dropna(subset=["Canatidad de Canje"])).mark_bar(
                    color=ACCENT, opacity=0.8
                ).encode(
                    x=alt.X("Canatidad de Canje:Q", bin=alt.Bin(maxbins=20), title="Cantidad de canje"),
                    y=alt.Y("count():Q", title="Registros"),
                    tooltip=[alt.Tooltip("count():Q", title="Registros")],
                )
                st.altair_chart(style_chart(hist, 260), width="stretch")
            else:
                st.info("Sin datos de «Canatidad de Canje».")

    st.divider()

    # --- Desgloses por dimensión ---------------------------------------- #
    st.subheader("Desglose")

    def bar_dim(dim: str, value: str = "Registros"):
        bd = data_loader.breakdown(df_f, dim)
        if bd.empty:
            st.info(f"Sin datos de «{dim}».")
            return
        base = alt.Chart(bd).encode(
            y=alt.Y(f"{dim}:N", sort="-x", title=None),
            x=alt.X(f"{value}:Q", title=value),
        )
        bars = base.mark_bar(color=ACCENT, cornerRadius=3)
        labels = base.mark_text(align="left", dx=4, color=INK_SOFT).encode(text=f"{value}:Q")
        st.altair_chart(
            style_chart(bars + labels, max(140, 34 * len(bd))), width="stretch"
        )

    d1, d2, d3 = st.columns(3)
    with d1:
        st.markdown("**Por zona**")
        bar_dim("Zona")
    with d2:
        st.markdown("**Por mercado**")
        bar_dim("Mercado")
    with d3:
        st.markdown("**Por tipo**")
        bar_dim("Tipo")

# =========================================================================== #
# TAB 2 — DETALLE
# =========================================================================== #
with tab_detalle:
    st.subheader("Respuestas filtradas")
    cols_visibles = [c for c in df_f.columns if not c.startswith("_")]
    view = df_f[cols_visibles]

    q = st.text_input("Buscar", placeholder="Filtra por cualquier texto de la tabla…")
    if q:
        mask = (
            view.astype(str)
            .apply(lambda s: s.str.contains(q, case=False, na=False, regex=False))
            .any(axis=1)
        )
        view = view[mask]

    colcfg: dict = {}
    if "Fecha" in view:
        colcfg["Fecha"] = st.column_config.DateColumn("Fecha", format="DD/MM/YYYY")
    for tcol in config.TIMESTAMP_COLUMNS:
        if tcol in view:
            colcfg[tcol] = st.column_config.DatetimeColumn(tcol, format="DD/MM/YYYY HH:mm")
    if "Cargue foto" in view:
        colcfg["Cargue foto"] = st.column_config.LinkColumn("Cargue foto", display_text="Ver")

    st.dataframe(
        view, width="stretch", hide_index=True, column_config=colcfg, height=460
    )
    st.caption(f"{len(view):,} fila(s) mostradas.")
    st.download_button(
        "⬇️ Descargar CSV",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="formulario_faurus.csv",
        mime="text/csv",
    )

# =========================================================================== #
# TAB 3 — CARGA AL FORM
# =========================================================================== #
with tab_carga:
    st.subheader("Carga automática a Google Forms")

    form_ok = "X" * 6 not in config.GOOGLE_FORM_URL
    if not form_ok:
        st.warning("Configurá `GOOGLE_FORM_URL` en `config.py` con la URL real del formulario (`/viewform`).")

    st.markdown(
        f"""
Se enviará **una respuesta al Google Form por cada una de las
{len(df_f):,} filas filtradas** (las mismas de la pestaña *Detalle*).
Al enviarse, el propio Form las vuelca de nuevo en el Sheet.

- **Fotos:** la columna «Cargue foto» debe apuntar a un **archivo local**
  (ruta absoluta, relativa al proyecto, o sólo el nombre dentro de
  `{config.PHOTO_BASE_DIR.name}/`). Una URL de Drive no sirve para subir.
- La primera vez se abre un navegador para **iniciar sesión en Google**
  (necesario para la subida). La sesión queda guardada.
"""
    )

    cc1, cc2 = st.columns([3, 2])
    with cc1:
        modo_prueba = st.toggle("Modo prueba (sólo 1 fila)", value=True)
    with cc2:
        st.caption("Dejalo activado la primera vez para validar los selectores.")

    with st.expander(f"Ver las {len(df_f):,} filas que se enviarían"):
        _cv = [c for c in df_f.columns if not c.startswith("_")]
        st.dataframe(df_f[_cv], width="stretch", hide_index=True)

    lanzar = st.button(
        "🚀 Iniciar Carga a Google Forms",
        type="primary",
        width="stretch",
        disabled=df_f.empty or not form_ok,
    )

    if lanzar:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        payload = config.RUNTIME_DIR / "payload.pkl"
        df_f.to_pickle(payload)

        cmd = [sys.executable, str(config.BASE_DIR / "automator.py"), "--input", str(payload)]
        if modo_prueba:
            cmd += ["--limit", "1"]

        st.info("Automatización lanzada. Progreso en vivo:")
        log_box = st.empty()
        lineas: list[str] = []

        proc = subprocess.Popen(
            cmd,
            cwd=str(config.BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for linea in proc.stdout:
            lineas.append(linea.rstrip())
            log_box.code("\n".join(lineas[-400:]), language="text")
        codigo = proc.wait()

        if codigo == 0:
            st.success("✅ Carga finalizada sin errores. Pulsá 🔄 Actualizar para ver las respuestas.")
        elif codigo == 1:
            st.warning("⚠️ Finalizó con algunas filas en error (ver log).")
        else:
            st.error(f"❌ La automatización terminó con código {codigo} (ver log).")
