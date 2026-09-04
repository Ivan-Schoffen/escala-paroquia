"""Calculo do tempo liturgico romano (RF07).

O calendario liturgico e movel: quase tudo orbita a data da Pascoa, que
depende de ciclos lunares. Em vez de consumir uma API externa (e depender
dela estar no ar toda vez que o coordenador gera uma escala), tudo e
calculado localmente a partir do algoritmo de Computus.

O que este modulo cobre e o **tempo liturgico** e a **semana** — que e
exatamente o que a especificacao pede para o cabecalho das missas, algo como
"3o Domingo do Tempo Comum". Solenidades locais e festas de padroeiro
continuam sendo responsabilidade do calendario de excecoes, onde o
coordenador cadastra o titulo a mao.

Segue o calendario proprio do Brasil em dois pontos: Epifania transferida
para o domingo entre 2 e 8 de janeiro, e Ascensao transferida para o domingo.
"""

from datetime import date, timedelta

_DOMINGO = 6  # date.weekday(): segunda = 0, domingo = 6


def domingo_de_pascoa(ano: int) -> date:
    """Algoritmo de Computus (versao gregoriana anonima)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def _domingo_em_ou_apos(d: date) -> date:
    return d + timedelta(days=(_DOMINGO - d.weekday()) % 7)


def _domingo_em_ou_antes(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def primeiro_domingo_advento(ano: int) -> date:
    """Quarto domingo antes do Natal — inicia o ano liturgico."""
    natal = date(ano, 12, 25)
    return natal - timedelta(days=(natal.weekday() + 1) % 7 + 21)


def epifania(ano: int) -> date:
    """No Brasil, transferida para o domingo entre 2 e 8 de janeiro."""
    return _domingo_em_ou_apos(date(ano, 1, 2))


def batismo_do_senhor(ano: int) -> date:
    """Encerra o Tempo do Natal.

    Domingo seguinte a Epifania; quando a Epifania cai em 7 ou 8 de janeiro,
    passa para a segunda-feira imediata.
    """
    dia_epifania = epifania(ano)
    if dia_epifania.day >= 7:
        return dia_epifania + timedelta(days=1)
    return dia_epifania + timedelta(days=7)


def _ordinal(numero: int, feminino: bool) -> str:
    return f"{numero}{'a' if feminino else 'o'}"


def _rotulo(numero: int, tempo: str, e_domingo: bool) -> str:
    if e_domingo:
        return f"{_ordinal(numero, False)} Domingo {tempo}"
    return f"{_ordinal(numero, True)} Semana {tempo}"


def descrever(dia: date) -> str:
    """Devolve o tempo liturgico do dia, ex: `"3o Domingo do Tempo Comum"`."""

    pascoa = domingo_de_pascoa(dia.year)
    cinzas = pascoa - timedelta(days=46)
    ramos = pascoa - timedelta(days=7)
    quinta_santa = pascoa - timedelta(days=3)
    pentecostes = pascoa + timedelta(days=49)

    advento_deste_ano = primeiro_domingo_advento(dia.year)
    batismo = batismo_do_senhor(dia.year)
    e_domingo = dia.weekday() == _DOMINGO

    # --- Advento e Natal (fim do ano civil) --------------------------------
    if dia >= advento_deste_ano:
        if dia < date(dia.year, 12, 25):
            semana = (dia - advento_deste_ano).days // 7 + 1
            return _rotulo(semana, "do Advento", e_domingo)
        if dia == date(dia.year, 12, 25):
            return "Natal do Senhor"
        return "Tempo do Natal"

    # --- Natal que atravessa a virada do ano -------------------------------
    if dia < batismo:
        if dia == date(dia.year, 1, 1):
            return "Santa Maria, Mae de Deus"
        if dia == epifania(dia.year):
            return "Epifania do Senhor"
        return "Tempo do Natal"

    if dia == batismo:
        return "Batismo do Senhor"

    # --- Tempo Comum, primeira parte ---------------------------------------
    if dia < cinzas:
        # A semana do Batismo e a 1a do Tempo Comum; o domingo seguinte ja e
        # o 2o Domingo do Tempo Comum.
        primeira = _domingo_em_ou_antes(batismo)
        semana = (_domingo_em_ou_antes(dia) - primeira).days // 7 + 1
        return _rotulo(semana, "do Tempo Comum", e_domingo)

    # --- Quaresma -----------------------------------------------------------
    if dia < quinta_santa:
        if dia == cinzas:
            return "Quarta-feira de Cinzas"
        if dia == ramos:
            return "Domingo de Ramos"
        if dia > ramos:
            return "Semana Santa"
        if dia < cinzas + timedelta(days=4):
            return "Apos as Cinzas"
        primeiro_domingo = _domingo_em_ou_apos(cinzas)
        semana = (_domingo_em_ou_antes(dia) - primeiro_domingo).days // 7 + 1
        return _rotulo(semana, "da Quaresma", e_domingo)

    # --- Triduo Pascal ------------------------------------------------------
    if dia < pascoa:
        return {
            quinta_santa: "Quinta-feira Santa",
            pascoa - timedelta(days=2): "Sexta-feira Santa",
            pascoa - timedelta(days=1): "Sabado Santo",
        }[dia]

    # --- Tempo Pascal -------------------------------------------------------
    if dia <= pentecostes:
        if dia == pascoa:
            return "Domingo de Pascoa"
        if dia < pascoa + timedelta(days=7):
            return "Oitava da Pascoa"
        if dia == pentecostes:
            return "Domingo de Pentecostes"
        semana = (_domingo_em_ou_antes(dia) - pascoa).days // 7 + 1
        # No Brasil a Ascensao e transferida para o 7o Domingo da Pascoa.
        if e_domingo and semana == 7:
            return "Ascensao do Senhor"
        return _rotulo(semana, "da Pascoa", e_domingo)

    # --- Tempo Comum, segunda parte ----------------------------------------
    # A numeracao aqui e contada de tras para frente: a ultima semana antes do
    # Advento e sempre a 34a.
    if dia == pascoa + timedelta(days=56):
        return "Santissima Trindade"
    if dia == pascoa + timedelta(days=60):
        return "Corpus Christi"

    ultimo_domingo = advento_deste_ano - timedelta(days=7)
    if dia == ultimo_domingo:
        return "Nosso Senhor Jesus Cristo, Rei do Universo"

    semana = 34 - (ultimo_domingo - _domingo_em_ou_antes(dia)).days // 7
    return _rotulo(semana, "do Tempo Comum", e_domingo)