"""
Configuración central del proyecto.

Fuente ÚNICA de datos: el Google Sheet vinculado al Google Form.
  - El dashboard lo lee para analizar.
  - La automatización itera esas mismas filas (ya filtradas) para cargarlas
    al Google Form.

Aquí se concentra TODO lo que probablemente tengas que ajustar: el Sheet,
la URL del formulario, el mapeo de columnas -> preguntas, el tipo de cada
pregunta y los parámetros del navegador.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PHOTOS_DIR = BASE_DIR / "fotos"
RUNTIME_DIR = BASE_DIR / ".runtime"          # intercambio dashboard <-> automator
BROWSER_PROFILE_DIR = BASE_DIR / ".pw-user-data"  # sesión de Google persistente

# Carpeta base donde se buscan las fotos cuando la columna "Cargue foto" trae
# sólo un nombre de archivo o una ruta relativa (no una ruta absoluta ni URL).
PHOTO_BASE_DIR = PHOTOS_DIR

# --------------------------------------------------------------------------- #
# Fuente de datos: Google Sheet vinculado al Google Form
# --------------------------------------------------------------------------- #
# El ID sale de la URL del Sheet:
#   https://docs.google.com/spreadsheets/d/<ESTO_ES_EL_ID>/edit#gid=<GID>
RESPONSES_SHEET_ID = "1Mpxmkc_9dP5HLIsPG0bWMqmgGmiCejG_MF2YYhGp_d0"
RESPONSES_SHEET_GID = "0"

# URL de lectura como CSV.
#   - gviz/tq  : funciona con "Cualquiera con el enlace: Lector" (es el caso de
#                este Sheet, verificado). ES EL QUE SE USA.
#   - export   : alternativa; a veces requiere permisos más abiertos o publicar.
RESPONSES_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{RESPONSES_SHEET_ID}"
    f"/gviz/tq?tqx=out:csv&gid={RESPONSES_SHEET_GID}"
)
RESPONSES_CSV_URL_ALT = (
    f"https://docs.google.com/spreadsheets/d/{RESPONSES_SHEET_ID}"
    f"/export?format=csv&gid={RESPONSES_SHEET_GID}"
)

# Para trabajar sin conexión: si esto apunta a un archivo local (.csv/.xlsx),
# el dashboard lo usa en lugar del Sheet. Dejar "" para leer del Sheet.
RESPONSES_LOCAL_OVERRIDE = ""

# Cada cuántos segundos se vuelve a leer el Sheet (cache del dashboard).
DASHBOARD_CACHE_TTL_S = 300

# Columnas que el Form agrega solo y que NO son preguntas; se ignoran en KPIs.
TIMESTAMP_COLUMNS = ["Marca temporal", "Timestamp", "Hora de inicio", "Hora de finalización"]

# --------------------------------------------------------------------------- #
# Google Form
# --------------------------------------------------------------------------- #
# TODO: reemplazar por la URL real del formulario (la de "viewform", NO la de edición).
GOOGLE_FORM_URL = "https://docs.google.com/forms/d/e/XXXXXXXXXXXXXXXXXXXXXXXX/viewform"

# --------------------------------------------------------------------------- #
# Parámetros del navegador (Playwright)
# --------------------------------------------------------------------------- #
HEADLESS = False        # False = ver el navegador mientras rellena (recomendado al inicio)
SLOW_MO_MS = 150        # milisegundos de pausa entre acciones, para poder seguir el proceso
NAV_TIMEOUT_MS = 30_000
ACTION_TIMEOUT_MS = 15_000
UPLOAD_TIMEOUT_MS = 90_000   # subir la foto a Google Drive puede tardar
PAUSE_BETWEEN_ROWS_S = 1.5   # respiro entre envíos para no saturar el formulario

# --------------------------------------------------------------------------- #
# Formato de fecha
# --------------------------------------------------------------------------- #
# Cómo se lee la columna "Fecha" del Sheet (día primero, típico en LATAM)
DATE_DAYFIRST = True
# Cómo espera la fecha el widget del Google Form.
#   - "iso"   -> 2026-09-05   (input type=date, la opción más común)
#   - "dmy"   -> 05/09/2026   (algunos formularios con campo de texto)
FORM_DATE_FORMAT = "iso"

# --------------------------------------------------------------------------- #
# Mapeo de columnas del Sheet  ->  título EXACTO de la pregunta en el Form
# --------------------------------------------------------------------------- #
# La clave es el nombre de la columna en el Google Sheet.
# El valor es el texto exacto que aparece como enunciado de la pregunta en el
# Google Form (sin el asterisco rojo de "obligatorio").
#
# TODO: abrir el formulario y verificar que estos textos coinciden carácter por
#       carácter (tildes, mayúsculas, paréntesis, el typo "Canatidad", etc.).
FIELD_TITLES = {
    "Fecha":              "Fecha",
    "Usuario (Gmail)":    "Usuario (Gmail)",
    "Tipo":               "Tipo",
    "Zona":               "Zona",
    "Mercado":            "Mercado",
    "Canje Realizado":    "Canje Realizado",
    "Número de puesto":   "Número de puesto",
    "Nombre del puesto":  "Nombre del puesto",
    "Cargue foto":        "Cargue foto",
    "Observaciones":      "Observaciones",
    "Canatidad de Canje": "Canatidad de Canje",   # (sic) el typo está en el formulario
}

# --------------------------------------------------------------------------- #
# Tipo de control de cada pregunta en el Google Form
# --------------------------------------------------------------------------- #
#   "text"      -> input de una línea o textarea
#   "date"      -> selector de fecha
#   "radio"     -> opción única (círculos)
#   "dropdown"  -> lista desplegable
#   "file"      -> subida de archivo (foto)
#
# TODO: confirmar cada tipo. Por ejemplo, "Tipo"/"Zona"/"Mercado" podrían ser
#       radio en lugar de dropdown según cómo se diseñó el formulario.
FIELD_TYPES = {
    "Fecha":              "date",
    "Usuario (Gmail)":    "text",
    "Tipo":               "dropdown",
    "Zona":               "dropdown",
    "Mercado":            "dropdown",
    "Canje Realizado":    "radio",
    "Número de puesto":   "text",
    "Nombre del puesto":  "text",
    "Cargue foto":        "file",
    "Observaciones":      "text",
    "Canatidad de Canje": "text",
}

# Columnas que, si vienen vacías en la fila, simplemente se saltan.
OPTIONAL_FIELDS = {
    "Número de puesto",
    "Nombre del puesto",
    "Observaciones",
}

# Orden en el que se rellenan las preguntas (útil si el formulario tiene
# validaciones que dependen del orden). Debe contener las mismas claves que arriba.
FIELD_ORDER = [
    "Fecha",
    "Usuario (Gmail)",
    "Tipo",
    "Zona",
    "Mercado",
    "Canje Realizado",
    "Número de puesto",
    "Nombre del puesto",
    "Cargue foto",
    "Observaciones",
    "Canatidad de Canje",
]

# Columna que contiene la ruta / nombre de archivo de la imagen a subir.
# Puede ser: ruta absoluta, ruta relativa al proyecto, o sólo el nombre de
# archivo (se busca dentro de PHOTO_BASE_DIR). Una URL de Drive NO sirve para
# subir; tiene que ser un archivo local.
PHOTO_PATH_COLUMN = "Cargue foto"

# --------------------------------------------------------------------------- #
# Textos de botones del formulario (cambian según el idioma de la cuenta Google)
# --------------------------------------------------------------------------- #
SUBMIT_BUTTON_TEXTS = ["Enviar", "Submit"]
NEXT_BUTTON_TEXTS = ["Siguiente", "Next"]
ANOTHER_RESPONSE_TEXTS = [
    "Enviar otra respuesta",
    "Submit another response",
]
ADD_FILE_BUTTON_TEXTS = ["Agregar archivo", "Añadir archivo", "Add file"]
