"""Helpers para conversar com o Supabase sem repetir try/except em toda rota."""

from datetime import date, datetime, time
from typing import Any

from fastapi import HTTPException, status

from database import supabase


def executar(consulta, contexto: str) -> list[dict]:
    """Roda a consulta e devolve `response.data`, traduzindo o erro do driver.

    Sem isso, qualquer falha do Supabase viraria um 500 com stack trace; aqui
    ela vira um 400 com uma mensagem que o frontend pode mostrar.
    """
    try:
        resposta = consulta.execute()
    except Exception as erro:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro ao {contexto}: {erro}",
        ) from erro
    return resposta.data or []


def um_ou_404(registros: list[dict], entidade: str) -> dict:
    if not registros:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entidade} nao encontrado(a).",
        )
    return registros[0]


def buscar_por_id(tabela: str, registro_id: str, entidade: str) -> dict:
    registros = executar(
        supabase.table(tabela).select("*").eq("id", registro_id),
        f"buscar {entidade.lower()}",
    )
    return um_ou_404(registros, entidade)


def campos_preenchidos(modelo) -> dict[str, Any]:
    """So os campos que vieram no corpo da requisicao.

    `exclude_unset` e o que diferencia "nao mandou o campo" de "mandou null":
    sem isso um PUT parcial apagaria as colunas omitidas.
    """
    return modelo.model_dump(exclude_unset=True)


def serializar(dados: dict) -> dict:
    """Converte date/time/datetime para string antes de mandar ao Supabase.

    O cliente serializa o corpo como JSON, que nao conhece esses tipos; sem
    isso um `horario: time(8, 0)` estoura na hora do insert.
    """
    convertidos = {}
    for chave, valor in dados.items():
        if isinstance(valor, (date, datetime, time)):
            convertidos[chave] = valor.isoformat()
        else:
            convertidos[chave] = valor
    return convertidos
