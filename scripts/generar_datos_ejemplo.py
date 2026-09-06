"""
Genera 'data/respuestas_ejemplo.csv' con la misma estructura que el Google Sheet
de respuestas, para desarrollar el dashboard sin conexión.

Uso:
    python scripts/generar_datos_ejemplo.py

Luego, en config.py:
    RESPONSES_LOCAL_OVERRIDE = "data/respuestas_ejemplo.csv"
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "data" / "respuestas_ejemplo.csv"

ZONAS = ["Norte", "Sur", "Este", "Oeste"]
MERCADOS = ["Mercado Central", "Mercado 4", "Abasto", "Ciudad del Este", "San Lorenzo"]
TIPOS = ["Relevamiento", "Activación", "Auditoría"]

random.seed(42)
start = date(2026, 8, 1)
rows = []
for _ in range(160):
    d = start + timedelta(days=random.randint(0, 35))
    canje = random.random() > 0.25
    rows.append(
        {
            "Marca temporal": (d + timedelta(minutes=random.randint(0, 600))).strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "Fecha": d.strftime("%d/%m/%Y"),
            "Usuario (Gmail)": random.choice(
                ["ana@faurus.com", "luis@faurus.com", "sofia@faurus.com"]
            ),
            "Tipo": random.choice(TIPOS),
            "Zona": random.choice(ZONAS),
            "Mercado": random.choice(MERCADOS),
            "Canje Realizado": "Sí" if canje else "No",
            "Número de puesto": random.randint(1, 80),
            "Nombre del puesto": f"Puesto {random.randint(1, 80)}",
            "Cargue foto": "https://drive.google.com/open?id=EJEMPLO",
            "Observaciones": random.choice(["", "", "Sin stock", "Cliente ausente"]),
            "Canatidad de Canje": random.randint(1, 15) if canje else 0,
        }
    )

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT, index=False)
print(f"Escrito: {OUT}  ({len(df)} filas)")
print('\nEn config.py:  RESPONSES_LOCAL_OVERRIDE = "data/respuestas_ejemplo.csv"')
