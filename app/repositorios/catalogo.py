"""Categorias e contas."""

from __future__ import annotations

import sqlite3
from datetime import date

from ..modelos import Categoria, Conta, TipoLancamento
from ..util import colapsar_espacos, normalizar

CATEGORIAS_PADRAO: tuple[tuple[str, TipoLancamento], ...] = (
    ("Moradia", TipoLancamento.DESPESA),
    ("Alimentação", TipoLancamento.DESPESA),
    ("Transporte", TipoLancamento.DESPESA),
    ("Saúde", TipoLancamento.DESPESA),
    ("Lazer", TipoLancamento.DESPESA),
    ("Educação", TipoLancamento.DESPESA),
    ("Assinaturas", TipoLancamento.DESPESA),
    ("Outros", TipoLancamento.DESPESA),
    ("Salário", TipoLancamento.RECEITA),
    ("Freelance", TipoLancamento.RECEITA),
    ("Investimentos", TipoLancamento.RECEITA),
    ("Outros", TipoLancamento.RECEITA),
)
CONTAS_PADRAO: tuple[str, ...] = ("Conta corrente", "Cartão de crédito", "Poupança", "Dinheiro")


class CatalogoRepositorio:
    def garantir_padroes(self, con: sqlite3.Connection) -> None:
        """Cria categorias e contas iniciais (idempotente)."""
        for nome, tipo in CATEGORIAS_PADRAO:
            self.obter_ou_criar_categoria(con, nome, tipo)
        for nome in CONTAS_PADRAO:
            self.obter_ou_criar_conta(con, nome)

    def categorias(self, con: sqlite3.Connection, tipo: TipoLancamento | None = None) -> list[Categoria]:
        sql = "SELECT id, nome, tipo FROM categorias"
        params: tuple = ()
        if tipo:
            sql += " WHERE tipo = ?"
            params = (tipo.value,)
        sql += " ORDER BY tipo DESC, id"  # despesas primeiro, na ordem de criação
        return [Categoria(r["id"], r["nome"], TipoLancamento(r["tipo"])) for r in con.execute(sql, params)]

    def contas(self, con: sqlite3.Connection) -> list[Conta]:
        return [Conta(r["id"], r["nome"]) for r in con.execute("SELECT id, nome FROM contas ORDER BY id")]

    def obter_ou_criar_categoria(self, con: sqlite3.Connection, nome: str, tipo: TipoLancamento) -> int:
        nome = colapsar_espacos(nome)
        chave = normalizar(nome)
        linha = con.execute("SELECT id FROM categorias WHERE chave = ? AND tipo = ?", (chave, tipo.value)).fetchone()
        if linha:
            return linha["id"]
        return con.execute(
            "INSERT INTO categorias (nome, chave, tipo) VALUES (?, ?, ?)", (nome, chave, tipo.value)
        ).lastrowid

    def obter_ou_criar_conta(self, con: sqlite3.Connection, nome: str) -> int:
        nome = colapsar_espacos(nome)
        chave = normalizar(nome)
        linha = con.execute("SELECT id FROM contas WHERE chave = ?", (chave,)).fetchone()
        if linha:
            return linha["id"]
        return con.execute("INSERT INTO contas (nome, chave) VALUES (?, ?)", (nome, chave)).lastrowid

    def intervalo_de_datas(self, con: sqlite3.Connection) -> tuple[date | None, date | None]:
        linha = con.execute("SELECT MIN(data) AS menor, MAX(data) AS maior FROM lancamentos").fetchone()
        if linha["menor"] is None:
            return None, None
        return date.fromisoformat(linha["menor"]), date.fromisoformat(linha["maior"])
