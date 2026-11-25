"""Rotas HTTP. Só traduzem requisição/resposta: as regras ficam nos serviços."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Query, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from .. import __version__
from ..erros import RegraDeNegocio
from ..esquemas import LancamentoEntrada, LoginEntrada, MetasEntrada, PagoEntrada
from ..middleware import COOKIE_DE_SESSAO
from ..servicos.csv_io import ImportacaoServico
from .dependencias import Dependencias, Filtro

roteador = APIRouter()


# ---------------------------------------------------------------- saúde e sessão
@roteador.get("/healthz", include_in_schema=False)
def saude(c: Dependencias) -> dict:
    return {"status": "ok", "versao": __version__, "esquema": c.db.versao()}


@roteador.get("/api/sessao", tags=["sessão"])
def sessao(request: Request, c: Dependencias) -> dict:
    logado = c.autenticacao.assinador.valido(request.cookies.get(COOKIE_DE_SESSAO))
    return {
        "autenticacao": c.autenticacao.ativa,
        "logado": logado or not c.autenticacao.ativa,
        "demo": c.config.demo,
        "repositorio": c.config.url_repositorio,
        "versao": __version__,
    }


@roteador.post("/api/login", tags=["sessão"])
def entrar(dados: LoginEntrada, request: Request, c: Dependencias) -> Response:
    ip = request.client.host if request.client else "?"
    if c.autenticacao.tentativas.bloqueado(ip):
        return JSONResponse({"detail": "Muitas tentativas. Tente de novo em alguns minutos."}, status_code=429)
    if not c.autenticacao.ativa or not c.autenticacao.senha_correta(dados.senha):
        if c.autenticacao.ativa:
            c.autenticacao.tentativas.registrar_falha(ip)
        return JSONResponse({"detail": "Senha incorreta."}, status_code=401)
    c.autenticacao.tentativas.limpar(ip)
    resposta = JSONResponse({"ok": True})
    resposta.set_cookie(
        COOKIE_DE_SESSAO, c.autenticacao.assinador.emitir(),
        max_age=c.config.dias_de_sessao * 86400, httponly=True, samesite="lax",
        secure=request.url.scheme == "https",
    )  # fmt: skip
    return resposta


@roteador.post("/api/logout", tags=["sessão"])
def sair() -> Response:
    resposta = JSONResponse({"ok": True})
    resposta.delete_cookie(COOKIE_DE_SESSAO)
    return resposta


# ---------------------------------------------------------------- dados de apoio
@roteador.get("/api/meta", tags=["apoio"])
def meta(c: Dependencias) -> dict:
    return c.catalogo.meta()


@roteador.get("/api/indicadores", tags=["apoio"])
def indicadores(c: Dependencias) -> dict:
    return c.indicadores.obter()


# ---------------------------------------------------------------- relatórios
@roteador.get("/api/resumo", tags=["relatórios"])
def resumo(c: Dependencias, filtro: Filtro) -> dict:
    return c.relatorios.resumo(filtro)


# ---------------------------------------------------------------- lançamentos
@roteador.get("/api/lancamentos", tags=["lançamentos"])
def listar(
    c: Dependencias,
    filtro: Filtro,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    return c.lancamentos.listar(filtro, pagina, tamanho)


@roteador.post("/api/lancamentos", status_code=201, tags=["lançamentos"])
def criar(dados: LancamentoEntrada, c: Dependencias) -> dict:
    return c.lancamentos.criar(dados).para_dict()


@roteador.put("/api/lancamentos/{id_}", tags=["lançamentos"])
def atualizar(id_: int, dados: LancamentoEntrada, c: Dependencias) -> dict:
    return c.lancamentos.atualizar(id_, dados).para_dict()


@roteador.patch("/api/lancamentos/{id_}/pago", tags=["lançamentos"])
def alterar_pago(id_: int, dados: PagoEntrada, c: Dependencias) -> dict:
    return c.lancamentos.definir_pago(id_, dados.pago).para_dict()


@roteador.delete("/api/lancamentos/{id_}", status_code=204, tags=["lançamentos"])
def excluir(id_: int, c: Dependencias) -> Response:
    c.lancamentos.excluir(id_)
    return Response(status_code=204)


@roteador.delete("/api/lancamentos", tags=["lançamentos"])
def excluir_todos(c: Dependencias, confirmar: bool = False) -> dict:
    if not confirmar:
        raise RegraDeNegocio("Confirme a exclusão com ?confirmar=true.")
    return {"excluidos": c.lancamentos.excluir_todos()}


# ---------------------------------------------------------------- orçamento
@roteador.get("/api/orcamento", tags=["orçamento"])
def orcamento(c: Dependencias, mes: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]) -> dict:
    return c.orcamento.consumo(mes)


@roteador.get("/api/orcamento/metas", tags=["orçamento"])
def metas(c: Dependencias) -> list[dict]:
    return c.orcamento.metas()


@roteador.put("/api/orcamento/metas", tags=["orçamento"])
def salvar_metas(dados: MetasEntrada, c: Dependencias) -> list[dict]:
    c.orcamento.salvar_metas(dados.metas)
    return c.orcamento.metas()


# ---------------------------------------------------------------- CSV
@roteador.get("/api/exportar.csv", tags=["arquivos"])
def exportar(c: Dependencias, filtro: Filtro) -> Response:
    return Response(
        c.exportacao.gerar_csv(filtro),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lancamentos.csv"'},
    )


@roteador.post("/api/importar", tags=["arquivos"])
async def importar(c: Dependencias, arquivo: Annotated[UploadFile, File()]) -> dict:
    bruto = await arquivo.read(ImportacaoServico.LIMITE_BYTES + 1)
    if len(bruto) > ImportacaoServico.LIMITE_BYTES:
        raise RegraDeNegocio("Arquivo grande demais (máximo 5 MB).")
    r = c.importacao.importar(bruto)
    return {"importados": r.importados, "ignorados": r.ignorados, "erros": r.erros[:20]}
