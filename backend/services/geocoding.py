"""Converte o endereco estruturado em coordenadas (lat/lng).

Duas etapas, ambas gratuitas e sem chave de API:

1. **ViaCEP** normaliza o endereco a partir do CEP, devolvendo logradouro,
   bairro, cidade e UF oficiais. Isso conserta abreviacoes e erros de
   digitacao antes de qualquer busca.
2. **Nominatim** (OpenStreetMap) transforma o endereco normalizado em
   latitude e longitude.

As coordenadas alimentam o desempate por distancia do sorteio (RN03). Como
esse criterio e opcional, uma falha aqui **nunca** derruba o cadastro: o
acolito ou a igreja e salvo com lat/lng nulos e simplesmente nao participa do
desempate geografico.
"""

import os
import re
import threading
import time
from typing import Optional

import httpx

_VIACEP = "https://viacep.com.br/ws/{cep}/json/"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"

_TIMEOUT = 8.0

# A politica de uso do Nominatim exige identificacao real e no maximo uma
# requisicao por segundo. Um lock global serializa as chamadas: o cadastro e
# uma acao pontual do coordenador, entao esperar um instante nao incomoda.
_INTERVALO_MINIMO = 1.1
_lock = threading.Lock()
_ultima_chamada = 0.0


def _user_agent() -> str:
    return os.getenv("GEOCODING_USER_AGENT", "escala-paroquia/1.0")


def _so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _consultar_viacep(cep: str) -> Optional[dict]:
    cep_limpo = _so_digitos(cep)
    if len(cep_limpo) != 8:
        return None
    try:
        resposta = httpx.get(_VIACEP.format(cep=cep_limpo), timeout=_TIMEOUT)
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception:
        return None
    # O ViaCEP responde 200 com {"erro": true} quando o CEP nao existe.
    if not isinstance(dados, dict) or dados.get("erro"):
        return None
    return dados


def _consultar_nominatim(parametros: dict) -> Optional[tuple[float, float]]:
    global _ultima_chamada
    try:
        with _lock:
            espera = _INTERVALO_MINIMO - (time.monotonic() - _ultima_chamada)
            if espera > 0:
                time.sleep(espera)
            resposta = httpx.get(
                _NOMINATIM,
                params={**parametros, "format": "json", "limit": 1},
                headers={"User-Agent": _user_agent()},
                timeout=_TIMEOUT,
            )
            _ultima_chamada = time.monotonic()
        resposta.raise_for_status()
        resultados = resposta.json()
    except Exception:
        return None

    if not resultados:
        return None
    try:
        return float(resultados[0]["lat"]), float(resultados[0]["lon"])
    except (KeyError, ValueError, TypeError):
        return None


def geocodificar(
    *,
    tipo_via: Optional[str],
    logradouro: str,
    numero: str,
    cep: str,
    bairro: Optional[str],
) -> tuple[Optional[float], Optional[float]]:
    """Devolve `(lat, lng)` do endereco, ou `(None, None)` se nao encontrar."""

    viacep = _consultar_viacep(cep)

    rua = (viacep or {}).get("logradouro") or " ".join(
        p for p in (tipo_via, logradouro) if p
    )
    cidade = (viacep or {}).get("localidade")
    uf = (viacep or {}).get("uf")

    # Busca estruturada primeiro: e bem mais precisa que texto livre.
    coordenadas = _consultar_nominatim(
        {
            "street": f"{numero} {rua}".strip(),
            "city": cidade or "",
            "state": uf or "",
            "postalcode": _so_digitos(cep),
            "country": "Brasil",
        }
    )
    if coordenadas:
        return coordenadas

    # Sem resultado exato, cai para o centro do bairro/cidade. A precisao e
    # menor, mas ainda serve para ordenar por proximidade.
    partes = [
        p
        for p in (rua, bairro or (viacep or {}).get("bairro"), cidade, uf, "Brasil")
        if p
    ]
    coordenadas = _consultar_nominatim({"q": ", ".join(partes)})
    if coordenadas:
        return coordenadas

    return None, None


def preencher_coordenadas(dados: dict) -> dict:
    """Adiciona `lat`/`lng` ao dicionario quando o endereco esta completo.

    Usado pelos CRUDs de igrejas e acolitos. Em um update parcial, so vale a
    pena consultar as APIs se algum campo de endereco realmente mudou.
    """
    campos = ("tipo_via", "logradouro", "numero", "cep", "bairro")
    if not any(campo in dados for campo in campos):
        return dados
    if not dados.get("logradouro") or not dados.get("cep"):
        return dados

    lat, lng = geocodificar(
        tipo_via=dados.get("tipo_via"),
        logradouro=dados["logradouro"],
        numero=dados.get("numero", ""),
        cep=dados["cep"],
        bairro=dados.get("bairro"),
    )
    dados["lat"] = lat
    dados["lng"] = lng
    return dados
