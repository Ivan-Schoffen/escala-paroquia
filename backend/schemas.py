"""Modelos Pydantic usados para validar a entrada e a saida da API."""

from datetime import date, time
from typing import Literal, Optional

from pydantic import BaseModel, Field

# As tres classificacoes da especificacao. Os valores batem exatamente com o
# CHECK constraint das tabelas no Supabase.
Classificacao = Literal["Responsavel", "Maior", "Menor"]


class EnderecoBase(BaseModel):
    """Endereco estruturado, separado em campos para a geocodificacao funcionar.

    Endereco em texto livre confunde o Nominatim com abreviacoes e erros de
    digitacao; por isso a especificacao pede os campos separados.
    """

    tipo_via: Optional[str] = None
    logradouro: str
    numero: str
    cep: str
    bairro: Optional[str] = None


# --------------------------------------------------------------------------
# Igrejas
# --------------------------------------------------------------------------


class IgrejaCreate(EnderecoBase):
    nome_igreja: str


class IgrejaUpdate(BaseModel):
    nome_igreja: Optional[str] = None
    tipo_via: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None


# --------------------------------------------------------------------------
# Acolitos
# --------------------------------------------------------------------------


class AcolitoCreate(EnderecoBase):
    nome_completo: str
    classificacao: Classificacao
    grupo_familiar_id: Optional[int] = None


class AcolitoUpdate(BaseModel):
    nome_completo: Optional[str] = None
    classificacao: Optional[Classificacao] = None
    grupo_familiar_id: Optional[int] = None
    tipo_via: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None
    ativo: Optional[bool] = None


# --------------------------------------------------------------------------
# Missas padrao (os "moldes" da rotina semanal)
# --------------------------------------------------------------------------


class MissaPadraoCreate(BaseModel):
    igreja_id: str
    dia_semana: int = Field(ge=0, le=6, description="0 = Domingo, 6 = Sabado")
    horario: time
    vagas_responsavel: int = Field(default=1, ge=0)
    vagas_maior: int = Field(default=0, ge=0)
    vagas_menor: int = Field(default=0, ge=0)


class MissaPadraoUpdate(BaseModel):
    igreja_id: Optional[str] = None
    dia_semana: Optional[int] = Field(default=None, ge=0, le=6)
    horario: Optional[time] = None
    vagas_responsavel: Optional[int] = Field(default=None, ge=0)
    vagas_maior: Optional[int] = Field(default=None, ge=0)
    vagas_menor: Optional[int] = Field(default=None, ge=0)
    ativo: Optional[bool] = None


# --------------------------------------------------------------------------
# Calendario de excecoes (solenidades e festas)
# --------------------------------------------------------------------------


class ExcecaoCreate(BaseModel):
    igreja_id: str
    data_exata: date
    horario: time
    titulo_evento: str
    vagas_responsavel: int = Field(default=1, ge=0)
    vagas_maior: int = Field(default=0, ge=0)
    vagas_menor: int = Field(default=0, ge=0)
    substitui_rotina: bool = True


class ExcecaoUpdate(BaseModel):
    igreja_id: Optional[str] = None
    data_exata: Optional[date] = None
    horario: Optional[time] = None
    titulo_evento: Optional[str] = None
    vagas_responsavel: Optional[int] = Field(default=None, ge=0)
    vagas_maior: Optional[int] = Field(default=None, ge=0)
    vagas_menor: Optional[int] = Field(default=None, ge=0)
    substitui_rotina: Optional[bool] = None


# --------------------------------------------------------------------------
# Escalas
# --------------------------------------------------------------------------


class GerarEscalaRequest(BaseModel):
    mes: int = Field(ge=1, le=12)
    ano: int = Field(ge=2000, le=2100)
    usar_geolocalizacao: bool = False


class TrocaAcolitoRequest(BaseModel):
    acolito_id: str
