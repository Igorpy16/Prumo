"""Regras de cadastro e consulta de lançamentos."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..database import Database
from ..erros import NaoEncontrado, RegraDeNegocio
from ..esquemas import LancamentoEntrada
from ..filtros import FiltroLancamentos
from ..modelos import Lancamento, NovoLancamento
from ..repositorios import CatalogoRepositorio, ConfiguracaoRepositorio, LancamentoRepositorio
from ..util import Moeda

CHAVE_EXEMPLO_APLICADO = "exemplo_aplicado"


class LancamentoServico:
    def __init__(
        self,
        db: Database,
        catalogo: CatalogoRepositorio,
        lancamentos: LancamentoRepositorio,
        configuracoes: ConfiguracaoRepositorio,
    ):
        self._db = db
        self._catalogo = catalogo
        self._lancamentos = lancamentos
        self._configuracoes = configuracoes

    def _resolver(self, con: sqlite3.Connection, entrada: LancamentoEntrada) -> NovoLancamento:
        """Transforma nomes de categoria e conta em ids (criando o que ainda não existe)."""
        return NovoLancamento(
            data=entrada.data,
            descricao=entrada.descricao,
            valor_centavos=Moeda.para_centavos(entrada.valor),
            tipo=entrada.tipo,
            categoria_id=self._catalogo.obter_ou_criar_categoria(con, entrada.categoria, entrada.tipo),
            conta_id=self._catalogo.obter_ou_criar_conta(con, entrada.conta),
            pago=entrada.pago,
        )

    def _obter_ou_falhar(self, con: sqlite3.Connection, id_: int) -> Lancamento:
        lancamento = self._lancamentos.obter(con, id_)
        if lancamento is None:
            raise NaoEncontrado("Lançamento não encontrado.")
        return lancamento

    def criar(self, entrada: LancamentoEntrada) -> Lancamento:
        try:
            with self._db.transacao() as con:
                novo_id = self._lancamentos.inserir(con, self._resolver(con, entrada))
                return self._obter_ou_falhar(con, novo_id)
        except sqlite3.IntegrityError as erro:
            raise RegraDeNegocio("Os dados informados não são válidos.") from erro

    def atualizar(self, id_: int, entrada: LancamentoEntrada) -> Lancamento:
        try:
            with self._db.transacao() as con:
                self._obter_ou_falhar(con, id_)
                self._lancamentos.atualizar(con, id_, self._resolver(con, entrada))
                return self._obter_ou_falhar(con, id_)
        except sqlite3.IntegrityError as erro:
            raise RegraDeNegocio("Os dados informados não são válidos.") from erro

    def definir_pago(self, id_: int, pago: bool) -> Lancamento:
        with self._db.transacao() as con:
            self._obter_ou_falhar(con, id_)
            self._lancamentos.definir_pago(con, id_, pago)
            return self._obter_ou_falhar(con, id_)

    def excluir(self, id_: int) -> None:
        with self._db.transacao() as con:
            if not self._lancamentos.excluir(con, id_):
                raise NaoEncontrado("Lançamento não encontrado.")

    def excluir_todos(self) -> int:
        with self._db.transacao() as con:
            apagados = self._lancamentos.excluir_todos(con)
            # Quem apaga tudo quer começar do zero: não recriar os dados de exemplo depois.
            self._configuracoes.salvar(con, CHAVE_EXEMPLO_APLICADO, "1")
            return apagados

    def listar(self, filtro: FiltroLancamentos, pagina: int, tamanho: int) -> dict[str, Any]:
        tamanho = max(1, min(tamanho, 100))
        with self._db.leitura() as con:
            total = self._lancamentos.contar(con, filtro)
            paginas = max(1, -(-total // tamanho))
            pagina = max(1, min(pagina, paginas))
            itens = self._lancamentos.listar(con, filtro, tamanho, (pagina - 1) * tamanho)
        return {
            "total": total,
            "pagina": pagina,
            "paginas": paginas,
            "tamanho": tamanho,
            "itens": [i.para_dict() for i in itens],
        }
