"""Proteção das rotas: login, somente leitura na demonstração e cabeçalhos de segurança."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from .config import Configuracoes
from .seguranca import LimitadorDeRequisicoes, ServicoDeAutenticacao

COOKIE_DE_SESSAO = "prumo_sessao"
ROTAS_PUBLICAS = {"/login", "/api/login", "/healthz", "/favicon.ico"}
PREFIXOS_PUBLICOS = ("/assets/",)
METODOS_DE_LEITURA = {"GET", "HEAD", "OPTIONS"}
ROTAS_LIBERADAS_NA_DEMO = {"/api/login", "/api/logout"}

# Sem scripts nem estilos embutidos e sem recursos de terceiros: tudo vem do próprio servidor.
POLITICA_DE_CONTEUDO = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
# A documentação interativa (/docs) usa scripts de um CDN, então fica de fora da política acima.
CAMINHOS_SEM_POLITICA = ("/docs", "/redoc", "/openapi.json")


class ProtecaoMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, config: Configuracoes, autenticacao: ServicoDeAutenticacao, limitador: LimitadorDeRequisicoes):
        super().__init__(app)
        self._config = config
        self._autenticacao = autenticacao
        self._limitador = limitador

    # ------------------------------------------------------------------ decisões
    def _barrar_na_demo(self, request: Request, caminho: str) -> Response | None:
        if not caminho.startswith("/api/"):
            return None
        if request.method not in METODOS_DE_LEITURA and caminho not in ROTAS_LIBERADAS_NA_DEMO:
            return JSONResponse({"detail": "Modo demonstração: somente leitura. Nada pode ser alterado."}, status_code=403)
        ip = request.client.host if request.client else "?"
        if self._limitador.excedeu(ip):
            return JSONResponse({"detail": "Muitas requisições. Aguarde um instante."}, status_code=429)
        return None

    def _barrar_sem_login(self, request: Request, caminho: str) -> Response | None:
        publica = caminho in ROTAS_PUBLICAS or caminho.startswith(PREFIXOS_PUBLICOS)
        if publica or self._autenticacao.assinador.valido(request.cookies.get(COOKIE_DE_SESSAO)):
            return None
        if caminho.startswith("/api/"):
            return JSONResponse({"detail": "Não autenticado."}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    # ------------------------------------------------------------------ ciclo da requisição
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        caminho = request.url.path
        resposta = None
        if self._config.demo:
            resposta = self._barrar_na_demo(request, caminho)
        if resposta is None and self._autenticacao.ativa:
            resposta = self._barrar_sem_login(request, caminho)
        if resposta is None:
            resposta = await call_next(request)
        self._cabecalhos(request, caminho, resposta)
        return resposta

    @staticmethod
    def _cabecalhos(request: Request, caminho: str, resposta: Response) -> None:
        h = resposta.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "same-origin"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not caminho.startswith(CAMINHOS_SEM_POLITICA):
            h["Content-Security-Policy"] = POLITICA_DE_CONTEUDO
        if request.url.scheme == "https":
            h["Strict-Transport-Security"] = "max-age=31536000"
        if caminho.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        elif caminho.startswith("/assets/fonts/"):
            h["Cache-Control"] = "public, max-age=31536000, immutable"
        elif caminho.startswith("/assets/"):
            h["Cache-Control"] = "no-cache"  # o navegador revalida (ETag) a cada uso
