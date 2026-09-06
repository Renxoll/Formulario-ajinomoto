"""
Automatización de carga al Google Form con Playwright (API síncrona).

Uso desde código (por ejemplo, desde el dashboard):

    from automator import run_automation
    resultado = run_automation(df_filtrado, on_log=print)

Uso desde la terminal (el dashboard lo invoca así, en un subproceso):

    python automator.py --input .runtime/payload.pkl

Notas importantes
-----------------
1. El campo "Cargue foto" sube el archivo a Google Drive. Para que funcione,
   el navegador debe tener una sesión de Google iniciada. Por eso usamos un
   contexto PERSISTENTE (launch_persistent_context) apuntando a
   config.BROWSER_PROFILE_DIR: la PRIMERA vez, iniciá sesión manualmente en
   Google en esa ventana; las siguientes ya quedará logueado.

2. Google Forms NO expone "name"/"id" estables en los inputs. La estrategia
   robusta es localizar el CONTENEDOR de cada pregunta (div[role="listitem"])
   por su TEXTO y, dentro de él, buscar el control. Aun así, si rediseñan el
   formulario vas a tener que ajustar los selectores marcados con "TODO".
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd
from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

import config

LogFn = Callable[[str], None]


def _resolve_photo(value: str) -> Path:
    """
    Convierte el valor de la columna "Cargue foto" en una ruta local:
      - ruta absoluta        -> tal cual
      - ruta relativa        -> contra la carpeta del proyecto
      - sólo nombre archivo  -> dentro de config.PHOTO_BASE_DIR
    """
    p = Path(str(value).strip()).expanduser()
    if p.is_absolute():
        return p
    candidato = (config.BASE_DIR / p).resolve()
    if candidato.exists():
        return candidato
    return (config.PHOTO_BASE_DIR / p.name).resolve()


# --------------------------------------------------------------------------- #
# Resultado
# --------------------------------------------------------------------------- #
@dataclass
class RowResult:
    index: int
    ok: bool
    error: str | None = None


@dataclass
class RunResult:
    total: int = 0
    exitosos: int = 0
    fallidos: int = 0
    detalle: list[RowResult] = field(default_factory=list)

    def add(self, r: RowResult) -> None:
        self.detalle.append(r)
        self.total += 1
        if r.ok:
            self.exitosos += 1
        else:
            self.fallidos += 1


# --------------------------------------------------------------------------- #
# Helpers de bajo nivel sobre la página
# --------------------------------------------------------------------------- #
class FormFiller:
    """Encapsula el llenado de UNA respuesta del formulario."""

    def __init__(self, page: Page, log: LogFn) -> None:
        self.page = page
        self.log = log

    # -- localizar el bloque de una pregunta por su enunciado --------------- #
    def question_block(self, title: str) -> Locator:
        """
        Devuelve el contenedor (div[role="listitem"]) que contiene el texto
        del enunciado. Se usa `has_text` con string exacto-ish; si hay varias
        preguntas con texto parecido, afiná el selector.

        TODO: si el formulario tiene secciones/páginas, quizá el listitem no
              esté visible hasta hacer scroll o pasar de página.
        """
        block = (
            self.page.locator('div[role="listitem"]')
            .filter(has_text=title)
            .first
        )
        block.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
        block.scroll_into_view_if_needed()
        return block

    # -- texto / textarea ------------------------------------------------- #
    def fill_text(self, title: str, value: str) -> None:
        block = self.question_block(title)
        # Google Forms usa <input type="text"> para respuesta corta y
        # <textarea> para respuesta larga (p. ej. "Observaciones").
        control = block.locator('input[type="text"], textarea').first
        control.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
        control.click()
        control.fill("")
        control.type(str(value), delay=15)

    # -- fecha ---------------------------------------------------------- #
    def fill_date(self, title: str, value: pd.Timestamp) -> None:
        block = self.question_block(title)
        ts = pd.Timestamp(value)

        # Caso más común: un único <input type="date">.
        date_input = block.locator('input[type="date"]')
        if date_input.count() > 0:
            if config.FORM_DATE_FORMAT == "iso":
                date_input.first.fill(ts.strftime("%Y-%m-%d"))
            else:
                date_input.first.fill(ts.strftime("%d/%m/%Y"))
            return

        # Caso alternativo: inputs separados de día / mes / año.
        # TODO: ajustar los aria-label según el idioma de la cuenta.
        pares = [
            (["Día", "Day"], ts.strftime("%d")),
            (["Mes", "Month"], ts.strftime("%m")),
            (["Año", "Year"], ts.strftime("%Y")),
        ]
        for labels, val in pares:
            for lbl in labels:
                loc = block.locator(f'input[aria-label="{lbl}"]')
                if loc.count() > 0:
                    loc.first.fill(val)
                    break
        else:
            raise RuntimeError(
                f"No pude identificar el control de fecha en '{title}'. "
                f"Inspeccioná el HTML y ajustá fill_date()."
            )

    # -- radio (opción única) ------------------------------------------ #
    def choose_radio(self, title: str, value: str) -> None:
        block = self.question_block(title)
        value = str(value).strip()

        # Google Forms: cada opción es div[role="radio"] con aria-label = texto.
        opcion = block.locator(f'div[role="radio"][aria-label="{value}"]')
        if opcion.count() == 0:
            # Fallback: por texto visible dentro de la opción.
            opcion = block.locator('div[role="radio"]').filter(has_text=value)
        if opcion.count() == 0:
            disponibles = block.locator('div[role="radio"]').all_inner_texts()
            raise RuntimeError(
                f"Opción '{value}' no encontrada en '{title}'. "
                f"Opciones visibles: {disponibles}"
            )
        opcion.first.click()

    # -- dropdown (lista desplegable) -------------------------------- #
    def choose_dropdown(self, title: str, value: str) -> None:
        block = self.question_block(title)
        value = str(value).strip()

        # Abrir el desplegable.
        listbox = block.locator('div[role="listbox"]').first
        listbox.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
        listbox.click()

        # Las opciones (div[role="option"]) se renderizan en un overlay a nivel
        # de página, no siempre dentro del bloque -> buscar en toda la página.
        opcion = self.page.locator(
            f'div[role="option"][aria-label="{value}"]'
        )
        if opcion.count() == 0:
            opcion = self.page.locator('div[role="option"]').filter(
                has_text=value
            )
        if opcion.count() == 0:
            disponibles = self.page.locator(
                'div[role="option"]'
            ).all_inner_texts()
            raise RuntimeError(
                f"Opción '{value}' no encontrada en dropdown '{title}'. "
                f"Opciones visibles: {disponibles}"
            )
        opcion.first.click()

    # -- subida de archivo (la parte delicada) --------------------- #
    def upload_file(self, title: str, file_path: str) -> None:
        """
        Sube una imagen al campo "Cargue foto".

        Flujo real de Google Forms (2024/2025):
          1. Click en el botón "Agregar archivo" dentro del bloque.
          2. Se abre un DIÁLOGO de Google Drive DENTRO DE UN IFRAME.
          3. Ese iframe contiene un <input type="file"> (normalmente oculto).
          4. set_input_files() sobre ese input dispara la subida.
          5. Se espera a que el diálogo se cierre y aparezca el "chip" con el
             nombre del archivo dentro del bloque de la pregunta.

        Requiere sesión de Google iniciada en el contexto persistente.
        """
        path = _resolve_photo(file_path)
        if not path.exists():
            raise FileNotFoundError(
                f"No existe la imagen: {path}\n"
                f"    (valor en la columna: {file_path!r}). Debe ser un archivo "
                f"local, no una URL. Se busca también dentro de "
                f"{config.PHOTO_BASE_DIR}."
            )

        block = self.question_block(title)

        # 1) Botón "Agregar archivo".
        #    TODO: verificar el texto/rol exacto del botón en tu formulario.
        add_btn = None
        for text in config.ADD_FILE_BUTTON_TEXTS:
            cand = block.get_by_role("button", name=text)
            if cand.count() > 0:
                add_btn = cand.first
                break
        if add_btn is None:
            # Fallback: cualquier botón dentro del bloque.
            add_btn = block.locator("div[role='button'], button").first
        add_btn.click()

        # 2) Esperar el iframe del selector de Google Drive.
        #    El src suele contener "picker" o "docs.google.com/picker".
        #    TODO: si no matchea, inspeccioná el atributo src del <iframe>.
        self.page.wait_for_selector(
            'iframe[src*="picker"], iframe[name^="picker"], '
            'iframe[src*="drive.google.com"]',
            timeout=config.UPLOAD_TIMEOUT_MS,
        )
        picker_iframe = None
        for fr in self.page.frames:
            if any(k in (fr.url or "") for k in ("picker", "drive.google.com")):
                picker_iframe = fr
                break
        if picker_iframe is None:
            raise RuntimeError(
                "No encontré el iframe del selector de archivos de Google Drive."
            )

        # 3) A veces hay que activar la pestaña "Subir" / "Upload" antes de que
        #    exista el <input type=file>.
        for tab_text in ("Subir", "Upload", "Explorar", "Browse"):
            tab = picker_iframe.get_by_text(tab_text, exact=False)
            try:
                if tab.count() > 0:
                    tab.first.click(timeout=2_000)
                    break
            except PlaywrightTimeoutError:
                pass

        # 4) Setear el archivo en el input oculto del iframe.
        file_input = picker_iframe.locator('input[type="file"]')
        file_input.wait_for(state="attached", timeout=config.UPLOAD_TIMEOUT_MS)
        file_input.set_input_files(str(path))

        # 5) Esperar a que termine la subida: el iframe del picker desaparece
        #    y en el bloque aparece el nombre del archivo.
        try:
            self.page.wait_for_selector(
                'iframe[src*="picker"]',
                state="detached",
                timeout=config.UPLOAD_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            self.log("  · Aviso: el diálogo de subida no se cerró solo; continúo.")

        # Confirmación best-effort: el chip con el nombre del archivo.
        try:
            block.get_by_text(path.name, exact=False).wait_for(
                timeout=config.ACTION_TIMEOUT_MS
            )
        except PlaywrightTimeoutError:
            self.log(
                f"  · Aviso: no pude confirmar visualmente la subida de {path.name}."
            )


# --------------------------------------------------------------------------- #
# Orquestación de una fila
# --------------------------------------------------------------------------- #
def _fill_one_row(filler: FormFiller, row: pd.Series, log: LogFn) -> None:
    for col in config.FIELD_ORDER:
        if col not in config.FIELD_TITLES:
            continue

        title = config.FIELD_TITLES[col]
        ftype = config.FIELD_TYPES.get(col, "text")
        raw = row.get(col, None)

        # Valor vacío en campo opcional -> se salta.
        if isinstance(raw, str):
            is_empty = not raw.strip()
        else:
            is_empty = raw is None or pd.isna(raw)

        if is_empty:
            if col in config.OPTIONAL_FIELDS:
                log(f"  · {col}: vacío (opcional) -> se omite")
                continue
            raise ValueError(f"Campo obligatorio vacío: '{col}'")

        try:
            if ftype == "text":
                filler.fill_text(title, str(raw))
            elif ftype == "date":
                filler.fill_date(title, raw)
            elif ftype == "radio":
                filler.choose_radio(title, str(raw))
            elif ftype == "dropdown":
                filler.choose_dropdown(title, str(raw))
            elif ftype == "file":
                filler.upload_file(title, str(raw))
            else:
                raise ValueError(f"Tipo de campo no soportado: {ftype!r}")
            log(f"  · {col}: OK")
        except Exception as exc:  # noqa: BLE001
            # Se re-lanza para marcar la fila como fallida, pero con contexto.
            raise RuntimeError(f"Fallo en campo '{col}' ({ftype}): {exc}") from exc


def _submit_and_reset(page: Page, log: LogFn) -> None:
    """Envía la respuesta y vuelve al formulario en blanco para la siguiente fila."""
    # Botón Enviar (puede haber "Siguiente" si el form tiene varias páginas).
    for text in config.SUBMIT_BUTTON_TEXTS:
        btn = page.get_by_role("button", name=text)
        if btn.count() > 0:
            btn.first.click()
            break
    else:
        # TODO: si tu formulario es multipágina, acá habría que manejar
        #       los botones "Siguiente" en bucle antes del "Enviar".
        raise RuntimeError("No encontré el botón de envío del formulario.")

    # Página de confirmación -> "Enviar otra respuesta".
    for text in config.ANOTHER_RESPONSE_TEXTS:
        link = page.get_by_role("link", name=text)
        try:
            link.first.wait_for(timeout=config.ACTION_TIMEOUT_MS)
            link.first.click()
            return
        except PlaywrightTimeoutError:
            continue

    # Fallback: recargar la URL del formulario.
    log("  · No apareció 'Enviar otra respuesta'; recargo la URL del formulario.")
    page.goto(config.GOOGLE_FORM_URL, wait_until="domcontentloaded")


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def run_automation(
    df: pd.DataFrame,
    on_log: LogFn | None = None,
    limit: int | None = None,
) -> RunResult:
    """
    Recorre el DataFrame filtrado y carga cada fila en el Google Form.

    Parámetros
    ----------
    df       : DataFrame ya filtrado desde el dashboard.
    on_log   : callback para emitir mensajes de progreso (default: print).
    limit    : si se indica, procesa sólo las primeras N filas (útil para probar).
    """
    log: LogFn = on_log or print
    result = RunResult()

    if config.GOOGLE_FORM_URL.count("X") > 5:
        raise RuntimeError(
            "Configurá config.GOOGLE_FORM_URL con la URL real del formulario."
        )

    rows = df.head(limit) if limit else df
    config.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        # Contexto persistente = recuerda la sesión de Google entre corridas.
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(config.BROWSER_PROFILE_DIR),
            headless=config.HEADLESS,
            slow_mo=config.SLOW_MO_MS,
            accept_downloads=False,
            viewport={"width": 1280, "height": 900},
        )
        context.set_default_timeout(config.ACTION_TIMEOUT_MS)
        context.set_default_navigation_timeout(config.NAV_TIMEOUT_MS)

        page = context.pages[0] if context.pages else context.new_page()

        log(f"Abriendo formulario: {config.GOOGLE_FORM_URL}")
        page.goto(config.GOOGLE_FORM_URL, wait_until="domcontentloaded")

        # Chequeo simple de login de Google (por si redirige a accounts.google.com).
        if "accounts.google.com" in page.url:
            log(
                "⚠️  Google pide iniciar sesión. Logueate en la ventana abierta; "
                "espero 60s y continúo."
            )
            page.wait_for_url(
                lambda url: "accounts.google.com" not in url, timeout=60_000
            )

        total = len(rows)
        log(f"Filas a procesar: {total}")

        for i, (idx, row) in enumerate(rows.iterrows(), start=1):
            log(f"\n[{i}/{total}] Fila {idx} ...")
            try:
                filler = FormFiller(page, log)
                _fill_one_row(filler, row, log)
                _submit_and_reset(page, log)
                result.add(RowResult(index=int(idx), ok=True))
                log(f"[{i}/{total}] ✔ Enviada")
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                result.add(RowResult(index=int(idx), ok=False, error=msg))
                log(f"[{i}/{total}] [X] ERROR: {msg}")
                # Intentar dejar el formulario limpio para la siguiente fila.
                try:
                    page.goto(
                        config.GOOGLE_FORM_URL, wait_until="domcontentloaded"
                    )
                except Exception:  # noqa: BLE001
                    pass

            time.sleep(config.PAUSE_BETWEEN_ROWS_S)

        log(
            f"\nResumen: {result.exitosos} OK / {result.fallidos} con error "
            f"de {result.total} filas."
        )
        context.close()

    return result


# --------------------------------------------------------------------------- #
# CLI (lo usa el dashboard para correr en un subproceso aislado)
# --------------------------------------------------------------------------- #
def _main() -> int:
    parser = argparse.ArgumentParser(description="Carga masiva a Google Forms")
    parser.add_argument(
        "--input",
        required=True,
        help="Ruta a un .pkl con el DataFrame filtrado (pandas.to_pickle).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Procesar sólo las primeras N filas (para pruebas).",
    )
    args = parser.parse_args()

    df = pd.read_pickle(args.input)

    def log(msg: str) -> None:
        # flush inmediato para que el dashboard lea el progreso en vivo.
        print(msg, flush=True)

    try:
        res = run_automation(df, on_log=log, limit=args.limit)
        return 0 if res.fallidos == 0 else 1
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(_main())
