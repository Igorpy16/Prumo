"""Acesso ao SQLite: conexões, transações e migrações versionadas."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.util import normalizar

PASTA_DE_MIGRACOES = Path(__file__).parent / "migracoes"
_NOME_DE_MIGRACAO = re.compile(r"^(\d{3})_(.+)\.sql$")


class Banco:
    """Fábrica de conexões. Cada operação abre e fecha a sua (barato no SQLite)."""

    def __init__(self, caminho: Path, pasta_de_migracoes: Path = PASTA_DE_MIGRACOES):
        self.caminho = Path(caminho)
        self.pasta_de_migracoes = pasta_de_migracoes

    # ------------------------------------------------------------------ conexões
    def abrir(self) -> sqlite3.Connection:
        # isolation_level=None: nós controlamos BEGIN/COMMIT explicitamente.
        con = sqlite3.connect(self.caminho, isolation_level=None, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")      # o SQLite deixa desligado por padrão
        con.execute("PRAGMA busy_timeout = 5000")
        con.execute("PRAGMA synchronous = NORMAL")   # seguro com WAL e bem mais rápido
        con.execute("PRAGMA temp_store = MEMORY")
        # busca sem acento e sem diferença de maiúsculas (o LIKE do SQLite só trata ASCII)
        con.create_function("norm", 1, normalizar, deterministic=True)
        return con

    @contextmanager
    def leitura(self) -> Iterator[sqlite3.Connection]:
        con = self.abrir()
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        """Tudo ou nada: confirma ao sair normalmente, desfaz se der qualquer erro."""
        con = self.abrir()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.execute("COMMIT")
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    # --------------------------------------------------------------- migrações
    def _migracoes(self) -> list[tuple[int, str, str]]:
        achadas = []
        for arquivo in sorted(self.pasta_de_migracoes.glob("*.sql")):
            m = _NOME_DE_MIGRACAO.match(arquivo.name)
            if m:
                achadas.append((int(m.group(1)), arquivo.name, arquivo.read_text(encoding="utf-8")))
        return achadas

    def versao(self) -> int:
        with self.leitura() as con:
            return con.execute("PRAGMA user_version").fetchone()[0]

    def migrar(self) -> list[str]:
        """Aplica, em ordem, as migrações ainda não executadas. Devolve os nomes aplicados.

        Cada migração roda numa transação junto com a atualização de `user_version`:
        se falhar, o banco fica exatamente como estava.
        """
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        con = self.abrir()
        aplicadas: list[str] = []
        try:
            con.execute("PRAGMA journal_mode = WAL")  # leitores não bloqueiam o escritor
            atual = con.execute("PRAGMA user_version").fetchone()[0]
            for versao, nome, sql in self._migracoes():
                if versao <= atual:
                    continue
                try:
                    con.executescript(
                        f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {versao};\nCOMMIT;"
                    )
                except BaseException:
                    if con.in_transaction:
                        con.execute("ROLLBACK")
                    raise
                aplicadas.append(nome)
        finally:
            con.close()
        return aplicadas

    # ------------------------------------------------------------------ manutenção
    def copiar_para(self, destino: Path) -> Path:
        """Cópia consistente do banco (mesmo com o app em uso), usando a API de backup do SQLite."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        origem = self.abrir()
        alvo = sqlite3.connect(destino)
        try:
            origem.backup(alvo)
            if alvo.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("A cópia do banco falhou na verificação de integridade.")
        finally:
            alvo.close()
            origem.close()
        return destino

    def remover_arquivos(self) -> None:
        for sufixo in ("", "-wal", "-shm"):
            Path(str(self.caminho) + sufixo).unlink(missing_ok=True)
