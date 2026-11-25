"""Dados fictícios para o primeiro uso e para a demonstração pública."""

from __future__ import annotations

import calendar
import random
import sqlite3
from datetime import date

from .modelos import NovoLancamento, TipoLancamento
from .repositorios import CatalogoRepositorio, LancamentoRepositorio, OrcamentoRepositorio

METAS_DE_EXEMPLO = {
    "Moradia": 3000, "Alimentação": 1800, "Transporte": 600, "Saúde": 800,
    "Lazer": 400, "Educação": 300, "Assinaturas": 150, "Outros": 300,
}  # fmt: skip


class ExemploSemeador:
    """Cria seis meses de lançamentos plausíveis e as metas de gasto. Determinístico (semente fixa)."""

    def __init__(self, catalogo: CatalogoRepositorio, lancamentos: LancamentoRepositorio, orcamento: OrcamentoRepositorio):
        self._catalogo = catalogo
        self._lancamentos = lancamentos
        self._orcamento = orcamento

    def semear(self, con: sqlite3.Connection, hoje: date | None = None, semente: int = 7) -> int:
        hoje = hoje or date.today()
        sorteio = random.Random(semente)
        linhas: list[NovoLancamento] = []
        receita, despesa = TipoLancamento.RECEITA, TipoLancamento.DESPESA

        def quanto(minimo: float, maximo: float) -> int:
            return round(sorteio.uniform(minimo, maximo) * 100)

        for atras in range(5, -1, -1):
            indice = hoje.year * 12 + hoje.month - 1 - atras
            ano, mes = indice // 12, indice % 12 + 1
            ultimo_dia = calendar.monthrange(ano, mes)[1]
            mes_atual = atras == 0

            def adicionar(dia: int, descricao: str, categoria: str, tipo: TipoLancamento, centavos: int, conta: str,
                          pago: bool | None = None) -> None:  # fmt: skip
                data = date(ano, mes, min(dia, ultimo_dia))
                linhas.append(
                    NovoLancamento(
                        data=data,
                        descricao=descricao,
                        valor_centavos=centavos,
                        tipo=tipo,
                        categoria_id=self._catalogo.obter_ou_criar_categoria(con, categoria, tipo),
                        conta_id=self._catalogo.obter_ou_criar_conta(con, conta),
                        pago=(data <= hoje) if pago is None else pago,
                    )
                )

            corrente, cartao = "Conta corrente", "Cartão de crédito"
            adicionar(5, "Salário", "Salário", receita, 850000, corrente)
            adicionar(1, "Rendimentos", "Investimentos", receita, quanto(170, 270), "Poupança")
            if sorteio.random() < 0.45:
                adicionar(sorteio.randint(12, 25), "Projeto freelance", "Freelance", receita, quanto(1200, 2600), corrente)

            adicionar(10, "Aluguel", "Moradia", despesa, 220000, corrente)
            adicionar(10, "Condomínio", "Moradia", despesa, 48000, corrente)
            adicionar(15, "Energia elétrica", "Moradia", despesa, quanto(150, 260), corrente, False if mes_atual else None)
            adicionar(12, "Internet", "Moradia", despesa, 12000, corrente, False if mes_atual else None)

            for dia in (3, 10, 17, 24):
                adicionar(dia + sorteio.randint(0, 2), "Supermercado", "Alimentação", despesa, quanto(220, 460), cartao)
            for _ in range(sorteio.randint(3, 5)):
                nome = sorteio.choice(["Restaurante", "Lanche", "Delivery", "Padaria"])
                adicionar(sorteio.randint(1, 28), nome, "Alimentação", despesa, quanto(35, 140), cartao)

            for _ in range(2):
                adicionar(sorteio.randint(1, 28), "Combustível", "Transporte", despesa, quanto(180, 260), cartao)
            for _ in range(3):
                adicionar(sorteio.randint(1, 28), "Aplicativo de transporte", "Transporte", despesa, quanto(18, 48), cartao)

            adicionar(8, "Plano de saúde", "Saúde", despesa, 52000, corrente)
            adicionar(6, "Academia", "Saúde", despesa, 11000, cartao)
            for _ in range(sorteio.randint(1, 2)):
                adicionar(sorteio.randint(1, 28), "Farmácia", "Saúde", despesa, quanto(40, 150), cartao)

            adicionar(20, "Streaming de vídeo", "Assinaturas", despesa, 5500, cartao)
            adicionar(20, "Streaming de música", "Assinaturas", despesa, 2200, cartao)
            for _ in range(sorteio.randint(1, 3)):
                nome = sorteio.choice(["Cinema", "Show", "Passeio", "Bar com amigos"])
                adicionar(sorteio.randint(1, 28), nome, "Lazer", despesa, quanto(40, 160), cartao)
            if sorteio.random() < 0.4:
                adicionar(sorteio.randint(1, 28), "Curso online", "Educação", despesa, quanto(150, 400), cartao)
            for _ in range(sorteio.randint(1, 2)):
                adicionar(sorteio.randint(1, 28), "Compras diversas", "Outros", despesa, quanto(60, 320), cartao)

        total = self._lancamentos.inserir_varios(con, linhas)
        for categoria, limite in METAS_DE_EXEMPLO.items():
            categoria_id = self._catalogo.obter_ou_criar_categoria(con, categoria, despesa)
            self._orcamento.salvar(con, categoria_id, limite * 100)
        return total
