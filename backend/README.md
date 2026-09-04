# Backend — API Escala de Acólitos

FastAPI + Supabase (PostgreSQL). Responsável pelos cadastros, pelo cálculo do
tempo litúrgico e pelo motor de sorteio.

## Como rodar

```powershell
cd backend
.\venv\Scripts\Activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Documentação interativa (Swagger): http://localhost:8000/docs

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha. O `.env` está no `.gitignore` e
**nunca** deve ser commitado.

## Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | Monta o app, CORS e registra os routers |
| `config.py` | Fuso da paróquia, formato de `mes_ano_referencia`, origens CORS |
| `database.py` | Cliente Supabase |
| `auth.py` | Valida o JWT do Supabase Auth nas rotas protegidas |
| `schemas.py` | Modelos Pydantic de entrada |
| `db_utils.py` | Helpers de consulta, 404 e serialização |
| `routers/` | Uma rota por entidade + `escalas.py` (fábrica) e `publico.py` |
| `services/liturgico.py` | Computus e tempos litúrgicos (RF07) |
| `services/geocoding.py` | ViaCEP + Nominatim → lat/lng (RN03) |
| `services/sorteio.py` | Motor de sorteio (RN01–RN04) |
| `services/apresentacao.py` | Agrupa a escala no formato que as telas consomem |
| `sql/` | Scripts a rodar no SQL Editor do Supabase |

## Autenticação

O login acontece no **frontend**, via `supabase.auth.signInWithPassword`. O
backend só valida o token: toda rota de escrita exige o header
`Authorization: Bearer <access_token>`.

Para testar pelo Swagger, use o botão **Authorize** e cole o `access_token`.
Crie o usuário do coordenador no painel do Supabase em
*Authentication → Users → Add user*.

## Rotas abertas (sem login)

- `GET /` — status
- `GET /publico/escala` — escala publicada do mês vigente (RF01)

Todas as demais rotas de escrita são protegidas.

## Testes

```powershell
.\venv\Scripts\python.exe -m tests.test_sorteio
```

Cobrem o motor de sorteio e o calendário litúrgico sem tocar no banco:
sobreposição de exceções (RN04), irmãos em bloco (RN02), balanceamento
mensal (RN01), desempate por distância (RN03), vagas não preenchidas e as
datas móveis do ano litúrgico.
