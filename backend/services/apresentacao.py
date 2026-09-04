"""Monta o JSON que as telas consomem.

A escala fica espalhada em tres tabelas (`escalas_geradas`, `escala_acolitos`
e `acolitos`). Agrupar isso aqui, no backend, deixa a tela publica burra do
jeito que a especificacao pede: ela so percorre a lista e desenha.
"""

from datetime import datetime
from typing import Iterable

from config import FUSO_PAROQUIA
from services.sorteio import ORDEM_FUNCOES


def _hora_local(valor) -> datetime:
    """Traz o timestamp do banco de volta para o fuso da paroquia.

    O Postgres devolve TIMESTAMPTZ normalizado em UTC; sem converter, a missa
    das 8h apareceria como 11h para o acolito.
    """
    if isinstance(valor, datetime):
        momento = valor
    else:
        momento = datetime.fromisoformat(str(valor))
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(FUSO_PAROQUIA)


def agrupar(
    escalas: Iterable[dict],
    participacoes: Iterable[dict],
    acolitos: Iterable[dict],
    igrejas: Iterable[dict],
) -> list[dict]:
    """Devolve as celebracoes agrupadas por igreja, em ordem cronologica."""

    nomes_acolitos = {a["id"]: a["nome_completo"] for a in acolitos}
    nomes_igrejas = {i["id"]: i["nome_igreja"] for i in igrejas}

    por_escala: dict[str, list[dict]] = {}
    for participacao in participacoes:
        por_escala.setdefault(participacao["escala_id"], []).append(participacao)

    agrupado: dict[str, dict] = {}
    for escala in sorted(escalas, key=lambda e: str(e["data_hora"])):
        igreja_id = escala["igreja_id"]
        bloco = agrupado.setdefault(
            igreja_id,
            {
                "igreja_id": igreja_id,
                "igreja": nomes_igrejas.get(igreja_id, "Igreja"),
                "celebracoes": [],
            },
        )

        equipe: dict[str, list[dict]] = {funcao: [] for funcao in ORDEM_FUNCOES}
        for participacao in por_escala.get(escala["id"], []):
            funcao = participacao.get("funcao") or "Maior"
            equipe.setdefault(funcao, []).append(
                {
                    "participacao_id": participacao["id"],
                    "acolito_id": participacao["acolito_id"],
                    "nome": nomes_acolitos.get(participacao["acolito_id"], "?"),
                }
            )
        for lista in equipe.values():
            lista.sort(key=lambda p: p["nome"])

        momento = _hora_local(escala["data_hora"])
        bloco["celebracoes"].append(
            {
                "escala_id": escala["id"],
                "data": momento.date().isoformat(),
                "hora": momento.strftime("%H:%M"),
                "titulo": escala.get("titulo_evento") or escala.get("tempo_liturgico"),
                "tempo_liturgico": escala.get("tempo_liturgico"),
                "titulo_evento": escala.get("titulo_evento"),
                "status": escala.get("status"),
                "equipe": equipe,
            }
        )

    return sorted(agrupado.values(), key=lambda b: b["igreja"])
