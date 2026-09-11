"""
Pestaña «Resumen»: KPIs, evolución diaria de canjes y desgloses por dimensión.

Se dibuja llamando a `render(df_f, df_prev, dims)` desde app.py, donde `dims`
son las columnas categóricas detectadas en vivo (data_loader.detect_dimensions).
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import config
import data_loader
from theme import ACCENT, GRID, INK_SOFT

# Formato de fecha para ejes/tooltips: sólo día y mes, sin hora (la hora no
# aporta nada en una serie diaria).
FMT_DIA = "%d %b"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _configure(ch):
    """Estética común: sin marco, ejes tenues, grilla suave sólo en Y."""
    return (
        ch.configure_view(strokeWidth=0)
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


def style_chart(ch: alt.Chart, height: int = 300) -> alt.Chart:
    """`_configure` para un único gráfico (le fija la altura antes)."""
    return _configure(ch.properties(height=height))


def style_concat(ch):
    """`_configure` para gráficos apilados con alt.vconcat (cada panel ya
    trae su propia altura vía .properties())."""
    return _configure(ch)


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


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(df_f: pd.DataFrame, df_prev: pd.DataFrame | None, dims: list[str]) -> None:
    k = kpis(df_f, dims)
    kp = kpis(df_prev, dims) if df_prev is not None and len(df_prev) else None

    # "Respuestas" y "Canjes realizados" no se muestran: cuentan filas, y para
    # el negocio lo que importa es la cantidad efectivamente canjeada
    # ("Canjes efectivos" = suma de "Cantidad de Canje"; una persona puede
    # canjear 2, 3…) y la tasa de canje.
    items = [
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

    # --- Evolución temporal (cantidad por día + acumulado, un solo gráfico) #
    # Las barras grafican "Cantidad" (suma de "Cantidad de Canje", NO cantidad
    # de respuestas) a propósito: así la suma de las barras coincide con el
    # último punto del acumulado de abajo y con el KPI "Canjes efectivos".
    serie = data_loader.daily_canjes(df_f)
    st.subheader("📆 Evolución diaria y acumulada de canjes")
    if serie.empty:
        st.info("Sin fechas válidas para graficar con los filtros actuales.")
    else:
        tooltip_evolucion = [
            alt.Tooltip("Fecha:T", title="Fecha", format=FMT_DIA),
            alt.Tooltip("Cantidad:Q", title="Cantidad de canje", format="d"),
            alt.Tooltip("Canjes:Q", title="Respuestas", format="d"),
            alt.Tooltip("Media7:Q", title="Media 7d", format=".1f"),
        ]
        barras = alt.Chart(serie).mark_bar(color=ACCENT, opacity=0.35, size=16).encode(
            x=alt.X("Fecha:T", title=None, axis=alt.Axis(format=FMT_DIA)),
            y=alt.Y("Cantidad:Q", title="Cantidad de canje por día", axis=alt.Axis(format="d", tickMinStep=1)),
            tooltip=tooltip_evolucion,
        )
        # Etiqueta con el valor entero encima de cada barra (sin decimales:
        # son conteos). Se omite en los días sin canjes para no ensuciar el
        # gráfico con ceros.
        etiquetas = alt.Chart(serie[serie["Cantidad"] > 0]).mark_text(
            dy=-10, color=ACCENT, fontWeight="bold", fontSize=11
        ).encode(
            x=alt.X("Fecha:T"),
            y=alt.Y("Cantidad:Q"),
            text=alt.Text("Cantidad:Q", format="d"),
            tooltip=tooltip_evolucion,
        )
        # Línea de media móvil CON puntos visibles en cada día.
        linea = alt.Chart(serie).mark_line(
            color=ACCENT, strokeWidth=2.5,
            point=alt.OverlayMarkDef(color=ACCENT, size=45, filled=True),
        ).encode(x="Fecha:T", y="Media7:Q", tooltip=tooltip_evolucion)
        panel_canjes = (barras + etiquetas + linea).properties(height=260)

        # Panel de abajo: cantidad acumulada, fusionado con el de arriba en un
        # solo bloque (mismo eje de fechas) en vez de un gráfico aparte — con
        # puntos visibles en cada día, no sólo la línea.
        base_acum = alt.Chart(serie).encode(
            x=alt.X("Fecha:T", title=None, axis=alt.Axis(format=FMT_DIA)),
            y=alt.Y("Acumulado:Q", title="Acumulado", axis=alt.Axis(format="d")),
            tooltip=[
                alt.Tooltip("Fecha:T", title="Fecha", format=FMT_DIA),
                alt.Tooltip("Acumulado:Q", title="Acumulado", format=",.0f"),
            ],
        )
        area_acum = base_acum.mark_area(color=ACCENT, opacity=0.15, line={"color": ACCENT, "strokeWidth": 2})
        puntos_acum = base_acum.mark_point(color=ACCENT, size=45, filled=True)
        panel_acum = (area_acum + puntos_acum).properties(height=160)

        chart = alt.vconcat(panel_canjes, panel_acum, spacing=6).resolve_scale(x="shared")
        st.altair_chart(style_concat(chart), width="stretch")
        st.caption(
            "Arriba: cantidad de canje por día (barras, con el valor arriba) y media móvil de 7 días "
            "(línea con puntos). Abajo: cantidad de canje acumulada en el período — el último punto "
            "coincide con la suma de las barras y con «Canjes efectivos»."
        )

    # --- Desgloses por dimensión ---------------------------------------- #
    # Adaptativo: si el Form agrega o saca una pregunta tipo dropdown/radio,
    # la columna aparece o desaparece sola acá (ver data_loader.detect_dimensions).
    if dims:
        st.divider()
        st.subheader("🧭 Desglose")

        def bar_dim(dim: str, value: str = "Cantidad"):
            # "Cantidad" (suma de "Cantidad de Canje"), no "Registros" (nº de
            # respuestas): así el total de las barras coincide con «Canjes
            # efectivos» y con el gráfico de evolución de arriba.
            bd = data_loader.breakdown(df_f, dim)
            if bd.empty:
                st.info(f"Sin datos de «{dim}».")
                return
            base = alt.Chart(bd).encode(
                # labelLimit alto para que no corte nombres largos de mercado
                # (p. ej. "Huáscar / Valle Sagrado"); labelOverlap=False para
                # que Vega-Lite NO se salte etiquetas cuando "cree" que se
                # van a superponer (con pocas categorías nunca se superponen
                # de verdad, pero por defecto igual oculta algunas).
                y=alt.Y(
                    f"{dim}:N", sort="-x", title=None,
                    axis=alt.Axis(labelLimit=280, labelOverlap=False, labelPadding=6),
                ),
                x=alt.X(f"{value}:Q", title="Cantidad de canje", axis=alt.Axis(format="d", tickMinStep=1)),
                tooltip=[
                    alt.Tooltip(f"{dim}:N", title=dim),
                    alt.Tooltip("Cantidad:Q", title="Cantidad de canje", format="d"),
                    alt.Tooltip("Registros:Q", title="Respuestas", format="d"),
                ],
            )
            bars = base.mark_bar(color=ACCENT, cornerRadius=3)
            labels = base.mark_text(align="left", dx=4, color=INK_SOFT, fontWeight="bold").encode(
                text=alt.Text(f"{value}:Q", format="d")
            )
            st.altair_chart(
                style_chart(bars + labels, max(160, 42 * len(bd))), width="stretch"
            )

        for col, dim in zip(st.columns(len(dims)), dims):
            with col:
                st.markdown(f"**Por {dim.lower()}**")
                bar_dim(dim)
