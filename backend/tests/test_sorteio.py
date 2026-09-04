"""Testes do motor de sorteio e do calendario liturgico.

Nao dependem do Supabase: o modulo `services.sorteio` e puro, recebe listas de
dicionarios e devolve o resultado em memoria. Rodar com:

    cd backend
    .\\venv\\Scripts\\python.exe -m tests.test_sorteio
"""

import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services import liturgico, sorteio  # noqa: E402

MATRIZ = "igreja-matriz"
CAPELA = "igreja-capela"

IGREJAS = [
    {"id": MATRIZ, "nome_igreja": "Matriz Sao Jose", "lat": -25.43, "lng": -49.27},
    {"id": CAPELA, "nome_igreja": "Capela Santa Rita", "lat": -25.50, "lng": -49.30},
]

# Domingo = 0 e Sabado = 6, como no banco.
MISSAS_PADRAO = [
    {
        "id": "m1",
        "igreja_id": MATRIZ,
        "dia_semana": 0,
        "horario": "08:00:00",
        "vagas_responsavel": 1,
        "vagas_maior": 2,
        "vagas_menor": 2,
        "ativo": True,
    },
    {
        "id": "m2",
        "igreja_id": CAPELA,
        "dia_semana": 6,
        "horario": "19:00:00",
        "vagas_responsavel": 1,
        "vagas_maior": 1,
        "vagas_menor": 1,
        "ativo": True,
    },
    {
        "id": "m3",
        "igreja_id": CAPELA,
        "dia_semana": 3,
        "horario": "19:30:00",
        "vagas_responsavel": 1,
        "vagas_maior": 1,
        "vagas_menor": 0,
        "ativo": False,  # desativada: nao pode aparecer na escala
    },
]

# 2026-08-02 e um domingo: a solenidade anula a missa das 8h na Matriz.
EXCECOES = [
    {
        "id": "e1",
        "igreja_id": MATRIZ,
        "data_exata": "2026-08-02",
        "horario": "19:30:00",
        "titulo_evento": "Solenidade da Padroeira",
        "vagas_responsavel": 2,
        "vagas_maior": 2,
        "vagas_menor": 2,
        "substitui_rotina": True,
    }
]


def _acolito(identificador, nome, classificacao, grupo=None, lat=None, lng=None):
    return {
        "id": identificador,
        "nome_completo": nome,
        "classificacao": classificacao,
        "grupo_familiar_id": grupo,
        "lat": lat,
        "lng": lng,
        "ativo": True,
    }


# Joao e Pedro sao irmaos (grupo 1) e ambos "Maior", entao sempre existe vaga
# compativel para os dois quando um deles e sorteado.
ACOLITOS = [
    _acolito("r1", "Carlos", "Responsavel"),
    _acolito("r2", "Marcos", "Responsavel"),
    _acolito("r3", "Antonio", "Responsavel"),
    _acolito("a1", "Joao", "Maior", grupo=1),
    _acolito("a2", "Pedro", "Maior", grupo=1),
    _acolito("a3", "Lucas", "Maior"),
    _acolito("a4", "Tiago", "Maior"),
    _acolito("a5", "Mateus", "Maior"),
    _acolito("a6", "Andre", "Maior"),
    _acolito("n1", "Gabriel", "Menor"),
    _acolito("n2", "Rafael", "Menor"),
    _acolito("n3", "Miguel", "Menor"),
    _acolito("n4", "Bento", "Menor"),
    _acolito("n5", "Davi", "Menor"),
    _acolito("n6", "Enzo", "Menor"),
]


def _rodar(usar_geolocalizacao=False):
    return sorteio.gerar(
        mes=8,
        ano=2026,
        missas_padrao=MISSAS_PADRAO,
        excecoes=EXCECOES,
        acolitos=ACOLITOS,
        igrejas=IGREJAS,
        usar_geolocalizacao=usar_geolocalizacao,
    )


