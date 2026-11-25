"""Acesso ao SQLite: conexões, transações, migrações e cópia de segurança."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .util import normalizar

PASTA_MIGRACOES = Path(__file__).parent / "migracoes"
_NOME_MIGRACAO = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


class Database:
    """Abre conexões curtas (uma por operação) com as configurações certas.

    * `leitura()`   conexão para consultas.
    * `transacao()` conexão com BEGIN IMMEDIATE: grava tudo ou nada.
    * `migrar()`    aplica, em ordem e de forma atômica, os arquivos de `migracoes/`.
    """

    def __init__(self, caminho: Path, pasta_migracoes: Path = PASTA_MIGRACOES):
        self.caminho = Path(caminho)
        self.pasta_migracoes = pasta_migracoes

    # ------------------------------------------------------------------ conexões
    def _abrir(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.caminho, isolation_level=None, timeout=5.0)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")      # o SQLite deixa desligado por padrão
        con.execute("PRAGMA busy_timeout = 5000")
        con.execute("PRAGMA synchronous = NORMAL")   # seguro com WAL e bem mais rápido
        con.execute("PRAGMA temp_store = MEMORY")
        # busca sem acento e sem diferença de maiúsculas: norm(descricao) LIKE '%cafe%'
        con.create_function("norm", 1, normalizar, deterministic=True)
        return con

    @contextmanager
    def leitura(self) -> Iterator[sqlite3.Connection]:
        con = self._abrir()
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transacao(self) -> Iterator[sqlite3.Connection]:
        con = self._abrir()
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

    # ------------------------------------------------------------------ migrações
    def _arquivos_de_migracao(self) -> list[tuple[int, Path]]:
        itens = []
        for arquivo in sorted(self.pasta_migracoes.glob("*.sql")):
            casou = _NOME_MIGRACAO.match(arquivo.name)
            if not casou:
                raise ValueError(f"Nome de migração inválido: {arquivo.name} (use 001_nome.sql)")
            itens.append((int(casou.group(1)), arquivo))
        return itens

    def versao(self) -> int:
        with self.leitura() as con:
            return con.execute("PRAGMA user_version").fetchone()[0]

    def migrar(self) -> list[str]:
        """Aplica as migrações pendentes e devolve os nomes das aplicadas."""
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        aplicadas: list[str] = []
        con = self._abrir()
        try:
            con.execute("PRAGMA journal_mode = WAL")  # leitores não bloqueiam o gravador
            atual = con.execute("PRAGMA user_version").fetchone()[0]
            for versao, arquivo in self._arquivos_de_migracao():
                if versao <= atual:
                    continue
                sql = arquivo.read_text(encoding="utf-8")
                # Tudo (incluindo a nova versão) numa única transação.
                con.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {versao};\nCOMMIT;")
                aplicadas.append(arquivo.name)
        except BaseException:
            if con.in_transaction:
                con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return aplicadas

    # ------------------------------------------------------------------ operação
    def responde(self) -> bool:
        """Usado pelo /healthz: o banco abre e responde?"""
        try:
            with self.leitura() as con:
                return con.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def copia_de_seguranca(self, destino: Path) -> Path:
        """Cópia consistente (mesmo com o app em uso), usando a API de backup do SQLite."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        origem = self._abrir()
        alvo = sqlite3.connect(destino)
        try:
            origem.backup(alvo)
            resultado = alvo.execute("PRAGMA quick_check").fetchone()[0]
            if resultado != "ok":
                raise RuntimeError(f"A cópia de segurança falhou na verificação: {resultado}")
        finally:
            alvo.close()
            origem.close()
        return destino
