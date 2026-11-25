"""Metas mensais de gasto por categoria."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from ..database import Database
from ..erros import RegraDeNegocio
from ..esquemas import MetaEntrada
from ..repositorios import OrcamentoRepositorio
from ..util import Moeda, somar_meses

_MES = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class OrcamentoServico:
    def __init__(self, db: Database, orcamento: OrcamentoRepositorio):
        self._db = db
        self._orcamento = orcamento

    @staticmethod
    def _intervalo_do_mes(mes: str) -> tuple[date, date]:
        casou = _MES.match(mes)
        if not casou:
            raise RegraDeNegocio("Mês inválido. Use o formato AAAA-MM.")
        ano, numero = int(casou.group(1)), int(casou.group(2))
        return date(ano, numero, 1), date(*somar_meses(ano, numero, 1), 1)

    def consumo(self, mes: str) -> dict[str, Any]:
        primeiro, proximo = self._intervalo_do_mes(mes)
        with self._db.leitura() as con:
            itens = self._orcamento.consumo(con, primeiro, proximo)
        com_meta = [i for i in itens if i.limite > 0]
        return {
            "mes": mes,
            "itens": [
                {
                    "categoria_id": i.categoria_id,
                    "categoria": i.categoria,
                    "limite": Moeda.para_reais(i.limite),
                    "gasto": Moeda.para_reais(i.gasto),
                    "percentual": round(i.gasto / i.limite * 100, 1) if i.limite else None,
                }
                for i in itens
            ],
            "total_limite": Moeda.para_reais(sum(i.limite for i in com_meta)),
            "gasto_com_meta": Moeda.para_reais(sum(i.gasto for i in com_meta)),
            "gasto_sem_meta": Moeda.para_reais(sum(i.gasto for i in itens if i.limite == 0)),
        }

    def metas(self) -> list[dict[str, Any]]:
        with self._db.leitura() as con:
            metas = self._orcamento.metas(con)
        return [
            {"categoria_id": m.categoria_id, "categoria": m.categoria, "limite": Moeda.para_reais(m.limite)}
            for m in metas
        ]

    def salvar_metas(self, metas: list[MetaEntrada]) -> None:
        with self._db.transacao() as con:
            for meta in metas:
                if not self._orcamento.categoria_de_despesa_existe(con, meta.categoria_id):
                    raise RegraDeNegocio(f"A categoria {meta.categoria_id} não existe ou não é de despesa.")
                self._orcamento.salvar(con, meta.categoria_id, Moeda.para_centavos(meta.limite))
