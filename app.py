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

import time
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


# Auto-actualización: cada TTL segundos fuerza un rerun completo de la app,
# así las respuestas nuevas del Sheet (filas, mercados, promotores nuevos…)
# entran solas, sin que alguien tenga que tocar el botón ni el código.
#
# `run_every` hace que Streamlit re-ejecute este fragmento cada TTL segundos,
# PERO la primera ejecución ocurre igual, en el momento (síncrono) en que el
# script llega a este punto. Si llamáramos a st.rerun() sin condición, ese
# primer llamado dispararía un rerun completo de inmediato, que al volver a
# ejecutar el script llegaría de nuevo acá y volvería a hacer rerun — un
# bucle infinito que nunca termina de dibujar la página. Por eso se guarda en
# session_state cuándo fue el último rerun real y sólo se dispara uno nuevo
# si ya pasó el intervalo completo.
_AUTO_REFRESH_KEY = "_last_auto_refresh_ts"


@st.fragment(run_every=f"{config.DASHBOARD_CACHE_TTL_S}s")
def _auto_refresh_tick() -> None:
    now = time.monotonic()
    last = st.session_state.setdefault(_AUTO_REFRESH_KEY, now)
    if now - last >= config.DASHBOARD_CACHE_TTL_S:
        st.session_state[_AUTO_REFRESH_KEY] = now
        st.rerun()


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
h_izq, h_der = st.columns([5, 2], vertical_alignment="center")
with h_izq:
    st.title("Formulario Ajinomoto")
    st.caption("Análisis de canjes en vivo desde el Google Sheet + carga automatizada al Form.")
with h_der:
    bc1, bc2 = st.columns([3, 2])
    with bc1:
        if st.button("🔄 Actualizar", width="stretch"):
            cargar.clear()
            st.rerun()
    with bc2:
        auto_refresh = st.toggle(
            "Auto", value=True,
            help=f"Vuelve a leer el Sheet solo cada {config.DASHBOARD_CACHE_TTL_S}s.",
        )
    st.markdown(
        f"<div style='text-align:right'><span class='chip'>Actualizado "
        f"{datetime.now():%H:%M:%S}</span></div>",
        unsafe_allow_html=True,
    )
st.markdown("<div class='aji-rule'></div>", unsafe_allow_html=True)

if auto_refresh:
    _auto_refresh_tick()

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

# Filtros de dimensión: se DETECTAN, no están hardcodeados. Cualquier columna
# de texto con pocos valores distintos aparece sola como filtro — si el Form
# agrega o saca una pregunta, el sidebar se adapta sin tocar código.
dims_presentes = data_loader.detect_dimensions(df)

if st.sidebar.button("Limpiar filtros", width="stretch"):
    for d in dims_presentes:
        st.session_state.pop(f"filtro::{d}", None)
    st.session_state.pop("f_fechas", None)
    st.rerun()

seleccion: dict[str, list[str]] = {
    dim: st.sidebar.multiselect(dim, data_loader.unique_sorted(df[dim]), key=f"filtro::{dim}")
    for dim in dims_presentes
}

# Filtros categóricos aplicados (sin fecha) — base para el período anterior.
df_cat = data_loader.apply_filters(df, filtros=seleccion)

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

n_filtros = sum(bool(v) for v in seleccion.values())
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
    tab_resumen.render(df_f, df_prev, dims_presentes)

with t_detalle:
    tab_detalle.render(df_f)

with t_carga:
    tab_carga.render(df_f)
