"""API do Sistema de Escalas Paroquiais.

Este arquivo so monta a aplicacao. As rotas vivem em `routers/` e as regras
de negocio em `services/`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import origens_cors
from routers import acolitos, escalas, excecoes, igrejas, missas, publico

app = FastAPI(
    title="API Escala de Acolitos",
    version="2.0",
    description=(
        "Backend do sistema de escalas paroquiais: cadastros, calendario "
        "liturgico e motor de sorteio."
    ),
)

# O frontend roda em outro dominio (Vercel), entao o navegador so aceita as
# respostas se a origem estiver liberada aqui.
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens_cors(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(publico.router)
app.include_router(igrejas.router)
app.include_router(acolitos.router)
app.include_router(missas.router)
app.include_router(excecoes.router)
app.include_router(escalas.router)


@app.get("/", tags=["Status"])
def read_root() -> dict:
    return {"status": "API da Paroquia rodando com sucesso!", "banco": "Conectado"}
