"""Autenticacao do coordenador via Supabase Auth.

O login em si acontece no frontend (`supabase.auth.signInWithPassword`), que
recebe um JWT. Este modulo so valida esse token nas rotas protegidas: o
backend nunca ve nem guarda a senha do coordenador.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import supabase

# auto_error=False para devolvermos a mensagem em portugues no lugar do
# "Not authenticated" padrao do FastAPI.
_bearer = HTTPBearer(auto_error=False)

_NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Acesso restrito a coordenacao. Faca login para continuar.",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_coordenador(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Valida o `Authorization: Bearer <token>` e devolve o usuario logado.

    Usar como dependencia em toda rota de escrita e em tudo que pertence ao
    painel administrativo.
    """
    if credenciais is None or not credenciais.credentials:
        raise _NAO_AUTENTICADO

    try:
        resposta = supabase.auth.get_user(credenciais.credentials)
    except Exception:
        # Token expirado, assinatura invalida ou Supabase fora do ar.
        raise _NAO_AUTENTICADO

    if resposta is None or resposta.user is None:
        raise _NAO_AUTENTICADO

    return {"id": resposta.user.id, "email": resposta.user.email}