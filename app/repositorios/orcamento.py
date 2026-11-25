"""Metas mensais de gasto por categoria."""

from __future__ import annotations

import sqlite3
from datetime import date

from ..modelos import ConsumoDeMeta, Meta


class OrcamentoRepositorio:
    def metas(self, con: sqlite3.Connection) -> list[Meta]:
        """Todas as categorias de despesa, com a meta atual (0 = sem meta)."""
        linhas = con.execute(
            """
            SELECT c.id AS categoria_id, c.nome AS categoria, COALESCE(o.limite_centavos, 0) AS limite
              FROM categorias c
              LEFT JOIN orcamentos o ON o.categoria_id = c.id
             WHERE c.tipo = 'despesa'
             ORDER BY c.id
            """
        ).fetchall()
        return [Meta(r["categoria_id"], r["categoria"], r["limite"]) for r in linhas]

    def categoria_de_despesa_existe(self, con: sqlite3.Connection, categoria_id: int) -> bool:
        return con.execute(
            "SELECT 1 FROM categorias WHERE id = ? AND tipo = 'despesa'", (categoria_id,)
        ).fetchone() is not None

    def salvar(self, con: sqlite3.Connection, categoria_id: int, limite_centavos: int) -> None:
        """Define a meta; limite 0 remove a meta."""
        if limite_centavos <= 0:
            con.execute("DELETE FROM orcamentos WHERE categoria_id = ?", (categoria_id,))
            return
        con.execute(
            "INSERT INTO orcamentos (categoria_id, limite_centavos) VALUES (?, ?) "
            "ON CONFLICT (categoria_id) DO UPDATE SET limite_centavos = excluded.limite_centavos",
            (categoria_id, limite_centavos),
        )

    def consumo(self, con: sqlite3.Connection, primeiro_dia: date, primeiro_dia_do_proximo_mes: date) -> list[ConsumoDeMeta]:
        """Meta x gasto de cada categoria no mês. Só lista categorias com meta ou com gasto."""
        linhas = con.execute(
            """
            SELECT c.id AS categoria_id,
                   c.nome AS categoria,
                   COALESCE(o.limite_centavos, 0) AS limite,
                   COALESCE(SUM(l.valor_centavos), 0) AS gasto
              FROM categorias c
              LEFT JOIN orcamentos o ON o.categoria_id = c.id
              LEFT JOIN lancamentos l ON l.categoria_id = c.id AND l.data >= ? AND l.data < ?
             WHERE c.tipo = 'despesa'
             GROUP BY c.id
            HAVING limite > 0 OR gasto > 0
             ORDER BY CASE WHEN limite > 0 THEN gasto * 1.0 / limite ELSE 999 END DESC, gasto DESC
            """,
            (primeiro_dia.isoformat(), primeiro_dia_do_proximo_mes.isoformat()),
        ).fetchall()
        return [ConsumoDeMeta(r["categoria_id"], r["categoria"], r["limite"], r["gasto"]) for r in linhas]
