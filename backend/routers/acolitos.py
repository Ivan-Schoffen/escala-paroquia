"""CRUD de acolitos e vinculo familiar entre irmaos (RF04)."""

from fastapi import APIRouter, Depends, HTTPException, status

from auth import require_coordenador
from database import supabase
from db_utils import buscar_por_id, campos_preenchidos, executar, um_ou_404
from schemas import AcolitoCreate, AcolitoUpdate
from services.geocoding import preencher_coordenadas

router = APIRouter(prefix="/acolitos", tags=["Acolitos"])

TABELA = "acolitos"


@router.get("/")
def listar_acolitos(apenas_ativos: bool = False) -> list[dict]:
    consulta = supabase.table(TABELA).select("*").order("nome_completo")
    if apenas_ativos:
        consulta = consulta.eq("ativo", True)
    return executar(consulta, "listar acolitos")


@router.get("/{acolito_id}")
def obter_acolito(acolito_id: str) -> dict:
    return buscar_por_id(TABELA, acolito_id, "Acolito")


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_acolito(
    acolito: AcolitoCreate,
    _=Depends(require_coordenador),
) -> dict:
    dados = preencher_coordenadas(acolito.model_dump())
    registros = executar(supabase.table(TABELA).insert(dados), "cadastrar acolito")
    return um_ou_404(registros, "Acolito")


@router.put("/{acolito_id}")
def atualizar_acolito(
    acolito_id: str,
    acolito: AcolitoUpdate,
    _=Depends(require_coordenador),
) -> dict:
    dados = campos_preenchidos(acolito)
    if not dados:
        return buscar_por_id(TABELA, acolito_id, "Acolito")

    atual = buscar_por_id(TABELA, acolito_id, "Acolito")
    dados = preencher_coordenadas({**atual, **dados})
    dados.pop("id", None)
    dados.pop("criado_em", None)

    registros = executar(
        supabase.table(TABELA).update(dados).eq("id", acolito_id),
        "atualizar acolito",
    )
    return um_ou_404(registros, "Acolito")


@router.delete("/{acolito_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_acolito(acolito_id: str, _=Depends(require_coordenador)) -> None:
    buscar_por_id(TABELA, acolito_id, "Acolito")
    executar(supabase.table(TABELA).delete().eq("id", acolito_id), "remover acolito")


def _proximo_grupo_familiar() -> int:
    registros = executar(
        supabase.table(TABELA)
        .select("grupo_familiar_id")
        .not_.is_("grupo_familiar_id", "null")
        .order("grupo_familiar_id", desc=True)
        .limit(1),
        "calcular grupo familiar",
    )
    if not registros:
        return 1
    return int(registros[0]["grupo_familiar_id"]) + 1


@router.post("/{acolito_id}/vincular/{irmao_id}")
def vincular_irmaos(
    acolito_id: str,
    irmao_id: str,
    _=Depends(require_coordenador),
) -> dict:
    """Coloca dois acolitos no mesmo grupo familiar (RN02).

    O coordenador so escolhe as duas pessoas na tela; quem resolve o
    `grupo_familiar_id` e este endpoint. Se um dos dois ja pertence a um
    grupo, o outro entra nesse mesmo grupo — assim tres ou mais irmaos vao
    sendo encadeados sem o coordenador lidar com IDs.
    """
    if acolito_id == irmao_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel vincular um acolito a ele mesmo.",
        )

    acolito = buscar_por_id(TABELA, acolito_id, "Acolito")
    irmao = buscar_por_id(TABELA, irmao_id, "Acolito")

    grupo = acolito.get("grupo_familiar_id") or irmao.get("grupo_familiar_id")
    if grupo is None:
        grupo = _proximo_grupo_familiar()
    grupo = int(grupo)

    alvos = [
        registro["id"]
        for registro in (acolito, irmao)
        if registro.get("grupo_familiar_id") != grupo
    ]
    for alvo in alvos:
        executar(
            supabase.table(TABELA).update({"grupo_familiar_id": grupo}).eq("id", alvo),
            "vincular irmaos",
        )

    return {"grupo_familiar_id": grupo, "acolitos": [acolito_id, irmao_id]}


@router.delete("/{acolito_id}/vinculo", status_code=status.HTTP_204_NO_CONTENT)
def desvincular(acolito_id: str, _=Depends(require_coordenador)) -> None:
    buscar_por_id(TABELA, acolito_id, "Acolito")
    executar(
        supabase.table(TABELA).update({"grupo_familiar_id": None}).eq("id", acolito_id),
        "remover vinculo familiar",
    )
