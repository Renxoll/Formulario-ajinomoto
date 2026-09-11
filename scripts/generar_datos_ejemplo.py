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

MERCADOS = ["Huamantanga", "Huáscar / Valle Sagrado", "Unicachi VES", "Caquetá", "Bambú"]
USUARIOS = ["ana@ajinomoto.com", "luis@ajinomoto.com", "sofia@ajinomoto.com"]
CANJES = [
    "03 Tiras Aji-no-mix® Deli Arroz + 06 sobres Aji-no-mix® Mezcla para apanar",
]

random.seed(42)
start = date(2026, 8, 1)
rows = []
for _ in range(160):
    d = start + timedelta(days=random.randint(0, 35), minutes=random.randint(0, 600))
    rows.append(
        {
            "Marca temporal": d.strftime("%d/%m/%Y %H:%M:%S"),
            "Usuario (Gmail)": random.choice(USUARIOS),
            "Mercado": random.choice(MERCADOS),
            "Canje Realizado": random.choice(CANJES),
            "Cargue foto": "https://drive.google.com/open?id=EJEMPLO",
            "Observaciones": random.choice(["", "", "Sin stock", "Cliente ausente"]),
            "Cantidad de Canje": random.randint(1, 5),
        }
    )

df = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUT, index=False)
print(f"Escrito: {OUT}  ({len(df)} filas)")
print('\nEn config.py:  RESPONSES_LOCAL_OVERRIDE = "data/respuestas_ejemplo.csv"')
