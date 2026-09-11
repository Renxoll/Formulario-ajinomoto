"""
Pestaña «Resumen»: KPIs, evolución diaria de canjes, top promotores y
desgloses por dimensión.

Se dibuja llamando a `render(df_f, df_prev, dims)` desde app.py, donde `dims`
son las columnas categóricas detectadas en vivo (data_loader.detect_dimensions).
"""

from __future__ import annotations

import html

import altair as alt
import pandas as pd
import streamlit as st

import config
import data_loader
from theme import ACCENT, GRID, INK_SOFT

PROMOTOR_COLUMN = data_loader.PROMOTOR_COLUMN

# Formato de fecha para ejes/tooltips: sólo día y mes, sin hora (la hora no
# aporta nada en una serie diaria).
FMT_DIA = "%d %b"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
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


def kpis(d: pd.DataFrame, dims: list[str]) -> dict:
    n = len(d)
    canjes = int(d["_canje_bool"].sum()) if "_canje_bool" in d else n
    return {
        "n": n,
        "canjes": canjes,
        "tasa": (canjes / n * 100) if n else 0.0,
        "cant": float(d["Cantidad de Canje"].sum()) if "Cantidad de Canje" in d else 0.0,
        "dims": {dim: d[dim].nunique() for dim in dims if dim in d.columns},
    }


def delta(cur: float, prev: float | None, pp: bool = False) -> str | None:
    if prev is None:
        return None
    d = cur - prev
    return f"{d:+.1f} pp" if pp else f"{d:+,.0f}"


def _etiqueta_dim(dim: str) -> str:
    """Nombre de la tarjeta de KPI para una dimensión: usa config.DIM_DISPLAY_NAMES
    si está definido; si no, pluraliza (fallback para dimensiones nuevas)."""
    if dim in config.DIM_DISPLAY_NAMES:
        return config.DIM_DISPLAY_NAMES[dim]
    vocales = "aeiouáéíóú"
    return dim if dim.endswith(("s", "S")) else dim + ("s" if dim[-1].lower() in vocales else "es")


