"""CRUD de igrejas — matriz e capelas (RF03)."""

from fastapi import APIRouter, Depends, status

from auth import require_coordenador
from database import supabase
from db_utils import buscar_por_id, campos_preenchidos, executar, um_ou_404
from schemas import IgrejaCreate, IgrejaUpdate
from services.geocoding import preencher_coordenadas

router = APIRouter(prefix="/igrejas", tags=["Igrejas"])

TABELA = "igrejas"


@router.get("/")
def listar_igrejas() -> list[dict]:
    return executar(
        supabase.table(TABELA).select("*").order("nome_igreja"),
        "listar igrejas",
    )


@router.get("/{igreja_id}")
def obter_igreja(igreja_id: str) -> dict:
    return buscar_por_id(TABELA, igreja_id, "Igreja")


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_igreja(
    igreja: IgrejaCreate,
    _=Depends(require_coordenador),
) -> dict:
    dados = preencher_coordenadas(igreja.model_dump())
    registros = executar(supabase.table(TABELA).insert(dados), "cadastrar igreja")
    return um_ou_404(registros, "Igreja")


@router.put("/{igreja_id}")
def atualizar_igreja(
    igreja_id: str,
    igreja: IgrejaUpdate,
    _=Depends(require_coordenador),
) -> dict:
    dados = campos_preenchidos(igreja)
    if not dados:
        return buscar_por_id(TABELA, igreja_id, "Igreja")

    # O endereco parcial precisa ser combinado com o que ja esta salvo, senao
    # a geocodificacao rodaria com metade dos campos.
    atual = buscar_por_id(TABELA, igreja_id, "Igreja")
    dados = preencher_coordenadas({**atual, **dados})
    dados.pop("id", None)
    dados.pop("criado_em", None)

    registros = executar(
        supabase.table(TABELA).update(dados).eq("id", igreja_id),
        "atualizar igreja",
    )
    return um_ou_404(registros, "Igreja")


@router.delete("/{igreja_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_igreja(igreja_id: str, _=Depends(require_coordenador)) -> None:
    buscar_por_id(TABELA, igreja_id, "Igreja")
    executar(supabase.table(TABELA).delete().eq("id", igreja_id), "remover igreja")
