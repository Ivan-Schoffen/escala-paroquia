"""Fabrica de escalas: geracao, revisao manual e publicacao (RF06)."""

from fastapi import APIRouter, Depends, HTTPException, status

from auth import require_coordenador
from config import mes_ano_referencia
from database import supabase
from db_utils import buscar_por_id, executar, um_ou_404
from schemas import GerarEscalaRequest, TrocaAcolitoRequest
from services import apresentacao, sorteio

router = APIRouter(prefix="/escalas", tags=["Escalas"])

TABELA = "escalas_geradas"
TABELA_PARTICIPACOES = "escala_acolitos"


def _carregar(mes_ano: str) -> tuple[list[dict], list[dict]]:
    escalas = executar(
        supabase.table(TABELA).select("*").eq("mes_ano_referencia", mes_ano),
        "buscar escalas do mes",
    )
    if not escalas:
        return [], []
    ids = [e["id"] for e in escalas]
    participacoes = executar(
        supabase.table(TABELA_PARTICIPACOES).select("*").in_("escala_id", ids),
        "buscar participacoes",
    )
    return escalas, participacoes


def _montar_resposta(escalas: list[dict], participacoes: list[dict]) -> list[dict]:
    acolitos = executar(
        supabase.table("acolitos").select("id, nome_completo"), "listar acolitos"
    )
    igrejas = executar(
        supabase.table("igrejas").select("id, nome_igreja"), "listar igrejas"
    )
    return apresentacao.agrupar(escalas, participacoes, acolitos, igrejas)


def _acolitos_ocupados_no_horario(data_hora: str) -> set[str]:
    """Quem ja serve em alguma celebracao naquele exato horario."""
    simultaneas = executar(
        supabase.table(TABELA).select("id").eq("data_hora", data_hora),
        "buscar celebracoes simultaneas",
    )
    if not simultaneas:
        return set()
    participacoes = executar(
        supabase.table(TABELA_PARTICIPACOES)
        .select("acolito_id")
        .in_("escala_id", [s["id"] for s in simultaneas]),
        "buscar participacoes simultaneas",
    )
    return {p["acolito_id"] for p in participacoes}


@router.post("/gerar")
def gerar_escala(
    pedido: GerarEscalaRequest,
    substituir_publicada: bool = False,
    _=Depends(require_coordenador),
) -> dict:
    """Roda o motor de sorteio e grava o rascunho do mes.

    Regerar apaga o que existia daquele mes. Por isso, se ja houver escala
    **publicada**, a rota recusa: apagar sem querer o que os acolitos ja
    receberam no WhatsApp seria o pior erro possivel. O coordenador confirma
    a sobrescrita com `substituir_publicada=true`.
    """
    mes_ano = mes_ano_referencia(pedido.mes, pedido.ano)
    existentes, _participacoes = _carregar(mes_ano)

    publicadas = [e for e in existentes if e.get("status") == "Publicado"]
    if publicadas and not substituir_publicada:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Ja existe uma escala publicada para {mes_ano}. "
                "Reenvie com substituir_publicada=true para sobrescrever."
            ),
        )

    if existentes:
        executar(
            supabase.table(TABELA).delete().eq("mes_ano_referencia", mes_ano),
            "limpar escala anterior do mes",
        )

    missas_padrao = executar(
        supabase.table("missas_padrao").select("*"), "listar missas padrao"
    )
    if not missas_padrao:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cadastre ao menos uma missa padrao antes de gerar a escala.",
        )

    excecoes = executar(
        supabase.table("calendario_excecoes").select("*"), "listar excecoes"
    )
    acolitos = executar(supabase.table("acolitos").select("*"), "listar acolitos")
    igrejas = executar(supabase.table("igrejas").select("*"), "listar igrejas")

    celebracoes = sorteio.gerar(
        mes=pedido.mes,
        ano=pedido.ano,
        missas_padrao=missas_padrao,
        excecoes=excecoes,
        acolitos=acolitos,
        igrejas=igrejas,
        usar_geolocalizacao=pedido.usar_geolocalizacao,
    )
    if not celebracoes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nenhuma celebracao encontrada para {mes_ano}.",
        )

    linhas = [
        {
            "igreja_id": c.igreja_id,
            "data_hora": c.data_hora.isoformat(),
            "tempo_liturgico": c.tempo_liturgico,
            "titulo_evento": c.titulo_evento,
            "mes_ano_referencia": mes_ano,
            "status": "Rascunho",
        }
        for c in celebracoes
    ]
    gravadas = executar(supabase.table(TABELA).insert(linhas), "gravar escalas")

    # O insert devolve as linhas na mesma ordem em que foram enviadas, entao
    # basta parear pelo indice para saber o id de cada celebracao.
    participacoes = []
    alertas = []
    for celebracao, gravada in zip(celebracoes, gravadas):
        escala_id = gravada["id"]
        for acolito_id, funcao in celebracao.escalados:
            participacoes.append(
                {"escala_id": escala_id, "acolito_id": acolito_id, "funcao": funcao}
            )
        for funcao, quantidade in celebracao.vagas_vazias.items():
            alertas.append(
                {
                    "escala_id": escala_id,
                    "data_hora": celebracao.data_hora.isoformat(),
                    "funcao": funcao,
                    "quantidade": quantidade,
                }
            )

    if participacoes:
        executar(
            supabase.table(TABELA_PARTICIPACOES).insert(participacoes),
            "gravar acolitos das escalas",
        )

    escalas, gravadas_participacoes = _carregar(mes_ano)
    return {
        "mes_ano_referencia": mes_ano,
        "status": "Rascunho",
        "celebracoes_geradas": len(celebracoes),
        "vagas_nao_preenchidas": alertas,
        "escala": _montar_resposta(escalas, gravadas_participacoes),
    }


