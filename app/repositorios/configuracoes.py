"""Pares chave/valor simples (marcadores de estado do próprio app)."""

from __future__ import annotations

import sqlite3


class ConfiguracaoRepositorio:
    def obter(self, con: sqlite3.Connection, chave: str) -> str | None:
        linha = con.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,)).fetchone()
        return linha["valor"] if linha else None

    def salvar(self, con: sqlite3.Connection, chave: str, valor: str) -> None:
        con.execute(
            "INSERT INTO configuracoes (chave, valor) VALUES (?, ?) "
            "ON CONFLICT (chave) DO UPDATE SET valor = excluded.valor",
            (chave, valor),
        )
