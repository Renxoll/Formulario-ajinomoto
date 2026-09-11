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

# Columna del Form que puede aparecer con nombres distintos (el typo se corrigió).
QTY_COLUMN = "Cantidad de Canje"

# Renombres de columnas que cambiaron de nombre en el Form/Sheet a lo largo del
# tiempo. Se aplican tras normalizar (quitar espacios).
COLUMN_ALIASES = {
    "Canatidad de Canje": QTY_COLUMN,   # el typo original del Form fue corregido
}

# Valores de "Canje Realizado" que NO cuentan como canje.
_CANJE_NEGATIVOS = {"", "no", "n", "false", "0", "ninguno", "sin canje", "-", "nan"}

USUARIO_COLUMN = "Usuario (Gmail)"
PROMOTOR_COLUMN = "Promotor"


class DataLoadError(Exception):
    """Error controlado al leer o validar los datos."""


def _normalizar_nombre(valor) -> str | None:
    """
    Limpieza puramente visual de "Usuario (Gmail)": recorta espacios repetidos
    y capitaliza (los emails quedan en minúscula). No decide identidad.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = " ".join(str(valor).split())
    if not texto:
        return None
    return texto.lower() if "@" in texto else texto.title()


def _promotor(df: pd.DataFrame) -> pd.Series | None:
    """Columna "Promotor": nombre normalizado + alias configurables (config.USUARIO_ALIASES)."""
    if USUARIO_COLUMN not in df.columns:
        return None
    nombre = df[USUARIO_COLUMN].map(_normalizar_nombre)
    return nombre.map(lambda v: config.USUARIO_ALIASES.get(v, v) if v else v).astype("string")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Quita espacios sobrantes en los nombres de columna y aplica alias."""
    df = df.rename(columns=lambda c: str(c).strip())
    ren = {k: v for k, v in COLUMN_ALIASES.items() if k in df.columns and v not in df.columns}
    return df.rename(columns=ren)


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tipado y columnas auxiliares:

    - Normaliza nombres de columnas (+ alias) y espacios en los valores de texto.
    - Marca 'missing_columns' (aviso, no error).
    - "Marca temporal" -> datetime. "Fecha" -> datetime, y si viene vacía se
      completa con la fecha del envío (Marca temporal) para que la fila no
      desaparezca de filtros ni gráficos.
    - "Cantidad de Canje" -> numérico.
    - "_canje_bool": True si "Canje Realizado" tiene un valor real (no vacío / no
      un "no"). En este Form el campo indica QUÉ canje se hizo, no un sí/no.
    """
    df = _normalize_columns(df)

    # Los encabezados y celdas del Form suelen venir con espacios al final.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        df.attrs["missing_columns"] = missing

    # --- Marca temporal (sello automático del Form: SIEMPRE presente) ------ #
    marca = None
    for col in config.TIMESTAMP_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(
                df[col], errors="coerce", dayfirst=config.DATE_DAYFIRST
            )
            if marca is None:
                marca = df[col]

    # --- Fecha efectiva -------------------------------------------------- #
    # "Fecha" es un campo que el encuestador suele dejar vacío. Se completa con
    # la fecha del envío para no perder esas filas.
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(
            df["Fecha"], errors="coerce", dayfirst=config.DATE_DAYFIRST
        )
        if marca is not None:
            df["Fecha"] = df["Fecha"].fillna(marca.dt.normalize())
    elif marca is not None:
        df["Fecha"] = marca.dt.normalize()

    if QTY_COLUMN in df.columns:
        df[QTY_COLUMN] = pd.to_numeric(df[QTY_COLUMN], errors="coerce")

    if "Canje Realizado" in df.columns:
        s = df["Canje Realizado"].astype("string").str.strip()
        df["_canje_bool"] = s.notna() & ~s.str.lower().isin(_CANJE_NEGATIVOS)

    # Limpia toda columna de texto corto que exista (Zona/Mercado/Tipo hoy;
    # cualquier otra que el Form agregue mañana queda igual de prolija).
    for col in df.columns:
        if col in (USUARIO_COLUMN, "Observaciones") or col.startswith("_"):
            continue
        if df[col].dtype == object or str(df[col].dtype) == "string":
            df[col] = df[col].astype("string").str.strip().replace({"": pd.NA})

    promotor = _promotor(df)
    if promotor is not None:
        df[PROMOTOR_COLUMN] = promotor

    return df


def detect_dimensions(df: pd.DataFrame) -> list[str]:
    """
    Columnas categóricas filtrables/desglosables, detectadas automáticamente
    (texto, con más de 1 y no demasiados valores distintos, que no sean texto
    libre/identificador — ver config.NON_DIM_COLUMNS). Sirve tanto para los
    filtros del sidebar como para el desglose de la pestaña Resumen: si el
    Form agrega o quita una pregunta tipo dropdown/radio, se refleja solo.
    """
    dims = []
    for col in df.columns:
        if col.startswith("_") or col in config.NON_DIM_COLUMNS:
            continue
        if not (df[col].dtype == object or str(df[col].dtype) == "string"):
            continue
        n = df[col].nunique(dropna=True)
        if 1 < n <= config.MAX_DIM_CARDINALITY:
            dims.append(col)
    return dims


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


def apply_filters(df: pd.DataFrame, filtros: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """
    Devuelve una copia del DataFrame quedándose con las filas cuyo valor, en
    cada columna de `filtros`, está entre los seleccionados. `filtros` es
    {columna: [valores]}; una columna con lista vacía no filtra. Genérico a
    propósito: funciona para cualquier dimensión que detect_dimensions() haya
    encontrado, no sólo Zona/Mercado/Tipo.
    """
    out = df
    for col, valores in (filtros or {}).items():
        if valores and col in out.columns:
            out = out[out[col].isin(valores)]
    return out.copy()


def daily_canjes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Serie diaria para los gráficos temporales.

    Devuelve columnas: Fecha | Canjes | Cantidad | Media7 | Acumulado
      - Canjes:    nº de registros con canje realizado ese día
      - Cantidad:  suma de "Cantidad de Canje" ese día
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
        base.groupby("Fecha")[QTY_COLUMN].sum().rename("Cantidad")
        if QTY_COLUMN in base.columns
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
    """Agrega por cualquier columna categórica (ver detect_dimensions): Registros, Canjes, Cantidad."""
    if dim not in df.columns or df.empty:
        return pd.DataFrame(columns=[dim, "Registros", "Canjes", "Cantidad"])

    g = df.groupby(dim, dropna=True)
    out = pd.DataFrame(
        {
            "Registros": g.size(),
            "Canjes": g["_canje_bool"].sum() if "_canje_bool" in df else g.size(),
            "Cantidad": g[QTY_COLUMN].sum() if QTY_COLUMN in df else 0,
        }
    ).reset_index()
    return out.sort_values("Registros", ascending=False)


def slice_period(df: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    """
    Filas cuya 'Fecha' cae en [desde, hasta] (inclusivo).
    Las filas SIN fecha (NaT) se conservan siempre: nunca deben desaparecer
    silenciosamente por el filtro de rango.
    """
    if "Fecha" not in df.columns or desde is None or hasta is None:
        return df
    f = df["Fecha"]
    keep = f.isna() | ((f.dt.date >= desde) & (f.dt.date <= hasta))
    return df[keep].copy()