def testar_excecao_sobrepoe_rotina():
    """RN04 — a solenidade anula o molde da missa padrao naquele dia."""
    celebracoes = _rodar()
    no_dia = [c for c in celebracoes if c.data_hora.date() == date(2026, 8, 2)]
    na_matriz = [c for c in no_dia if c.igreja_id == MATRIZ]

    assert len(na_matriz) == 1, f"esperava 1 celebracao na Matriz, veio {len(na_matriz)}"
    assert na_matriz[0].data_hora.strftime("%H:%M") == "19:30"
    assert na_matriz[0].titulo_evento == "Solenidade da Padroeira"
    assert na_matriz[0].vagas == {"Responsavel": 2, "Maior": 2, "Menor": 2}

    # Os outros domingos seguem a rotina das 8h.
    outros_domingos = [
        c
        for c in celebracoes
        if c.igreja_id == MATRIZ and c.data_hora.date() != date(2026, 8, 2)
    ]
    assert outros_domingos, "a rotina dos demais domingos sumiu"
    assert all(c.data_hora.strftime("%H:%M") == "08:00" for c in outros_domingos)


def testar_missa_desativada_nao_entra():
    celebracoes = _rodar()
    quartas = [c for c in celebracoes if c.data_hora.weekday() == 2]
    assert not quartas, "a missa marcada como inativa foi escalada"


def testar_irmaos_servem_juntos():
    """RN02 — o fura-fila coloca os vinculados na mesma celebracao."""
    celebracoes = _rodar()
    separados = []
    for celebracao in celebracoes:
        ids = {acolito_id for acolito_id, _ in celebracao.escalados}
        if ("a1" in ids) != ("a2" in ids):
            separados.append(celebracao.data_hora.isoformat())

    assert not separados, f"irmaos escalados separados em: {separados}"


def testar_balanceamento_justo():
    """RN01 — a diferenca entre quem mais e quem menos serviu e no maximo 1."""
    celebracoes = _rodar()
    contagem = Counter()
    for celebracao in celebracoes:
        for acolito_id, _ in celebracao.escalados:
            contagem[acolito_id] += 1

    por_classificacao = {}
    for acolito in ACOLITOS:
        por_classificacao.setdefault(acolito["classificacao"], []).append(
            contagem.get(acolito["id"], 0)
        )

    for classificacao, valores in por_classificacao.items():
        diferenca = max(valores) - min(valores)
        # Os irmaos entram em bloco, entao o par pode ficar 1 missa acima da
        # media dos demais Maiores; 2 e o limite aceitavel nesse caso.
        limite = 2 if classificacao == "Maior" else 1
        assert diferenca <= limite, (
            f"{classificacao} desbalanceado: {sorted(valores)} "
            f"(diferenca {diferenca}, limite {limite})"
        )


def testar_ninguem_em_dois_lugares_ao_mesmo_tempo():
    celebracoes = _rodar()
    por_horario = {}
    for celebracao in celebracoes:
        for acolito_id, _ in celebracao.escalados:
            chave = (celebracao.data_hora, acolito_id)
            por_horario[chave] = por_horario.get(chave, 0) + 1
    repetidos = [k for k, v in por_horario.items() if v > 1]
    assert not repetidos, f"acolito em dois lugares no mesmo horario: {repetidos}"


def testar_vagas_e_funcoes_respeitadas():
    celebracoes = _rodar()
    classificacoes = {a["id"]: a["classificacao"] for a in ACOLITOS}
    for celebracao in celebracoes:
        preenchidas = Counter(funcao for _, funcao in celebracao.escalados)
        for funcao, quantidade in preenchidas.items():
            assert quantidade <= celebracao.vagas[funcao], (
                f"{funcao}: {quantidade} escalados para "
                f"{celebracao.vagas[funcao]} vagas"
            )
        for acolito_id, funcao in celebracao.escalados:
            assert classificacoes[acolito_id] == funcao, (
                f"{acolito_id} e {classificacoes[acolito_id]} mas ocupou "
                f"vaga de {funcao}"
            )
        # Com 3 Responsaveis cadastrados, nenhuma missa pode ficar sem um.
        assert preenchidas["Responsavel"] >= 1, "celebracao sem Responsavel"


