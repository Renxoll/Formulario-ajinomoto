"""
Dashboard "Formulario Ajinomoto" + lanzador de la carga automática a Google Forms.

Fuente única de datos: el Google Sheet vinculado al Google Form.
  - El dashboard lo lee para analizar.
  - La automatización itera esas mismas filas (ya filtradas) para cargarlas
    al Google Form.

app.py es sólo el armazón: página, estilos, carga de datos, filtros del
sidebar y las tres pestañas. Cada pestaña vive en su propio módulo:
  - tab_resumen.py  -> "📈 Resumen"
  - tab_detalle.py  -> "🗂️ Detalle"
  - tab_carga.py    -> "🤖 Carga al Form"

Ejecutar:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import config
import data_loader
import tab_carga
import tab_detalle
import tab_resumen
import theme

# --------------------------------------------------------------------------- #
# Página + estilos (identidad Ajinomoto: rojo #ED1C24 sobre blanco)
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Dashboard Formulario Ajinomoto",
    page_icon="🍜",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(theme.CSS, unsafe_allow_html=True)

# Logo Ajinomoto en la esquina de la app (arriba a la izquierda, sobre el sidebar).
_LOGO = Path(__file__).with_name("ajinomoto_logo.svg")
if _LOGO.exists():
    st.logo(str(_LOGO), size="large", link="https://www.ajinomoto.com")


# --------------------------------------------------------------------------- #
# Datos
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=config.DASHBOARD_CACHE_TTL_S, show_spinner="Leyendo Google Sheet …")
def cargar() -> pd.DataFrame:
    return data_loader.load_responses()


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
st.markdown("<div class='aji-rule'></div>", unsafe_allow_html=True)

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

# --------------------------------------------------------------------------- #
# Pestañas — cada una en su módulo
# --------------------------------------------------------------------------- #
t_resumen, t_detalle, t_carga = st.tabs(["📈 Resumen", "🗂️ Detalle", "🤖 Carga al Form"])

with t_resumen:
    tab_resumen.render(df_f, df_prev)

with t_detalle:
    tab_detalle.render(df_f)

with t_carga:
    tab_carga.render(df_f)
