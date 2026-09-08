"""
Pestaña «Resumen»: KPIs, evolución diaria de canjes y desgloses por dimensión.

Se dibuja llamando a `render(df_f, df_prev)` desde app.py.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import data_loader
from theme import ACCENT, GRID, INK_SOFT


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
# Render
# --------------------------------------------------------------------------- #
def render(df_f: pd.DataFrame, df_prev: pd.DataFrame | None) -> None:
    k = kpis(df_f)
    kp = kpis(df_prev) if df_prev is not None and len(df_prev) else None

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
