"""Dados auxiliares para montar a tela: categorias, contas e intervalo dos dados."""

from __future__ import annotations

from typing import Any

from ..database import Database
from ..repositorios import CatalogoRepositorio


class CatalogoServico:
    def __init__(self, db: Database, catalogo: CatalogoRepositorio):
        self._db = db
        self._catalogo = catalogo

    def meta(self) -> dict[str, Any]:
        with self._db.leitura() as con:
            categorias = self._catalogo.categorias(con)
            contas = self._catalogo.contas(con)
            menor, maior = self._catalogo.intervalo_de_datas(con)
        return {
            "categorias": [c.para_dict() for c in categorias],
            "contas": [c.para_dict() for c in contas],
            "periodo_dos_dados": {
                "inicio": menor.isoformat() if menor else None,
                "fim": maior.isoformat() if maior else None,
            },
        }
