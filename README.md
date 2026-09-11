# Dashboard Formulario Ajinomoto + Carga automática a Google Forms

Aplicación local (Streamlit) que:

1. Muestra un **dashboard analítico** (KPIs con comparación de período, evolución
   diaria, media móvil, acumulado, distribución y desgloses) leyendo **en vivo el
   Google Sheet vinculado al Google Form**.
2. Permite lanzar una **automatización con Playwright** que rellena el Google Form
   iterando sobre **esas mismas filas** (ya filtradas), incluida la subida de la
   foto.
3. Al enviarse cada respuesta, el propio Form la vuelca de nuevo en el Sheet, así
   que el dashboard la muestra al pulsar **🔄 Actualizar**.

**Fuente única de datos:** el Google Sheet. No se usa ningún Excel local.

---

## Estructura del proyecto

```
juanpablo-dashboard/
├── app.py               # Armazón: página, estilos, carga de datos, filtros del sidebar
├── tab_resumen.py        # Pestaña "📈 Resumen": KPIs, evolución, desgloses
├── tab_detalle.py        # Pestaña "🗂️ Detalle": tabla filtrable + descarga CSV
├── tab_carga.py           # Pestaña "🤖 Carga al Form": lanza automator.py
├── theme.py              # Paleta e identidad visual (Ajinomoto) compartida por las pestañas
├── automator.py          # Automatización Playwright (importable y como CLI)
├── data_loader.py        # load_responses() (Sheet) + helpers de filtros/series/desgloses
├── config.py              # TODO lo configurable: Sheet, URL del Form, mapeo de campos
├── ajinomoto_logo.svg
├── requirements.txt
├── README.md
├── .gitignore
├── scripts/
│   └── generar_datos_ejemplo.py   # CSV de ejemplo para desarrollar sin conexión
├── data/                          # respuestas_ejemplo.csv (opcional, no versionado)
├── fotos/                         # imágenes referenciadas en la columna "Cargue foto"
├── .pw-user-data/                 # perfil de Chromium con la sesión de Google (se crea solo)
└── .runtime/                      # payload temporal dashboard → automator (se crea solo)
```

---

## Instalación

Requiere **Python 3.11 – 3.14**.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

> En Python 3.13/3.14 hace falta `altair >= 6` (ya está en `requirements.txt`);
> `altair 5.x` no importa en esas versiones. Probado con Python 3.14 +
> Streamlit 1.63 + Altair 6.2.

---

## Configuración (`config.py`)

### Dashboard — lectura del Google Sheet

Ya viene configurado con el Sheet
(`RESPONSES_SHEET_ID = "1q8RWCv2REfFn-rKeKlPSJ7odWFBYzBOKV7xRiSX63Yo"`), compartido
como **"Cualquiera con el enlace: Lector"**. La lectura usa la URL
`gviz/tq?tqx=out:csv` (verificada que funciona con ese modo de compartir).

| Qué | Dónde | Nota |
|---|---|---|
| ID del Google Sheet | `RESPONSES_SHEET_ID` | En la URL: `.../spreadsheets/d/`**`<ID>`**`/edit`. |
| Pestaña (gid) | `RESPONSES_SHEET_GID` | El `gid=` de la URL (default `0`). |
| Archivo local en vez del Sheet | `RESPONSES_LOCAL_OVERRIDE` | Ruta a un `.csv`/`.xlsx` para trabajar sin conexión. `""` = leer del Sheet. |
| Refresco del cache | `DASHBOARD_CACHE_TTL_S` | Segundos antes de releer el Sheet (default 60). |

> Columnas del Sheet (Form simplificado, ya no pregunta Fecha/Tipo/Zona/Número
> de puesto/Nombre del puesto): `Marca temporal`, `Usuario (Gmail)`, `Mercado`,
> `Canje Realizado`, `Cargue foto`, `Observaciones`, `Cantidad de Canje`.
>
> **Filtros y desgloses son adaptativos**: el sidebar y la pestaña Resumen sólo
> muestran Zona/Tipo si esas columnas existen en el Sheet. Si el Form vuelve a
> preguntarlas, aparecen solas — no hace falta tocar el código.
>
> Notas de robustez (las maneja `data_loader`):
> - Los encabezados vienen con un **espacio al final** → se recortan.
> - Si el Form renombra una pregunta, agregá el par viejo→nuevo en
>   `data_loader.COLUMN_ALIASES` (ya está `Canatidad de Canje` → `Cantidad de Canje`).
> - **"Fecha" no existe en este Sheet**: se deriva de "Marca temporal" (el sello
>   automático del Form) para que el filtro de rango de fechas funcione igual.
> - **"Canje Realizado"** en este Form indica *qué* canje se hizo (no un sí/no):
>   cuenta como canje toda fila con ese campo no vacío.

### Automatización

| Qué | Dónde | Nota |
|---|---|---|
| URL del formulario | `GOOGLE_FORM_URL` | La de **`/viewform`**, no la de edición. **Falta completarla.** |
| Mapeo columnas → preguntas | `FIELD_TITLES` | Texto **exacto** del enunciado (tildes, paréntesis). |
| Tipo de cada pregunta | `FIELD_TYPES` | `text` / `date` / `radio` / `dropdown` / `file`. |
| Formato de fecha del Form | `FORM_DATE_FORMAT` | `"iso"` (`2026-09-05`) o `"dmy"` (`05/09/2026`). |
| Ver navegador / velocidad | `HEADLESS`, `SLOW_MO_MS` | Dejá `HEADLESS=False` al principio. |

