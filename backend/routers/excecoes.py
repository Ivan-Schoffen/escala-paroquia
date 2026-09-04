"""CRUD do calendario de excecoes — solenidades e festas (RF05)."""

from typing import Optional

from fastapi import APIRouter, Depends, status

from auth import require_coordenador
from database import supabase
from db_utils import (
    buscar_por_id,
    campos_preenchidos,
    executar,
    serializar,
    um_ou_404,
)
from schemas import ExcecaoCreate, ExcecaoUpdate

router = APIRouter(prefix="/excecoes", tags=["Calendario de Excecoes"])

TABELA = "calendario_excecoes"


@router.get("/")
def listar_excecoes(
    igreja_id: Optional[str] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None,
) -> list[dict]:
    consulta = supabase.table(TABELA).select("*").order("data_exata")
    if igreja_id:
        consulta = consulta.eq("igreja_id", igreja_id)
    if mes and ano:
        primeiro = f"{ano}-{mes:02d}-01"
        ultimo = f"{ano + (mes == 12)}-{(mes % 12) + 1:02d}-01"
        consulta = consulta.gte("data_exata", primeiro).lt("data_exata", ultimo)
    return executar(consulta, "listar excecoes")


@router.get("/{excecao_id}")
def obter_excecao(excecao_id: str) -> dict:
    return buscar_por_id(TABELA, excecao_id, "Excecao")


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_excecao(
    excecao: ExcecaoCreate,
    _=Depends(require_coordenador),
) -> dict:
    buscar_por_id("igrejas", excecao.igreja_id, "Igreja")
    registros = executar(
        supabase.table(TABELA).insert(serializar(excecao.model_dump())),
        "cadastrar excecao",
    )
    return um_ou_404(registros, "Excecao")


@router.put("/{excecao_id}")
def atualizar_excecao(
    excecao_id: str,
    excecao: ExcecaoUpdate,
    _=Depends(require_coordenador),
) -> dict:
    dados = campos_preenchidos(excecao)
    if not dados:
        return buscar_por_id(TABELA, excecao_id, "Excecao")
    buscar_por_id(TABELA, excecao_id, "Excecao")

    registros = executar(
        supabase.table(TABELA).update(serializar(dados)).eq("id", excecao_id),
        "atualizar excecao",
    )
    return um_ou_404(registros, "Excecao")


@router.delete("/{excecao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_excecao(excecao_id: str, _=Depends(require_coordenador)) -> None:
    buscar_por_id(TABELA, excecao_id, "Excecao")
    executar(
        supabase.table(TABELA).delete().eq("id", excecao_id),
        "remover excecao",
    )
