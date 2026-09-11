"""
Pestaña «Detalle»: tabla de respuestas filtradas, buscador y descarga CSV.

Se dibuja llamando a `render(df_f)` desde app.py.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import config
import data_loader


def _orden_columnas(cols: list[str]) -> list[str]:
    """"Promotor" (nombre prolijo) va justo al lado de "Usuario (Gmail)" (el dato crudo)."""
    promotor = data_loader.PROMOTOR_COLUMN
    usuario = data_loader.USUARIO_COLUMN
    if promotor not in cols or usuario not in cols:
        return cols
    cols = [c for c in cols if c != promotor]
    i = cols.index(usuario)
    return cols[: i + 1] + [promotor] + cols[i + 1 :]


def render(df_f: pd.DataFrame) -> None:
    st.subheader("Respuestas filtradas")
    cols_visibles = _orden_columnas([c for c in df_f.columns if not c.startswith("_")])
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
        file_name="formulario_ajinomoto.csv",
        mime="text/csv",
    )