### Columna "Cargue foto"

Para que la automatización suba la imagen necesita un **archivo local**. El valor
de la celda puede ser:

- Ruta absoluta: `/Users/tu_usuario/fotos/puesto_12.jpg`
- Ruta relativa al proyecto: `fotos/puesto_12.jpg`
- Sólo el nombre: `puesto_12.jpg` → se busca dentro de `fotos/` (`PHOTO_BASE_DIR`)

Una **URL de Google Drive no sirve** para subir (el dashboard igual la muestra
como enlace en la pestaña *Detalle*).

---

## Uso

```bash
streamlit run app.py
```

### Pestaña 📈 Resumen
KPIs con delta vs. período anterior de igual duración, evolución diaria (barras +
media móvil 7d), cantidad acumulada, histograma de cantidad por registro y
desgloses por zona / mercado / tipo.

### Pestaña 🗂️ Detalle
Tabla filtrable con buscador de texto libre, formato de fechas y descarga a CSV.

### Pestaña 🤖 Carga al Form
1. Ajustá los filtros del sidebar: se cargan **exactamente esas filas**.
2. Dejá activado **"Modo prueba (sólo 1 fila)"** la primera vez.
3. **🚀 Iniciar Carga a Google Forms** → se abre el navegador; la primera vez,
   iniciá sesión en Google.
4. Seguí el log en vivo. Cuando la prueba salga bien, desactivá el modo prueba.
5. Al terminar, **🔄 Actualizar** para ver las nuevas respuestas en el dashboard.

Sin dashboard:

```bash
python automator.py --input .runtime/payload.pkl --limit 1
```

### Desarrollo sin conexión

```bash
python scripts/generar_datos_ejemplo.py
# luego en config.py:  RESPONSES_LOCAL_OVERRIDE = "data/respuestas_ejemplo.csv"
```

---

## Selectores de Google Forms

Google Forms **no** usa `id`/`name` estables. `automator.py`:

1. Localiza el contenedor de cada pregunta: `div[role="listitem"]` que **contiene
   el texto del enunciado**.
2. Dentro, busca el control:
   - Texto: `input[type="text"]`, `textarea`
   - Fecha: `input[type="date"]` (o inputs `Día`/`Mes`/`Año`)
   - Opción única: `div[role="radio"][aria-label="..."]`
   - Desplegable: `div[role="listbox"]` → abre → `div[role="option"]`
   - Archivo: botón *"Agregar archivo"* → iframe del *picker* de Drive →
     `input[type="file"]` (oculto) → `set_input_files(...)`

Puntos frágiles marcados con `# TODO:` en el código. Para inspeccionar: abrí el
Form en Chrome → clic derecho sobre el campo → *Inspeccionar*. Útil:

```bash
playwright codegen "https://docs.google.com/forms/d/e/XXXX/viewform"
```

---

## Requisitos de la subida de foto

- El campo *"Cargue foto"* sube a **Google Drive** → **hace falta sesión de Google
  iniciada**. Se usa un contexto persistente (`.pw-user-data/`): te logueás una
  vez y queda guardado.
- Máx. 10 MB por archivo (límite del formulario).

---

## Problemas frecuentes

| Síntoma | Causa probable / solución |
|---|---|
| `No se pudo leer el Google Sheet` | ID/gid mal, o el Sheet dejó de estar compartido por enlace. Verificá `RESPONSES_SHEET_ID` y el modo de compartir. |
| `El Google Sheet respondió con contenido inesperado (¿pide iniciar sesión?)` | El Sheet es privado. Compartilo como "Cualquiera con el enlace: Lector" o usá `RESPONSES_LOCAL_OVERRIDE`. |
| El dashboard no muestra respuestas nuevas | 1) Cache (60 s). Pulsá **🔄 Actualizar**. 2) Revisá el **rango de fechas** del sidebar: si lo achicaste, filas fuera del rango no aparecen (las que no tienen fecha propia usan la de "Marca temporal"). |
| Los KPIs de cantidad dan 0 / falta una columna | El Form renombró la pregunta. Agregá el par viejo→nuevo en `data_loader.COLUMN_ALIASES`. |
| Botón de carga deshabilitado | Falta `GOOGLE_FORM_URL`, o los filtros dejaron 0 filas. |
| `No existe la imagen: …` | La columna «Cargue foto» no apunta a un archivo local (¿es una URL de Drive?). |
| `Opción 'X' no encontrada en dropdown` | El valor del Sheet no coincide con la opción del Form. Revisá mayúsculas/tildes/espacios. |
| `No encontré el iframe del selector de archivos` | Cambió el `src` del iframe del picker. Ajustá el selector en `FormFiller.upload_file`. |
| Se queda en `accounts.google.com` | No hay sesión. Logueate en la ventana; se reintenta 60 s. |
| `Campo obligatorio vacío` | Falta un dato en una columna no listada en `OPTIONAL_FIELDS`. |
| El form es multipágina | Añadí el manejo del botón *"Siguiente"* en `_submit_and_reset()`. |
