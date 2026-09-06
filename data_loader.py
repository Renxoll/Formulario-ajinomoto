"""
Carga y limpieza de datos.

Fuente ÚNICA: el Google Sheet vinculado al Google Form (load_responses()).
El mismo DataFrame alimenta el dashboard y, ya filtrado, la automatización.

_finalize() hace el tipado común (fechas, numéricos, booleano de canje,
limpieza de categóricas) para que KPIs, filtros y gráficos sean uniformes.
"""

from __future__ import annotations

import pandas as pd

import config

# Columnas mínimas que esperamos encontrar.
EXPECTED_COLUMNS = list(config.FIELD_TITLES.keys())


class DataLoadError(Exception):
    """Error controlado al leer o validar los datos."""


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Quita espacios sobrantes en los nombres de columna."""
    return df.rename(columns=lambda c: str(c).strip())


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tipado y columnas auxiliares comunes a ambas fuentes:

    - Normaliza nombres de columnas.
    - Marca 'missing_columns' (aviso, no error).
    - "Fecha" y las columnas de timestamp del Form -> datetime.
    - "Canatidad de Canje" -> numérico.
    - "Canje Realizado" -> booleano auxiliar "_canje_bool".
    - Limpia strings de las categóricas usadas en filtros.
    """
    df = _normalize_columns(df)

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        df.attrs["missing_columns"] = missing

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(
            df["Fecha"], errors="coerce", dayfirst=config.DATE_DAYFIRST
        )

    # Columnas automáticas del Form (marca temporal): útiles como eje temporal
    # alternativo, pero no son preguntas.
    for col in config.TIMESTAMP_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=False)

    if "Canatidad de Canje" in df.columns:
        df["Canatidad de Canje"] = pd.to_numeric(
            df["Canatidad de Canje"], errors="coerce"
        )

    if "Canje Realizado" in df.columns:
        df["_canje_bool"] = (
            df["Canje Realizado"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"sí", "si", "s", "true", "1", "yes", "y", "verdadero"})
        )

    for col in ("Zona", "Mercado", "Tipo"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    return df


def load_responses() -> pd.DataFrame:
    """
    Lee las respuestas del Google Form desde el Google Sheet vinculado.

    Usa config.RESPONSES_CSV_URL (endpoint gviz), que funciona sin credenciales
    si el Sheet está compartido como "Cualquiera con el enlace: Lector".
    Si config.RESPONSES_LOCAL_OVERRIDE apunta a un archivo local, usa ese.
    """
    source = config.RESPONSES_LOCAL_OVERRIDE or config.RESPONSES_CSV_URL

    if not config.RESPONSES_LOCAL_OVERRIDE and "X" * 6 in config.RESPONSES_SHEET_ID:
        raise DataLoadError(
            "Falta configurar el Google Sheet.\n"
            "Editá RESPONSES_SHEET_ID (y RESPONSES_SHEET_GID) en config.py con "
            "los valores de la URL del Sheet:\n"
            "  https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>"
        )

    try:
        if str(source).lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(source, engine="openpyxl")
        else:
            # pandas descarga la URL con urllib; no hace falta 'requests'.
            df = pd.read_csv(source)
    except Exception as exc:  # noqa: BLE001
        raise DataLoadError(
            "No se pudo leer el Google Sheet de respuestas.\n"
            f"Fuente: {source}\n"
            f"Detalle: {exc}\n\n"
            "Verificá que:\n"
            "  1. RESPONSES_SHEET_ID / RESPONSES_SHEET_GID sean correctos.\n"
            "  2. El Sheet esté compartido como 'Cualquiera con el enlace: Lector'\n"
            "     (o publicado en la web)."
        ) from exc

    # Si el Sheet pide login, Google devuelve una página HTML y pandas la lee
    # como una sola columna rara.
    if df.shape[1] < 2 and "docs.google.com" in str(source):
        raise DataLoadError(
            "El Google Sheet respondió con contenido inesperado (¿pide iniciar "
            "sesión?).\nCompartilo como 'Cualquiera con el enlace: Lector'."
        )

    if df.empty:
        # No es un error: todavía no hay respuestas cargadas.
        df.attrs["empty_source"] = True

    return _finalize(df)


# Alias retrocompatible.
load_dataframe = load_responses
load_data = load_responses


def unique_sorted(series: pd.Series) -> list:
    """Valores únicos, sin nulos, ordenados; útil para poblar los filtros."""
    return sorted(series.dropna().unique().tolist())


def apply_filters(
    df: pd.DataFrame,
    zonas: list[str] | None = None,
    mercados: list[str] | None = None,
    tipos: list[str] | None = None,
    fecha_desde=None,
    fecha_hasta=None,
) -> pd.DataFrame:
    """Devuelve una copia del DataFrame aplicando los filtros del sidebar."""
    out = df

    if zonas:
        out = out[out["Zona"].isin(zonas)]
    if mercados:
        out = out[out["Mercado"].isin(mercados)]
    if tipos:
        out = out[out["Tipo"].isin(tipos)]

    if fecha_desde is not None and "Fecha" in out.columns:
        out = out[out["Fecha"] >= pd.Timestamp(fecha_desde)]
    if fecha_hasta is not None and "Fecha" in out.columns:
        out = out[out["Fecha"] <= pd.Timestamp(fecha_hasta)]

    return out.copy()


def daily_canjes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Serie diaria para los gráficos temporales.

    Devuelve columnas: Fecha | Canjes | Cantidad | Media7 | Acumulado
      - Canjes:    nº de registros con canje realizado ese día
      - Cantidad:  suma de "Canatidad de Canje" ese día
      - Media7:    media móvil de 7 días de Canjes
      - Acumulado: suma acumulada de Cantidad
    Rellena los días sin registros con 0 (para que la línea no "salte").
    """
    cols = ["Fecha", "Canjes", "Cantidad", "Media7", "Acumulado"]
    if "Fecha" not in df.columns or df["Fecha"].isna().all():
        return pd.DataFrame(columns=cols)

    base = df.dropna(subset=["Fecha"]).copy()
    base["Fecha"] = base["Fecha"].dt.normalize()

    if "_canje_bool" in base.columns:
        base["_c"] = base["_canje_bool"].astype(int)
    else:
        base["_c"] = 1  # sin la columna, cada fila cuenta como un canje
    canjes = base.groupby("Fecha")["_c"].sum().rename("Canjes")
    cantidad = (
        base.groupby("Fecha")["Canatidad de Canje"].sum().rename("Cantidad")
        if "Canatidad de Canje" in base.columns
        else pd.Series(0.0, index=canjes.index, name="Cantidad")
    )

    out = pd.concat([canjes, cantidad], axis=1).fillna(0)
    # Rango completo de fechas, sin huecos.
    full_idx = pd.date_range(out.index.min(), out.index.max(), freq="D")
    out = out.reindex(full_idx, fill_value=0)
    out.index.name = "Fecha"

    out["Media7"] = out["Canjes"].rolling(7, min_periods=1).mean()
    out["Acumulado"] = out["Cantidad"].cumsum()
    return out.reset_index()[cols]


def breakdown(df: pd.DataFrame, dim: str) -> pd.DataFrame:
    """Agrega por una dimensión ('Zona'/'Mercado'/'Tipo'): Registros, Canjes, Cantidad."""
    if dim not in df.columns or df.empty:
        return pd.DataFrame(columns=[dim, "Registros", "Canjes", "Cantidad"])

    g = df.groupby(dim, dropna=True)
    out = pd.DataFrame(
        {
            "Registros": g.size(),
            "Canjes": g["_canje_bool"].sum() if "_canje_bool" in df else g.size(),
            "Cantidad": (
                g["Canatidad de Canje"].sum()
                if "Canatidad de Canje" in df
                else 0
            ),
        }
    ).reset_index()
    return out.sort_values("Registros", ascending=False)


def slice_period(df: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    """Filas cuya 'Fecha' cae en [desde, hasta] (fechas date, inclusivo)."""
    if "Fecha" not in df.columns or desde is None or hasta is None:
        return df
    f = df["Fecha"].dt.date
    return df[(f >= desde) & (f <= hasta)].copy()
