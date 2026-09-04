"""CRUD das missas padrao — os "moldes" da rotina semanal (RF03)."""

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
from schemas import MissaPadraoCreate, MissaPadraoUpdate

router = APIRouter(prefix="/missas-padrao", tags=["Missas Padrao"])

TABELA = "missas_padrao"


@router.get("/")
def listar_missas(igreja_id: Optional[str] = None) -> list[dict]:
    consulta = supabase.table(TABELA).select("*").order("dia_semana").order("horario")
    if igreja_id:
        consulta = consulta.eq("igreja_id", igreja_id)
    return executar(consulta, "listar missas padrao")


@router.get("/{missa_id}")
def obter_missa(missa_id: str) -> dict:
    return buscar_por_id(TABELA, missa_id, "Missa padrao")


@router.post("/", status_code=status.HTTP_201_CREATED)
def criar_missa(
    missa: MissaPadraoCreate,
    _=Depends(require_coordenador),
) -> dict:
    buscar_por_id("igrejas", missa.igreja_id, "Igreja")
    registros = executar(
        supabase.table(TABELA).insert(serializar(missa.model_dump())),
        "cadastrar missa padrao",
    )
    return um_ou_404(registros, "Missa padrao")


@router.put("/{missa_id}")
def atualizar_missa(
    missa_id: str,
    missa: MissaPadraoUpdate,
    _=Depends(require_coordenador),
) -> dict:
    dados = campos_preenchidos(missa)
    if not dados:
        return buscar_por_id(TABELA, missa_id, "Missa padrao")
    buscar_por_id(TABELA, missa_id, "Missa padrao")

    registros = executar(
        supabase.table(TABELA).update(serializar(dados)).eq("id", missa_id),
        "atualizar missa padrao",
    )
    return um_ou_404(registros, "Missa padrao")


@router.delete("/{missa_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_missa(missa_id: str, _=Depends(require_coordenador)) -> None:
    buscar_por_id(TABELA, missa_id, "Missa padrao")
    executar(
        supabase.table(TABELA).delete().eq("id", missa_id),
        "remover missa padrao",
    )
