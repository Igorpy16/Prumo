"""Consultas agregadas. Toda a soma e agrupamento acontece no SQL, não em Python."""

from __future__ import annotations

import sqlite3

from ..filtros import FiltroLancamentos
from ..modelos import ItemAgrupado, Lancamento, PontoMensal, Totais


class RelatorioRepositorio:
    def totais(self, con: sqlite3.Connection, filtro: FiltroLancamentos) -> Totais:
        where, params = filtro.clausula()
        linha = con.execute(
            f"""
            SELECT COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor_centavos END), 0)               AS receitas,
                   COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor_centavos END), 0)               AS despesas,
                   COALESCE(SUM(CASE WHEN tipo = 'despesa' AND pago = 0 THEN valor_centavos END), 0)  AS a_pagar,
                   COUNT(CASE WHEN tipo = 'despesa' AND pago = 0 THEN 1 END)                          AS qtd_a_pagar,
                   COUNT(*)                                                                           AS quantidade
              FROM lancamentos {where}
            """,
            params,
        ).fetchone()
        return Totais(linha["receitas"], linha["despesas"], linha["a_pagar"], linha["qtd_a_pagar"], linha["quantidade"])

    def serie_mensal(
        self, con: sqlite3.Connection, filtro: FiltroLancamentos, mes_inicial: str, mes_final: str
    ) -> list[PontoMensal]:
        """Um ponto por mês (inclusive meses sem movimento) com o saldo acumulado.

        Usa uma CTE recursiva para gerar a lista de meses, um LEFT JOIN para não
        perder os meses vazios e uma função de janela para o acumulado.
        """
        where, params = filtro.clausula()
        linhas = con.execute(
            f"""
            WITH RECURSIVE meses (m) AS (
                SELECT ?
                UNION ALL
                SELECT strftime('%Y-%m', m || '-01', '+1 month') FROM meses WHERE m < ?
            ),
            agregado AS (
                SELECT substr(data, 1, 7) AS m,
                       SUM(CASE WHEN tipo = 'receita' THEN valor_centavos ELSE 0 END) AS receitas,
                       SUM(CASE WHEN tipo = 'despesa' THEN valor_centavos ELSE 0 END) AS despesas
                  FROM lancamentos {where}
                 GROUP BY m
            )
            SELECT meses.m AS mes,
                   COALESCE(a.receitas, 0) AS receitas,
                   COALESCE(a.despesas, 0) AS despesas,
                   SUM(COALESCE(a.receitas, 0) - COALESCE(a.despesas, 0)) OVER (ORDER BY meses.m) AS acumulado
              FROM meses
              LEFT JOIN agregado a ON a.m = meses.m
             ORDER BY meses.m
            """,
            [mes_inicial, mes_final, *params],
        ).fetchall()
        return [PontoMensal(r["mes"], r["receitas"], r["despesas"], r["acumulado"]) for r in linhas]

    def despesas_por_categoria(self, con: sqlite3.Connection, filtro: FiltroLancamentos) -> list[ItemAgrupado]:
        where, params = filtro.clausula(extras=("tipo = 'despesa'",))
        linhas = con.execute(
            f"""
            SELECT categoria_id AS id, categoria AS nome, SUM(valor_centavos) AS total, COUNT(*) AS quantidade
              FROM v_lancamentos {where}
             GROUP BY categoria_id
             ORDER BY total DESC, nome
            """,
            params,
        ).fetchall()
        return [ItemAgrupado(r["id"], r["nome"], r["total"], r["quantidade"]) for r in linhas]

    def despesas_por_conta(self, con: sqlite3.Connection, filtro: FiltroLancamentos) -> list[ItemAgrupado]:
        where, params = filtro.clausula(extras=("tipo = 'despesa'",))
        linhas = con.execute(
            f"""
            SELECT conta_id AS id, conta AS nome, SUM(valor_centavos) AS total, COUNT(*) AS quantidade
              FROM v_lancamentos {where}
             GROUP BY conta_id
             ORDER BY total DESC, nome
            """,
            params,
        ).fetchall()
        return [ItemAgrupado(r["id"], r["nome"], r["total"], r["quantidade"]) for r in linhas]

    def maiores_despesas(self, con: sqlite3.Connection, filtro: FiltroLancamentos, limite: int = 5) -> list[Lancamento]:
        where, params = filtro.clausula(extras=("tipo = 'despesa'",))
        linhas = con.execute(
            f"""
            SELECT id, data, descricao, valor_centavos, tipo, pago, categoria_id, categoria, conta_id, conta
              FROM v_lancamentos {where}
             ORDER BY valor_centavos DESC, data DESC
             LIMIT ?
            """,
            [*params, limite],
        ).fetchall()
        return [Lancamento.da_linha(r) for r in linhas]
