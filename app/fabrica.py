"""Criação da aplicação FastAPI."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from . import __version__
from .api import roteador
from .api.mensagens import traduzir_erros_de_validacao
from .config import Configuracoes
from .container import Container
from .erros import ErroDeDominio
from .integracoes.bcb import FonteDeIndicadores
from .middleware import ProtecaoMiddleware

log = logging.getLogger("prumo")


def criar_app(
    config: Configuracoes | None = None, fonte_de_indicadores: FonteDeIndicadores | None = None
) -> FastAPI:
    config = config or Configuracoes.do_ambiente()
    container = Container(config, fonte_de_indicadores)
    container.iniciar()

    app = FastAPI(
        title="Prumo: controle financeiro",
        version=__version__,
        docs_url=None if config.demo else "/docs",
        redoc_url=None,
        openapi_url=None if config.demo else "/openapi.json",
    )
    app.state.container = container

    # ---- erros: sempre {"detail": "...", "campos": {...}} em português
    @app.exception_handler(ErroDeDominio)
    async def _erro_de_dominio(_: Request, erro: ErroDeDominio) -> JSONResponse:
        return JSONResponse({"detail": erro.mensagem}, status_code=erro.status_http)

    @app.exception_handler(RequestValidationError)
    async def _erro_de_validacao(_: Request, erro: RequestValidationError) -> JSONResponse:
        return JSONResponse(traduzir_erros_de_validacao(erro.errors()), status_code=422)

    # ---- middlewares (o último adicionado é o primeiro a receber a requisição)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        ProtecaoMiddleware, config=config, autenticacao=container.autenticacao, limitador=container.limitador_demo
    )

    # ---- API e páginas
    app.include_router(roteador)

    @app.get("/", include_in_schema=False)
    def pagina_inicial() -> FileResponse:
        return FileResponse(config.pasta_web / "index.html")

    @app.get("/login", include_in_schema=False)
    def pagina_de_login(request: Request):
        from .middleware import COOKIE_DE_SESSAO

        logado = container.autenticacao.assinador.valido(request.cookies.get(COOKIE_DE_SESSAO))
        if not container.autenticacao.ativa or logado:
            return RedirectResponse("/", status_code=303)
        return FileResponse(config.pasta_web / "login.html")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> RedirectResponse:
        return RedirectResponse("/assets/img/favicon.svg", status_code=301)

    app.mount("/assets", StaticFiles(directory=config.pasta_web / "assets"), name="assets")
    return app
