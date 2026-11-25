"""Monta o resumo do painel a partir das consultas agregadas."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..database import Database
from ..filtros import FiltroLancamentos
from ..modelos import ItemAgrupado, Totais
from ..repositorios import CatalogoRepositorio, RelatorioRepositorio
from ..util import Moeda, somar_meses

MAXIMO_DE_MESES = 60


def _variacao(atual: int, anterior: int | None) -> float | None:
    if not anterior:
        return None
    return round((atual / anterior - 1) * 100, 1)


class RelatorioServico:
    def __init__(self, db: Database, catalogo: CatalogoRepositorio, relatorios: RelatorioRepositorio):
        self._db = db
        self._catalogo = catalogo
        self._relatorios = relatorios

    @staticmethod
    def _kpis(t: Totais) -> dict[str, Any]:
        return {
            "receitas": Moeda.para_reais(t.receitas),
            "despesas": Moeda.para_reais(t.despesas),
            "saldo": Moeda.para_reais(t.saldo),
            "taxa_poupanca": round(t.saldo / t.receitas * 100, 1) if t.receitas > 0 else None,
            "a_pagar": Moeda.para_reais(t.a_pagar),
            "qtd_a_pagar": t.qtd_a_pagar,
        }

    @staticmethod
    def _agrupar(itens: list[ItemAgrupado], total: int) -> list[dict[str, Any]]:
        return [
            {
                "id": i.id,
                "nome": i.nome,
                "valor": Moeda.para_reais(i.total),
                "percentual": round(i.total / total * 100, 1) if total else 0.0,
                "quantidade": i.quantidade,
            }
            for i in itens
        ]

    @staticmethod
    def _meses(inicio: date, fim: date) -> tuple[str, str]:
        """Primeiro e último mês (AAAA-MM) do gráfico, limitado a 60 meses."""
        ultimo = (fim.year, fim.month)
        primeiro = max((inicio.year, inicio.month), somar_meses(*ultimo, -(MAXIMO_DE_MESES - 1)))
        return f"{primeiro[0]:04d}-{primeiro[1]:02d}", f"{ultimo[0]:04d}-{ultimo[1]:02d}"

    def resumo(self, filtro: FiltroLancamentos) -> dict[str, Any]:
        with self._db.leitura() as con:
            totais = self._relatorios.totais(con, filtro)
            anterior_filtro = filtro.periodo_anterior()
            anterior = self._relatorios.totais(con, anterior_filtro) if anterior_filtro else None

            resposta: dict[str, Any] = {
                "vazio": totais.quantidade == 0,
                "kpis": self._kpis(totais),
                "variacao": {
                    "receitas": _variacao(totais.receitas, anterior.receitas if anterior else None),
                    "despesas": _variacao(totais.despesas, anterior.despesas if anterior else None),
                },
            }
            if totais.quantidade == 0:
                return resposta

            menor, maior = self._catalogo.intervalo_de_datas(con)
            mes_inicial, mes_final = self._meses(filtro.inicio or menor, filtro.fim or maior)
            serie = self._relatorios.serie_mensal(con, filtro, mes_inicial, mes_final)
            categorias = self._relatorios.despesas_por_categoria(con, filtro)
            contas = self._relatorios.despesas_por_conta(con, filtro)
            maiores = self._relatorios.maiores_despesas(con, filtro, 5)

        resposta["mensal"] = {
            "meses": [p.mes for p in serie],
            "receitas": [Moeda.para_reais(p.receitas) for p in serie],
            "despesas": [Moeda.para_reais(p.despesas) for p in serie],
            "saldo": [Moeda.para_reais(p.saldo) for p in serie],
            "acumulado": [Moeda.para_reais(p.acumulado) for p in serie],
        }
        resposta["categorias"] = self._agrupar(categorias, totais.despesas)
        resposta["contas"] = self._agrupar(contas, totais.despesas)
        resposta["maiores_despesas"] = [m.para_dict() for m in maiores]
        return resposta
