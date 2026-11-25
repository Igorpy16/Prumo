"""Importação e exportação de CSV."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from ..database import Database
from ..erros import RegraDeNegocio
from ..esquemas import DATA_MAXIMA, DATA_MINIMA, TETO_VALOR
from ..filtros import FiltroLancamentos
from ..modelos import NovoLancamento, TipoLancamento
from ..repositorios import CatalogoRepositorio, LancamentoRepositorio
from ..util import Moeda, colapsar_espacos, neutralizar_formula, normalizar

_TIPOS_RECEITA = {"receita", "entrada", "credito", "c"}
_TIPOS_DESPESA = {"despesa", "saida", "debito", "gasto", "d"}
_NAO_PAGO = {"nao", "n", "0", "false", "pendente", "aberto"}


@dataclass(slots=True)
class ResultadoImportacao:
    importados: int = 0
    ignorados: int = 0
    erros: list[str] = field(default_factory=list)


class ConversorDeLinha:
    """Converte textos do CSV (em formato brasileiro ou ISO) nos tipos do domínio."""

    @staticmethod
    def data(texto: str) -> date:
        texto = texto.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
            try:
                valor = datetime.strptime(texto, formato).date()
            except ValueError:
                continue
            if not DATA_MINIMA <= valor <= DATA_MAXIMA:
                raise ValueError(f"data fora do intervalo aceito ({texto})")
            return valor
        raise ValueError(f"data inválida ({texto or 'vazia'})")

    @staticmethod
    def valor(texto: str) -> int:
        """'R$ 1.234,56', '1234.56' e '-89,90' viram centavos positivos."""
        limpo = re.sub(r"[^\d,.\-]", "", texto)
        if not limpo:
            raise ValueError("valor vazio")
        if "," in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif limpo.count(".") > 1:
            limpo = limpo.replace(".", "")
        try:
            numero = abs(Decimal(limpo))
        except InvalidOperation:
            raise ValueError(f"valor inválido ({texto})") from None
        numero = numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if numero <= 0 or numero > TETO_VALOR:
            raise ValueError(f"valor fora do intervalo aceito ({texto})")
        return Moeda.para_centavos(numero)

    @staticmethod
    def tipo(texto: str) -> TipoLancamento:
        chave = normalizar(texto)
        if chave in _TIPOS_RECEITA:
            return TipoLancamento.RECEITA
        if chave in _TIPOS_DESPESA:
            return TipoLancamento.DESPESA
        raise ValueError(f"tipo desconhecido ({texto or 'vazio'})")

    @staticmethod
    def pago(texto: str) -> bool:
        return normalizar(texto) not in _NAO_PAGO


@dataclass(frozen=True, slots=True)
class _LinhaValida:
    data: date
    descricao: str
    categoria: str
    tipo: TipoLancamento
    centavos: int
    conta: str
    pago: bool


class ImportacaoServico:
    LIMITE_BYTES = 5_000_000
    LIMITE_LINHAS = 20_000
    OBRIGATORIAS = ("data", "descricao", "categoria", "tipo", "valor")

    def __init__(self, db: Database, catalogo: CatalogoRepositorio, lancamentos: LancamentoRepositorio):
        self._db = db
        self._catalogo = catalogo
        self._lancamentos = lancamentos

    @staticmethod
    def _decodificar(bruto: bytes) -> str:
        try:
            return bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            return bruto.decode("cp1252", errors="replace")  # "CSV" do Excel em português

    @staticmethod
    def _separador(texto: str) -> str:
        primeira = texto.splitlines()[0] if texto else ""
        return max(";,\t|", key=lambda s: (primeira.count(s), s == ";"))

    def _converter(self, celulas: list[str], posicao: dict[str, int]) -> _LinhaValida:
        def campo(nome: str) -> str:
            indice = posicao.get(nome)
            return celulas[indice].strip() if indice is not None and indice < len(celulas) else ""

        descricao, categoria = colapsar_espacos(campo("descricao"))[:120], colapsar_espacos(campo("categoria"))[:60]
        if not descricao or not categoria:
            raise ValueError("descrição ou categoria vazia")
        conta = colapsar_espacos(campo("conta"))[:60] or "Conta corrente"
        return _LinhaValida(
            data=ConversorDeLinha.data(campo("data")),
            descricao=descricao,
            categoria=categoria,
            tipo=ConversorDeLinha.tipo(campo("tipo")),
            centavos=ConversorDeLinha.valor(campo("valor")),
            conta=conta,
            pago=ConversorDeLinha.pago(campo("pago")) if "pago" in posicao else True,
        )

    def importar(self, bruto: bytes) -> ResultadoImportacao:
        if len(bruto) > self.LIMITE_BYTES:
            raise RegraDeNegocio("Arquivo grande demais (máximo de 5 MB).")
        texto = self._decodificar(bruto)
        linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=self._separador(texto)))
        if not linhas:
            raise RegraDeNegocio("O arquivo está vazio.")

        posicao: dict[str, int] = {}
        for indice, titulo in enumerate(linhas[0]):
            posicao.setdefault(normalizar(titulo), indice)
        faltando = [c for c in self.OBRIGATORIAS if c not in posicao]
        if faltando:
            raise RegraDeNegocio(
                "Colunas ausentes: " + ", ".join(faltando) + ". Esperado: Data, Descrição, Categoria, Tipo, Valor "
                "(e, opcionais, Conta e Pago)."
            )
        corpo = linhas[1:]
        if len(corpo) > self.LIMITE_LINHAS:
            raise RegraDeNegocio(f"Linhas demais (máximo de {self.LIMITE_LINHAS}).")

        resultado = ResultadoImportacao()
        validas: list[_LinhaValida] = []
        for numero, celulas in enumerate(corpo, start=2):
            if not any(c.strip() for c in celulas):
                continue
            try:
                validas.append(self._converter(celulas, posicao))
            except ValueError as erro:
                resultado.ignorados += 1
                if len(resultado.erros) < 10:
                    resultado.erros.append(f"linha {numero}: {erro}")

        if validas:
            with self._db.transacao() as con:
                categorias: dict[tuple[str, TipoLancamento], int] = {}
                contas: dict[str, int] = {}
                novos = []
                for v in validas:
                    chave_cat = (normalizar(v.categoria), v.tipo)
                    if chave_cat not in categorias:
                        categorias[chave_cat] = self._catalogo.obter_ou_criar_categoria(con, v.categoria, v.tipo)
                    chave_conta = normalizar(v.conta)
                    if chave_conta not in contas:
                        contas[chave_conta] = self._catalogo.obter_ou_criar_conta(con, v.conta)
                    novos.append(
                        NovoLancamento(
                            v.data, v.descricao, v.centavos, v.tipo, categorias[chave_cat], contas[chave_conta], v.pago
                        )
                    )
                resultado.importados = self._lancamentos.inserir_varios(con, novos)
        return resultado


class ExportacaoServico:
    CABECALHO = ("Data", "Descrição", "Categoria", "Tipo", "Valor", "Conta", "Pago")

    def __init__(self, db: Database, lancamentos: LancamentoRepositorio):
        self._db = db
        self._lancamentos = lancamentos

    def gerar_csv(self, filtro: FiltroLancamentos) -> bytes:
        """CSV com ';' e vírgula decimal (abre direto no Excel em português), com BOM UTF-8."""
        with self._db.leitura() as con:
            itens = self._lancamentos.listar(con, filtro)
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
        escritor.writerow(self.CABECALHO)
        for i in itens:
            escritor.writerow(
                (
                    i.data.isoformat(),
                    neutralizar_formula(i.descricao),
                    neutralizar_formula(i.categoria),
                    i.tipo.value.capitalize(),
                    Moeda.formatar_csv(i.valor_centavos),
                    neutralizar_formula(i.conta),
                    "Sim" if i.pago else "Não",
                )
            )
        return ("﻿" + saida.getvalue()).encode("utf-8")
