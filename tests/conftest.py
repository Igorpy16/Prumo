from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Configuracoes
from app.fabrica import criar_app
from app.integracoes.bcb import Indicador


class FonteFalsa:
    """Substitui o Banco Central nos testes: nada acessa a internet."""

    def __init__(self, itens=None, falhar=False):
        self.itens, self.falhar, self.chamadas = itens or [], falhar, 0

    def buscar(self):
        self.chamadas += 1
        if self.falhar:
            raise RuntimeError("fora do ar")
        return self.itens


def indicador(codigo="selic", valor=14.5):
    from datetime import date

    return Indicador(codigo, codigo.upper(), valor, "% a.a.", date(2026, 11, 1), "teste", 432)


def montar(tmp_path, **extra):
    env = {"DATABASE_PATH": str(tmp_path / "t.db"), "INDICADORES": "0", "SEMEAR_DEMO": "0", **extra}
    return Configuracoes.do_ambiente(env)


@pytest.fixture
def config(tmp_path):
    return montar(tmp_path)


@pytest.fixture
def app(config):
    return criar_app(config)


@pytest.fixture
def cliente(app):
    return TestClient(app)


@pytest.fixture
def container(app):
    return app.state.container


def lancamento(**o):
    base = {"data": "2026-10-10", "descricao": "Mercado", "valor": "100.00", "tipo": "despesa", "categoria": "Alimentação"}
    return {**base, **o}