@router.get("/{ano}/{mes}")
def obter_escala_do_mes(
    ano: int,
    mes: int,
    _=Depends(require_coordenador),
) -> dict:
    """Rascunho ou publicado do mes, para a tela de revisao."""
    mes_ano = mes_ano_referencia(mes, ano)
    escalas, participacoes = _carregar(mes_ano)
    status_atual = None
    if escalas:
        todas_publicadas = all(e.get("status") == "Publicado" for e in escalas)
        status_atual = "Publicado" if todas_publicadas else "Rascunho"
    return {
        "mes_ano_referencia": mes_ano,
        "status": status_atual,
        "escala": _montar_resposta(escalas, participacoes),
    }


@router.get("/{ano}/{mes}/contadores")
def contadores_do_mes(
    ano: int,
    mes: int,
    _=Depends(require_coordenador),
) -> list[dict]:
    """Quantas vezes cada acolito serviu no mes (RN01), para o dashboard."""
    mes_ano = mes_ano_referencia(mes, ano)
    _escalas, participacoes = _carregar(mes_ano)
    contagem: dict[str, int] = {}
    for participacao in participacoes:
        acolito_id = participacao["acolito_id"]
        contagem[acolito_id] = contagem.get(acolito_id, 0) + 1

    acolitos = executar(
        supabase.table("acolitos").select("id, nome_completo, classificacao"),
        "listar acolitos",
    )
    resultado = [
        {
            "acolito_id": a["id"],
            "nome": a["nome_completo"],
            "classificacao": a["classificacao"],
            "missas": contagem.get(a["id"], 0),
        }
        for a in acolitos
    ]
    resultado.sort(key=lambda r: (-r["missas"], r["nome"]))
    return resultado


@router.get("/celebracao/{escala_id}/candidatos")
def listar_candidatos(
    escala_id: str,
    funcao: str,
    _=Depends(require_coordenador),
) -> list[dict]:
    """Alimenta o menu suspenso da troca manual.

    Devolve so quem cabe de fato naquela vaga: mesma classificacao, ativo e
    livre naquele horario.
    """
    if funcao not in sorteio.ORDEM_FUNCOES:
        opcoes = ", ".join(sorteio.ORDEM_FUNCOES)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Funcao invalida. Use uma de: {opcoes}.",
        )

    escala = buscar_por_id(TABELA, escala_id, "Escala")
    ocupados = _acolitos_ocupados_no_horario(str(escala["data_hora"]))

    candidatos = executar(
        supabase.table("acolitos")
        .select("id, nome_completo, classificacao")
        .eq("classificacao", funcao)
        .eq("ativo", True)
        .order("nome_completo"),
        "listar candidatos",
    )
    return [c for c in candidatos if c["id"] not in ocupados]


@router.put("/participacoes/{participacao_id}")
def trocar_acolito(
    participacao_id: str,
    troca: TrocaAcolitoRequest,
    _=Depends(require_coordenador),
) -> dict:
    """Troca manual do coordenador: substitui quem ocupa uma vaga."""
    participacao = buscar_por_id(TABELA_PARTICIPACOES, participacao_id, "Participacao")
    escala = buscar_por_id(TABELA, participacao["escala_id"], "Escala")
    novo = buscar_por_id("acolitos", troca.acolito_id, "Acolito")

    funcao = participacao.get("funcao")
    if funcao and novo["classificacao"] != funcao:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{novo['nome_completo']} e '{novo['classificacao']}' e a vaga "
                f"e de '{funcao}'."
            ),
        )

    ocupados = _acolitos_ocupados_no_horario(str(escala["data_hora"]))
    ocupados.discard(participacao["acolito_id"])
    if troca.acolito_id in ocupados:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{novo['nome_completo']} ja esta escalado(a) nesse horario.",
        )

    registros = executar(
        supabase.table(TABELA_PARTICIPACOES)
        .update({"acolito_id": troca.acolito_id})
        .eq("id", participacao_id),
        "trocar acolito",
    )
    return um_ou_404(registros, "Participacao")


@router.delete(
    "/participacoes/{participacao_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remover_participacao(
    participacao_id: str,
    _=Depends(require_coordenador),
) -> None:
    buscar_por_id(TABELA_PARTICIPACOES, participacao_id, "Participacao")
    executar(
        supabase.table(TABELA_PARTICIPACOES).delete().eq("id", participacao_id),
        "remover acolito da escala",
    )


@router.post("/publicar")
def publicar_escala(
    pedido: GerarEscalaRequest,
    _=Depends(require_coordenador),
) -> dict:
    """Vira o mes inteiro de Rascunho para Publicado — a escala vai ao ar."""
    mes_ano = mes_ano_referencia(pedido.mes, pedido.ano)
    escalas, _participacoes = _carregar(mes_ano)
    if not escalas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nao existe escala gerada para {mes_ano}.",
        )

    executar(
        supabase.table(TABELA)
        .update({"status": "Publicado"})
        .eq("mes_ano_referencia", mes_ano),
        "publicar escala",
    )
    return {
        "mes_ano_referencia": mes_ano,
        "status": "Publicado",
        "celebracoes": len(escalas),
    }
