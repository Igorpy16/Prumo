"""Raiz de composição: cria os objetos e liga as dependências em um só lugar."""

from __future__ import annotations

from datetime import date

from .config import Configuracoes
from .database import Database
from .exemplo import ExemploSemeador
from .integracoes.bcb import ClienteBCB, FonteDeIndicadores
from .repositorios import (
    CatalogoRepositorio,
    ConfiguracaoRepositorio,
    LancamentoRepositorio,
    OrcamentoRepositorio,
    RelatorioRepositorio,
)
from .seguranca import LimitadorDeRequisicoes, ServicoDeAutenticacao
from .servicos import (
    CatalogoServico,
    ExportacaoServico,
    ImportacaoServico,
    IndicadoresServico,
    LancamentoServico,
    OrcamentoServico,
    RelatorioServico,
)
from .servicos.lancamentos import CHAVE_EXEMPLO_APLICADO


class Container:
    """Guarda todas as dependências. Os testes podem injetar uma `fonte_de_indicadores` falsa."""

    def __init__(self, config: Configuracoes, fonte_de_indicadores: FonteDeIndicadores | None = None):
        self.config = config
        self.db = Database(config.caminho_banco)

        catalogo = CatalogoRepositorio()
        lancamentos = LancamentoRepositorio()
        relatorios = RelatorioRepositorio()
        orcamento = OrcamentoRepositorio()
        configuracoes = ConfiguracaoRepositorio()
        self._catalogo_repo = catalogo
        self._configuracoes_repo = configuracoes
        self._semeador = ExemploSemeador(catalogo, lancamentos, orcamento)

        self.catalogo = CatalogoServico(self.db, catalogo)
        self.lancamentos = LancamentoServico(self.db, catalogo, lancamentos, configuracoes)
        self.relatorios = RelatorioServico(self.db, catalogo, relatorios)
        self.orcamento = OrcamentoServico(self.db, orcamento)
        self.importacao = ImportacaoServico(self.db, catalogo, lancamentos)
        self.exportacao = ExportacaoServico(self.db, lancamentos)

        if fonte_de_indicadores is None and config.indicadores_ativos:
            fonte_de_indicadores = ClienteBCB(timeout_s=config.indicadores_timeout_s)
        self.indicadores = IndicadoresServico(
            fonte_de_indicadores, self.db, configuracoes, ttl_s=config.indicadores_ttl_s
        )

        self.autenticacao = ServicoDeAutenticacao(config)
        self.limitador_demo = LimitadorDeRequisicoes(config.limite_demo_por_minuto)

    def iniciar(self, hoje: date | None = None) -> None:
        """Prepara o banco: migrações, cadastros padrão e (uma única vez) os dados de exemplo."""
        if self.config.demo:
            self.config.caminho_banco.unlink(missing_ok=True)  # a demonstração sempre recomeça limpa
        self.db.migrar()
        with self.db.transacao() as con:
            self._catalogo_repo.garantir_padroes(con)
            ja_aplicado = self._configuracoes_repo.obter(con, CHAVE_EXEMPLO_APLICADO) == "1"
            if self.config.semear_exemplo and not ja_aplicado:
                self._semeador.semear(con, hoje)
            self._configuracoes_repo.salvar(con, CHAVE_EXEMPLO_APLICADO, "1")
