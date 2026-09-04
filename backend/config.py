"""Configuracoes lidas do ambiente."""

import os
from datetime import datetime, timedelta, timezone

# Fuso da paroquia. As missas sao cadastradas em horario local ("Domingo, 8h")
# e a coluna data_hora e TIMESTAMPTZ; sem o offset explicito o Postgres
# assumiria UTC e a missa das 8h apareceria como 5h para o acolito.
# O Brasil nao adota mais horario de verao, entao um offset fixo basta.
FUSO_PAROQUIA = timezone(timedelta(hours=int(os.getenv("UTC_OFFSET_HORAS", "-3"))))


def agora_local() -> datetime:
    return datetime.now(FUSO_PAROQUIA)


def mes_ano_referencia(mes: int, ano: int) -> str:
    """Formato usado na coluna `mes_ano_referencia`, ex: `"08-2026"`."""
    return f"{mes:02d}-{ano}"


def origens_cors() -> list[str]:
    origens = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in origens.split(",") if o.strip()]