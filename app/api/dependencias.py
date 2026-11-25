"""Dependências compartilhadas pelas rotas."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Query, Request

from ..container import Container
from ..erros import RegraDeNegocio
from ..filtros import FiltroLancamentos
from ..modelos import Situacao, TipoLancamento


def container(request: Request) -> Container:
    return request.app.state.container


def filtro_da_consulta(
    inicio: date | None = None,
    fim: date | None = None,
    tipo: TipoLancamento | None = None,
    situacao: Situacao | None = None,
    busca: Annotated[str | None, Query(max_length=120)] = None,
    categoria: Annotated[list[int] | None, Query()] = None,
    conta: Annotated[list[int] | None, Query()] = None,
) -> FiltroLancamentos:
    if inicio and fim and inicio > fim:
        raise RegraDeNegocio("A data inicial não pode ser depois da final.")
    return FiltroLancamentos(
        inicio=inicio, fim=fim, tipo=tipo, situacao=situacao, busca=busca,
        categorias=tuple(categoria or ()), contas=tuple(conta or ()),
    )  # fmt: skip


Dependencias = Annotated[Container, Depends(container)]
Filtro = Annotated[FiltroLancamentos, Depends(filtro_da_consulta)]