def _iniciales(nombre: str) -> str:
    partes = [p for p in str(nombre).replace("@", " ").split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


def _leaderboard(df: pd.DataFrame, top: int = 8) -> None:
    """Ranking «Top promotores» con avatar de iniciales y barra de progreso."""
    lb = data_loader.breakdown(df, PROMOTOR_COLUMN).sort_values("Cantidad", ascending=False).head(top)
    if lb.empty:
        st.info(f"Sin datos de «{PROMOTOR_COLUMN}».")
        return

    max_v = lb["Cantidad"].max() or 1
    filas = []
    for i, r in enumerate(lb.itertuples(index=False), start=1):
        nombre = str(getattr(r, PROMOTOR_COLUMN))
        pct = max(4, round(100 * r.Cantidad / max_v))  # mínimo visible aunque sea chico
        filas.append(
            f"""<div class="aji-lb-row">
                <div class="aji-lb-rank">{i}</div>
                <div class="aji-lb-avatar">{html.escape(_iniciales(nombre))}</div>
                <div class="aji-lb-info">
                    <div class="aji-lb-name">{html.escape(nombre)}</div>
                    <div class="aji-lb-bar"><div class="aji-lb-fill" style="width:{pct}%"></div></div>
                </div>
                <div class="aji-lb-value">{r.Cantidad:,.0f}
                    <div class="aji-lb-sub">{r.Registros:,.0f} resp.</div>
                </div>
            </div>"""
        )
    st.markdown(f"<div class='aji-lb'>{''.join(filas)}</div>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(df_f: pd.DataFrame, df_prev: pd.DataFrame | None, dims: list[str]) -> None:
    k = kpis(df_f, dims)
    kp = kpis(df_prev, dims) if df_prev is not None and len(df_prev) else None

    # "Respuestas" no se muestra: hoy coincide siempre con "Canjes realizados"
    # (todas las respuestas registran un canje), así que es redundante.
    # "Canjes efectivos" es la SUMA de "Cantidad de Canje" (una persona puede
    # canjear 2, 3…), a diferencia de "Canjes realizados" que cuenta filas.
    items = [
        ("Canjes realizados", f"{k['canjes']:,}", delta(k["canjes"], kp["canjes"] if kp else None)),
        ("Tasa de canje", f"{k['tasa']:.0f}%", delta(k["tasa"], kp["tasa"] if kp else None, pp=True)),
        ("Canjes efectivos", f"{k['cant']:,.0f}", delta(k["cant"], kp["cant"] if kp else None)),
    ]
    for dim, cnt in k["dims"].items():
        items.append((_etiqueta_dim(dim), f"{cnt}", None))

    for col, (label, value, dl) in zip(st.columns(len(items)), items):
        col.metric(label, value, dl)
    if kp:
        st.caption("Los deltas comparan contra el período inmediatamente anterior de igual duración.")

    st.divider()

    # --- Evolución temporal ------------------------------------------------ #
    serie = data_loader.daily_canjes(df_f)
    st.subheader("📆 Evolución diaria de canjes")
    if serie.empty:
        st.info("Sin fechas válidas para graficar con los filtros actuales.")
    else:
        tooltip_evolucion = [
            alt.Tooltip("Fecha:T", title="Fecha", format=FMT_DIA),
            alt.Tooltip("Canjes:Q", title="Canjes", format="d"),
            alt.Tooltip("Media7:Q", title="Media 7d", format=".1f"),
        ]
        barras = alt.Chart(serie).mark_bar(color=ACCENT, opacity=0.35, size=16).encode(
            x=alt.X("Fecha:T", title=None, axis=alt.Axis(format=FMT_DIA)),
            y=alt.Y("Canjes:Q", title="Canjes por día", axis=alt.Axis(format="d", tickMinStep=1)),
            tooltip=tooltip_evolucion,
        )
        # Etiqueta con el valor entero encima de cada barra (sin decimales:
        # son conteos). Se omite en los días sin canjes para no ensuciar el
        # gráfico con ceros.
        etiquetas = alt.Chart(serie[serie["Canjes"] > 0]).mark_text(
            dy=-10, color=ACCENT, fontWeight="bold", fontSize=11
        ).encode(
            x=alt.X("Fecha:T"),
            y=alt.Y("Canjes:Q"),
            text=alt.Text("Canjes:Q", format="d"),
            tooltip=tooltip_evolucion,
        )
        linea = alt.Chart(serie).mark_line(color=ACCENT, strokeWidth=2.5).encode(
            x="Fecha:T", y="Media7:Q"
        )
        st.altair_chart(style_chart(barras + etiquetas + linea, 300), width="stretch")
        st.caption("Barras = canjes por día (con el valor arriba) · línea = media móvil de 7 días.")

        g1, g2 = st.columns(2)
        with g1:
            st.markdown("**Cantidad de canje acumulada**")
            area = alt.Chart(serie).mark_area(
                color=ACCENT, opacity=0.18, line={"color": ACCENT, "strokeWidth": 2}
            ).encode(
                x=alt.X("Fecha:T", title=None, axis=alt.Axis(format=FMT_DIA)),
                y=alt.Y("Acumulado:Q", title="Acumulado", axis=alt.Axis(format="d")),
                tooltip=[
                    alt.Tooltip("Fecha:T", title="Fecha", format=FMT_DIA),
                    alt.Tooltip("Acumulado:Q", title="Acumulado", format=",.0f"),
                ],
            )
            st.altair_chart(style_chart(area, 260), width="stretch")
        with g2:
            st.markdown("**Distribución de la cantidad por registro**")
            if "Cantidad de Canje" in df_f and df_f["Cantidad de Canje"].notna().any():
                hist = alt.Chart(df_f.dropna(subset=["Cantidad de Canje"])).mark_bar(
                    color=ACCENT, opacity=0.8
                ).encode(
                    x=alt.X("Cantidad de Canje:Q", bin=alt.Bin(maxbins=20), title="Cantidad de canje"),
                    y=alt.Y("count():Q", title="Registros", axis=alt.Axis(format="d", tickMinStep=1)),
                    tooltip=[alt.Tooltip("count():Q", title="Registros", format="d")],
                )
                st.altair_chart(style_chart(hist, 260), width="stretch")
            else:
                st.info("Sin datos de «Cantidad de Canje».")

    # --- Top promotores ---------------------------------------------------- #
    if PROMOTOR_COLUMN in df_f.columns:
        st.divider()
        st.subheader("🏅 Top promotores")
        st.caption(
            "Nombre normalizado a partir de «Usuario (Gmail)» (ver config.USUARIO_ALIASES "
            "para fusionar variantes de un mismo nombre)."
        )
        _leaderboard(df_f)

    # --- Desgloses por dimensión ---------------------------------------- #
    # "Promotor" ya se ve en el ranking de arriba; el resto de las
    # dimensiones detectadas se desglosan acá (adaptativo: si el Form agrega
    # o saca una pregunta tipo dropdown/radio, aparece o desaparece solo).
    dims_desglose = [d for d in dims if d != PROMOTOR_COLUMN]
    if dims_desglose:
        st.divider()
        st.subheader("🧭 Desglose")

        def bar_dim(dim: str, value: str = "Registros"):
            bd = data_loader.breakdown(df_f, dim)
            if bd.empty:
                st.info(f"Sin datos de «{dim}».")
                return
            base = alt.Chart(bd).encode(
                # labelLimit alto para que no corte nombres largos de mercado
                # (p. ej. "Huáscar / Valle Sagrado").
                y=alt.Y(f"{dim}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=280)),
                x=alt.X(f"{value}:Q", title=value, axis=alt.Axis(format="d", tickMinStep=1)),
            )
            bars = base.mark_bar(color=ACCENT, cornerRadius=3)
            labels = base.mark_text(align="left", dx=4, color=INK_SOFT, fontWeight="bold").encode(
                text=alt.Text(f"{value}:Q", format="d")
            )
            st.altair_chart(
                style_chart(bars + labels, max(140, 34 * len(bd))), width="stretch"
            )

        for col, dim in zip(st.columns(len(dims_desglose)), dims_desglose):
            with col:
                st.markdown(f"**Por {dim.lower()}**")
                bar_dim(dim)
