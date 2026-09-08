"""
Pestaña «Carga al Form»: lanza automator.py para volcar las filas filtradas
al Google Form y muestra el progreso en vivo.

Se dibuja llamando a `render(df_f)` desde app.py.
"""

from __future__ import annotations

import subprocess
import sys

import pandas as pd
import streamlit as st

import config


def render(df_f: pd.DataFrame) -> None:
    st.subheader("Carga automática a Google Forms")

    form_ok = "X" * 6 not in config.GOOGLE_FORM_URL
    if not form_ok:
        st.warning("Configurá `GOOGLE_FORM_URL` en `config.py` con la URL real del formulario (`/viewform`).")

    st.markdown(
        f"""
Se enviará **una respuesta al Google Form por cada una de las
{len(df_f):,} filas filtradas** (las mismas de la pestaña *Detalle*).
Al enviarse, el propio Form las vuelca de nuevo en el Sheet.

- **Fotos:** la columna «Cargue foto» debe apuntar a un **archivo local**
  (ruta absoluta, relativa al proyecto, o sólo el nombre dentro de
  `{config.PHOTO_BASE_DIR.name}/`). Una URL de Drive no sirve para subir.
- La primera vez se abre un navegador para **iniciar sesión en Google**
  (necesario para la subida). La sesión queda guardada.
"""
    )

    cc1, cc2 = st.columns([3, 2])
    with cc1:
        modo_prueba = st.toggle("Modo prueba (sólo 1 fila)", value=True)
    with cc2:
        st.caption("Dejalo activado la primera vez para validar los selectores.")

    with st.expander(f"Ver las {len(df_f):,} filas que se enviarían"):
        _cv = [c for c in df_f.columns if not c.startswith("_")]
        st.dataframe(df_f[_cv], width="stretch", hide_index=True)

    lanzar = st.button(
        "🚀 Iniciar Carga a Google Forms",
        type="primary",
        width="stretch",
        disabled=df_f.empty or not form_ok,
    )

    if lanzar:
        config.RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        payload = config.RUNTIME_DIR / "payload.pkl"
        df_f.to_pickle(payload)

        cmd = [sys.executable, str(config.BASE_DIR / "automator.py"), "--input", str(payload)]
        if modo_prueba:
            cmd += ["--limit", "1"]

        st.info("Automatización lanzada. Progreso en vivo:")
        log_box = st.empty()
        lineas: list[str] = []

        proc = subprocess.Popen(
            cmd,
            cwd=str(config.BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for linea in proc.stdout:
            lineas.append(linea.rstrip())
            log_box.code("\n".join(lineas[-400:]), language="text")
        codigo = proc.wait()

        if codigo == 0:
            st.success("✅ Carga finalizada sin errores. Pulsá 🔄 Actualizar para ver las respuestas.")
        elif codigo == 1:
            st.warning("⚠️ Finalizó con algunas filas en error (ver log).")
        else:
            st.error(f"❌ La automatización terminó con código {codigo} (ver log).")
