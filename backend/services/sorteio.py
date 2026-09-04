"""Motor de sorteio das escalas (RF06, RN01 a RN04).

O trabalho acontece em duas etapas independentes e testaveis separadamente:

**Etapa A — montar os moldes.** Expande as missas padrao para todos os dias do
mes e deixa o calendario de excecoes sobrescrever os dias de solenidade
(RN04).

**Etapa B — alocar os acolitos.** Para cada vaga, ordena os candidatos por
tres criterios, nessa ordem: menos missas no mes (RN01), menor distancia de
casa ate a igreja (RN03, opcional) e sorteio aleatorio para desempatar. Logo
apos preencher uma vaga, os irmaos do escolhido "furam a fila" e entram na
mesma celebracao (RN02).

Este modulo e puro: recebe os dados ja lidos do banco e devolve o resultado
em memoria, sem escrever nada. Quem persiste e o `routers/escalas.py`.
"""

import calendar
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Iterable, Optional

from config import FUSO_PAROQUIA
from services import liturgico

# O Responsavel vem primeiro porque nenhuma missa pode ficar sem ele (RN02):
# se as pessoas acabarem, e melhor que faltem Maiores ou Menores.
ORDEM_FUNCOES = ("Responsavel", "Maior", "Menor")

_RAIO_TERRA_KM = 6371.0

# Distancia usada para quem nao tem coordenadas. Nao exclui ninguem: o criterio
# 1 (quem serviu menos) continua mandando. So desempata por ultimo dentro do
# mesmo numero de missas.
_DISTANCIA_DESCONHECIDA = float("inf")


