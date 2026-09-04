"""Visao publica — a rota que o acolito abre no celular (RF01).

Sem autenticacao e sem parametros obrigatorios: o backend decide qual mes
mostrar e devolve tudo pronto para a tela desenhar.
"""

from typing import Optional

from fastapi import APIRouter

from config import agora_local, mes_ano_referencia
from database import supabase
from db_utils import executar
from services import apresentacao

router = APIRouter(prefix="/publico", tags=["Visao Publica"])

TABELA = "escalas_geradas"


def _mes_com_publicacao(mes: Optional[int], ano: Optional[int]) -> Optional[str]:
    """Escolhe o mes a exibir.

    A regra e o mes vigente. Mas se a escala dele ainda nao foi publicada,
    mostrar uma pagina vazia seria pior do que mostrar a ultima escala que os
    acolitos receberam — entao caimos para a publicacao mais recente.
    """
    if mes and ano:
        return mes_ano_referencia(mes, ano)

    hoje = agora_local()
    atual = mes_ano_referencia(hoje.month, hoje.year)
    existe = executar(
        supabase.table(TABELA)
        .select("id")
        .eq("mes_ano_referencia", atual)
        .eq("status", "Publicado")
        .limit(1),
        "verificar escala do mes",
    )
    if existe:
        return atual

    ultima = executar(
        supabase.table(TABELA)
        .select("mes_ano_referencia, data_hora")
        .eq("status", "Publicado")
        .order("data_hora", desc=True)
        .limit(1),
        "buscar ultima escala publicada",
    )
    return ultima[0]["mes_ano_referencia"] if ultima else None


@router.get("/escala")
def escala_publica(mes: Optional[int] = None, ano: Optional[int] = None) -> dict:
    mes_ano = _mes_com_publicacao(mes, ano)
    if mes_ano is None:
        return {"mes_ano_referencia": None, "escala": []}

    escalas = executar(
        supabase.table(TABELA)
        .select("*")
        .eq("mes_ano_referencia", mes_ano)
        .eq("status", "Publicado"),
        "buscar escala publicada",
    )
    if not escalas:
        return {"mes_ano_referencia": mes_ano, "escala": []}

    participacoes = executar(
        supabase.table("escala_acolitos")
        .select("*")
        .in_("escala_id", [e["id"] for e in escalas]),
        "buscar participacoes",
    )
    acolitos = executar(
        supabase.table("acolitos").select("id, nome_completo"), "listar acolitos"
    )
    igrejas = executar(
        supabase.table("igrejas").select("id, nome_igreja"), "listar igrejas"
    )

    return {
        "mes_ano_referencia": mes_ano,
        "escala": apresentacao.agrupar(escalas, participacoes, acolitos, igrejas),
    }