def testar_geolocalizacao_desempata():
    """RN03 — com o toggle ligado, quem mora perto ganha o desempate."""
    igrejas = [{"id": MATRIZ, "nome_igreja": "Matriz", "lat": -25.43, "lng": -49.27}]
    missa = [
        {
            "id": "m",
            "igreja_id": MATRIZ,
            "dia_semana": 0,
            "horario": "08:00:00",
            "vagas_responsavel": 0,
            "vagas_maior": 0,
            "vagas_menor": 1,
            "ativo": True,
        }
    ]
    perto = _acolito("perto", "Perto", "Menor", lat=-25.44, lng=-49.28)
    longe = _acolito("longe", "Longe", "Menor", lat=-26.50, lng=-50.30)

    # Um unico domingo isola o desempate: os dois comecam com zero missas.
    celebracoes = sorteio.montar_celebracoes(8, 2026, missa, [])[:1]
    sorteio.alocar(celebracoes, [perto, longe], igrejas, usar_geolocalizacao=True)
    assert celebracoes[0].escalados[0][0] == "perto", "o mais distante foi escolhido"

    # Com o toggle desligado o criterio some e os dois voltam a ser possiveis.
    escolhidos = set()
    for _ in range(30):
        celebracoes = sorteio.montar_celebracoes(8, 2026, missa, [])[:1]
        sorteio.alocar(celebracoes, [perto, longe], igrejas, usar_geolocalizacao=False)
        escolhidos.add(celebracoes[0].escalados[0][0])
    assert escolhidos == {"perto", "longe"}, (
        "com geolocalizacao desligada o sorteio deveria alternar, "
        f"mas escolheu sempre {escolhidos}"
    )


def testar_vagas_nao_preenchidas_sao_reportadas():
    igrejas = [{"id": MATRIZ, "nome_igreja": "Matriz", "lat": None, "lng": None}]
    missa = [
        {
            "id": "m",
            "igreja_id": MATRIZ,
            "dia_semana": 0,
            "horario": "08:00:00",
            "vagas_responsavel": 1,
            "vagas_maior": 5,
            "vagas_menor": 0,
            "ativo": True,
        }
    ]
    elenco = [
        _acolito("r", "Unico Responsavel", "Responsavel"),
        _acolito("a", "Unico Maior", "Maior"),
    ]
    celebracoes = sorteio.montar_celebracoes(8, 2026, missa, [])[:1]
    sorteio.alocar(celebracoes, elenco, igrejas)
    assert celebracoes[0].vagas_vazias == {"Maior": 4}, celebracoes[0].vagas_vazias


def testar_calendario_liturgico():
    esperado = {
        date(2026, 1, 11): "Batismo do Senhor",
        date(2026, 1, 25): "3o Domingo do Tempo Comum",
        date(2026, 2, 18): "Quarta-feira de Cinzas",
        date(2026, 3, 8): "3o Domingo da Quaresma",
        date(2026, 3, 29): "Domingo de Ramos",
        date(2026, 4, 3): "Sexta-feira Santa",
        date(2026, 4, 5): "Domingo de Pascoa",
        date(2026, 5, 24): "Domingo de Pentecostes",
        date(2026, 11, 22): "Nosso Senhor Jesus Cristo, Rei do Universo",
        date(2026, 11, 29): "1o Domingo do Advento",
        date(2026, 12, 25): "Natal do Senhor",
        date(2025, 6, 19): "Corpus Christi",
        date(2025, 7, 6): "14o Domingo do Tempo Comum",
    }
    for dia, texto in esperado.items():
        obtido = liturgico.descrever(dia)
        assert obtido == texto, f"{dia}: esperava '{texto}', veio '{obtido}'"


def main() -> int:
    testes = [valor for nome, valor in globals().items() if nome.startswith("testar_")]
    falhas = 0
    for teste in testes:
        try:
            teste()
        except AssertionError as erro:
            falhas += 1
            print(f"[FALHOU] {teste.__name__}: {erro}")
        else:
            print(f"[ok]     {teste.__name__}")
    print()
    print(f"{len(testes) - falhas}/{len(testes)} testes passaram.")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