@dataclass
class Celebracao:
    """Uma missa concreta do mes, ja com o molde de vagas resolvido."""

    igreja_id: str
    data_hora: datetime
    vagas: dict[str, int]
    tempo_liturgico: str
    titulo_evento: Optional[str] = None
    escalados: list[tuple[str, str]] = field(default_factory=list)
    vagas_vazias: dict[str, int] = field(default_factory=dict)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Menor distancia entre dois pontos do globo, em quilometros."""
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return 2 * _RAIO_TERRA_KM * math.asin(math.sqrt(a))


def _para_time(valor) -> time:
    if isinstance(valor, time):
        return valor
    # O Supabase devolve TIME como string, ex: "08:00:00".
    return time.fromisoformat(str(valor))


def _para_date(valor) -> date:
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    return date.fromisoformat(str(valor)[:10])


def _dia_semana_liturgico(dia: date) -> int:
    """Converte `date.weekday()` (segunda = 0) para a convencao do banco.

    O banco usa 0 = Domingo e 6 = Sabado, como definido na especificacao.
    """
    return (dia.weekday() + 1) % 7


def _vagas(registro: dict) -> dict[str, int]:
    return {
        "Responsavel": int(registro.get("vagas_responsavel") or 0),
        "Maior": int(registro.get("vagas_maior") or 0),
        "Menor": int(registro.get("vagas_menor") or 0),
    }


# --------------------------------------------------------------------------
# Etapa A — montar os moldes do mes
# --------------------------------------------------------------------------


def montar_celebracoes(
    mes: int,
    ano: int,
    missas_padrao: Iterable[dict],
    excecoes: Iterable[dict],
) -> list[Celebracao]:
    """Expande a rotina semanal no mes e aplica as excecoes por cima (RN04)."""

    _, ultimo_dia = calendar.monthrange(ano, mes)
    dias = [date(ano, mes, d) for d in range(1, ultimo_dia + 1)]

    excecoes = list(excecoes)

    # Dias em que a rotina de uma igreja e anulada pela solenidade.
    substituidos: set[tuple[str, date]] = {
        (e["igreja_id"], _para_date(e["data_exata"]))
        for e in excecoes
        if e.get("substitui_rotina", True)
    }

    celebracoes: list[Celebracao] = []

    for missa in missas_padrao:
        if missa.get("ativo") is False:
            continue
        horario = _para_time(missa["horario"])
        for dia in dias:
            if _dia_semana_liturgico(dia) != int(missa["dia_semana"]):
                continue
            if (missa["igreja_id"], dia) in substituidos:
                continue
            celebracoes.append(
                Celebracao(
                    igreja_id=missa["igreja_id"],
                    data_hora=datetime.combine(dia, horario, tzinfo=FUSO_PAROQUIA),
                    vagas=_vagas(missa),
                    tempo_liturgico=liturgico.descrever(dia),
                )
            )

    for excecao in excecoes:
        dia = _para_date(excecao["data_exata"])
        if dia.month != mes or dia.year != ano:
            continue
        celebracoes.append(
            Celebracao(
                igreja_id=excecao["igreja_id"],
                data_hora=datetime.combine(
                    dia, _para_time(excecao["horario"]), tzinfo=FUSO_PAROQUIA
                ),
                vagas=_vagas(excecao),
                tempo_liturgico=liturgico.descrever(dia),
                titulo_evento=excecao.get("titulo_evento"),
            )
        )

    celebracoes.sort(key=lambda c: (c.data_hora, c.igreja_id))
    return celebracoes


# --------------------------------------------------------------------------
# Etapa B — alocar os acolitos
# --------------------------------------------------------------------------


def _irmaos_alocaveis(
    acolito: dict,
    familias: dict[int, list[str]],
    por_id: dict[str, dict],
    disponivel_aqui,
) -> list[dict]:
    """Irmaos do acolito que poderiam entrar nesta celebracao.

    Quem ja esta servindo em outra igreja no mesmo horario fica de fora: nao
    ha o que fazer nesse caso, e exigir a presenca dele travaria o sorteio.
    """
    grupo = acolito.get("grupo_familiar_id")
    if grupo is None:
        return []
    return [
        por_id[irmao_id]
        for irmao_id in familias.get(int(grupo), [])
        if irmao_id != acolito["id"]
        and irmao_id in por_id
        and disponivel_aqui(irmao_id)
    ]


def _bloco_cabe(
    acolito: dict,
    funcao: str,
    restantes: dict[str, int],
    familias: dict[int, list[str]],
    por_id: dict[str, dict],
    disponivel_aqui,
) -> bool:
    """O acolito e todos os irmaos dele cabem nas vagas que sobraram?"""
    irmaos = _irmaos_alocaveis(acolito, familias, por_id, disponivel_aqui)
    if not irmaos:
        return True

    saldo = dict(restantes)
    saldo[funcao] -= 1
    for irmao in irmaos:
        classificacao = irmao["classificacao"]
        saldo[classificacao] = saldo.get(classificacao, 0) - 1
        if saldo[classificacao] < 0:
            return False
    return True


def alocar(
    celebracoes: list[Celebracao],
    acolitos: Iterable[dict],
    igrejas: Iterable[dict],
    usar_geolocalizacao: bool = False,
    contador_inicial: Optional[dict[str, int]] = None,
) -> list[Celebracao]:
    """Preenche as vagas das celebracoes, alterando-as no lugar."""

    ativos = [a for a in acolitos if a.get("ativo") is not False]
    por_id = {a["id"]: a for a in ativos}
    por_funcao: dict[str, list[dict]] = {f: [] for f in ORDEM_FUNCOES}
    for acolito in ativos:
        por_funcao.setdefault(acolito["classificacao"], []).append(acolito)

    # Irmaos: quem compartilha o mesmo grupo_familiar_id.
    familias: dict[int, list[str]] = {}
    for acolito in ativos:
        grupo = acolito.get("grupo_familiar_id")
        if grupo is not None:
            familias.setdefault(int(grupo), []).append(acolito["id"])

    coordenadas_igreja = {
        i["id"]: (i.get("lat"), i.get("lng")) for i in igrejas
    }

    # Contador do mes mantido em memoria (RN01). Consultar o banco a cada vaga
    # seria lento e, pior, daria numeros errados: as alocacoes desta mesma
    # execucao ainda nao foram gravadas.
    contador: dict[str, int] = {a["id"]: 0 for a in ativos}
    if contador_inicial:
        for acolito_id, quantidade in contador_inicial.items():
            if acolito_id in contador:
                contador[acolito_id] = quantidade

    # Ninguem pode servir em duas igrejas no mesmo horario.
    ocupados: dict[datetime, set[str]] = {}

    def distancia(acolito: dict, igreja_id: str) -> float:
        if not usar_geolocalizacao:
            return 0.0
        lat_igreja, lng_igreja = coordenadas_igreja.get(igreja_id, (None, None))
        lat, lng = acolito.get("lat"), acolito.get("lng")
        if None in (lat, lng, lat_igreja, lng_igreja):
            return _DISTANCIA_DESCONHECIDA
        return haversine_km(float(lat), float(lng), float(lat_igreja), float(lng_igreja))

    def disponivel(acolito_id: str, celebracao: Celebracao, ja: set[str]) -> bool:
        if acolito_id in ja:
            return False
        return acolito_id not in ocupados.get(celebracao.data_hora, set())

    for celebracao in celebracoes:
        restantes = dict(celebracao.vagas)
        ja_escalados: set[str] = set()

        def disponivel_aqui(acolito_id: str) -> bool:
            return disponivel(acolito_id, celebracao, ja_escalados)

        def escalar(acolito_id: str, funcao: str) -> None:
            celebracao.escalados.append((acolito_id, funcao))
            ja_escalados.add(acolito_id)
            restantes[funcao] -= 1
            contador[acolito_id] += 1
            ocupados.setdefault(celebracao.data_hora, set()).add(acolito_id)

        for funcao in ORDEM_FUNCOES:
            while restantes.get(funcao, 0) > 0:
                candidatos = [
                    a
                    for a in por_funcao.get(funcao, [])
                    if disponivel(a["id"], celebracao, ja_escalados)
                ]
                if not candidatos:
                    break

                # Embaralhar antes de ordenar transforma o sort estavel do
                # Python no criterio 3 (aleatorio) de graca: quem empata em
                # missas e distancia sai em ordem imprevisivel.
                random.shuffle(candidatos)
                candidatos.sort(
                    key=lambda a: (contador[a["id"]], distancia(a, celebracao.igreja_id))
                )

                # Irmaos entram ou saem em bloco: se a celebracao nao tem vaga
                # para todos, o motor pula o grupo inteiro e procura o proximo
                # do ranking. Sem isso, uma missa com uma unica vaga de Maior
                # separaria os irmaos toda semana.
                escolhido = next(
                    (
                        a
                        for a in candidatos
                        if _bloco_cabe(a, funcao, restantes, familias, por_id, disponivel_aqui)
                    ),
                    # Se nenhum bloco couber, preencher a vaga ainda e melhor
                    # do que deixa-la vazia.
                    candidatos[0],
                )
                escalar(escolhido["id"], funcao)

                # RN02 — fura-fila dos irmaos: o ranking e suspenso para
                # encaixar os vinculados na mesma celebracao, cada um na vaga
                # compativel com a sua propria classificacao.
                for irmao in _irmaos_alocaveis(
                    escolhido, familias, por_id, disponivel_aqui
                ):
                    funcao_irmao = irmao["classificacao"]
                    if restantes.get(funcao_irmao, 0) <= 0:
                        continue
                    escalar(irmao["id"], funcao_irmao)

        celebracao.vagas_vazias = {f: q for f, q in restantes.items() if q > 0}

    return celebracoes


def gerar(
    mes: int,
    ano: int,
    missas_padrao: Iterable[dict],
    excecoes: Iterable[dict],
    acolitos: Iterable[dict],
    igrejas: Iterable[dict],
    usar_geolocalizacao: bool = False,
) -> list[Celebracao]:
    """Atalho que roda as duas etapas em sequencia."""
    celebracoes = montar_celebracoes(mes, ano, missas_padrao, excecoes)
    return alocar(celebracoes, acolitos, igrejas, usar_geolocalizacao)