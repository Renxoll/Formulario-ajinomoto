"""
Pestaña «Detalle»: tabla de respuestas filtradas, buscador y descarga CSV.

Se dibuja llamando a `render(df_f)` desde app.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config


def render(df_f: pd.DataFrame) -> None:
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

    # Sólo para MOSTRAR: si varias filas seguidas son del mismo día, no se
    # repite la fecha — se deja en blanco salvo en la primera de cada grupo
    # (las filas ya vienen en el orden en que se enviaron, así que los mismos
    # días quedan juntos). El CSV que se descarga sí lleva la fecha completa
    # en cada fila.
    view_mostrar = view.copy()
    if "Fecha" in view_mostrar.columns:
        fecha = view_mostrar["Fecha"]
        repetida = fecha.notna() & fecha.eq(fecha.shift(1))
        view_mostrar.loc[repetida, "Fecha"] = pd.NaT

    st.dataframe(
        view_mostrar, width="stretch", hide_index=True, column_config=colcfg, height=460
    )
    st.caption(f"{len(view):,} fila(s) mostradas.")
    st.download_button(
        "⬇️ Descargar CSV",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="formulario_ajinomoto.csv",
        mime="text/csv",
    )
