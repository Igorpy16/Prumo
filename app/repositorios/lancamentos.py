"""Lançamentos (receitas e despesas)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from ..filtros import FiltroLancamentos
from ..modelos import Lancamento, NovoLancamento

_COLUNAS = "id, data, descricao, valor_centavos, tipo, pago, categoria_id, categoria, conta_id, conta"


def _valores(n: NovoLancamento) -> tuple:
    return (n.data.isoformat(), n.descricao, n.valor_centavos, n.tipo.value, n.categoria_id, n.conta_id, int(n.pago))


class LancamentoRepositorio:
    def inserir(self, con: sqlite3.Connection, n: NovoLancamento) -> int:
        return con.execute(
            "INSERT INTO lancamentos (data, descricao, valor_centavos, tipo, categoria_id, conta_id, pago) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            _valores(n),
        ).lastrowid

    def inserir_varios(self, con: sqlite3.Connection, novos: Iterable[NovoLancamento]) -> int:
        lote = [_valores(n) for n in novos]
        con.executemany(
            "INSERT INTO lancamentos (data, descricao, valor_centavos, tipo, categoria_id, conta_id, pago) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            lote,
        )
        return len(lote)

    def atualizar(self, con: sqlite3.Connection, id_: int, n: NovoLancamento) -> bool:
        cur = con.execute(
            "UPDATE lancamentos SET data = ?, descricao = ?, valor_centavos = ?, tipo = ?, "
            "categoria_id = ?, conta_id = ?, pago = ? WHERE id = ?",
            (*_valores(n), id_),
        )
        return cur.rowcount > 0

    def definir_pago(self, con: sqlite3.Connection, id_: int, pago: bool) -> bool:
        return con.execute("UPDATE lancamentos SET pago = ? WHERE id = ?", (int(pago), id_)).rowcount > 0

    def excluir(self, con: sqlite3.Connection, id_: int) -> bool:
        return con.execute("DELETE FROM lancamentos WHERE id = ?", (id_,)).rowcount > 0

    def excluir_todos(self, con: sqlite3.Connection) -> int:
        return con.execute("DELETE FROM lancamentos").rowcount

    def obter(self, con: sqlite3.Connection, id_: int) -> Lancamento | None:
        linha = con.execute(f"SELECT {_COLUNAS} FROM v_lancamentos WHERE id = ?", (id_,)).fetchone()
        return Lancamento.da_linha(linha) if linha else None

    def listar(
        self, con: sqlite3.Connection, filtro: FiltroLancamentos, limite: int | None = None, deslocamento: int = 0
    ) -> list[Lancamento]:
        where, params = filtro.clausula()
        sql = f"SELECT {_COLUNAS} FROM v_lancamentos {where} ORDER BY data DESC, id DESC"
        if limite is not None:
            sql += " LIMIT ? OFFSET ?"
            params = [*params, limite, deslocamento]
        return [Lancamento.da_linha(r) for r in con.execute(sql, params)]

    def contar(self, con: sqlite3.Connection, filtro: FiltroLancamentos) -> int:
        where, params = filtro.clausula()
        return con.execute(f"SELECT COUNT(*) FROM lancamentos {where}", params).fetchone()[0]
