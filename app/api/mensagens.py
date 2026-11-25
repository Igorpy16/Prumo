"""Tradução das mensagens de validação do Pydantic para português."""

from __future__ import annotations

from typing import Any

_ROTULOS = {
    "data": "Data", "descricao": "Descrição", "valor": "Valor", "tipo": "Tipo", "categoria": "Categoria",
    "conta": "Conta", "pago": "Situação", "limite": "Limite", "senha": "Senha", "metas": "Metas",
}  # fmt: skip

_TRADUCOES = {
    "missing": "Campo obrigatório.",
    "string_too_short": "Preencha este campo.",
    "string_too_long": "Texto longo demais.",
    "greater_than": "Informe um valor maior que zero.",
    "less_than_equal": "Valor acima do permitido.",
    "greater_than_equal": "Valor abaixo do permitido.",
    "decimal_max_places": "Use no máximo 2 casas decimais.",
    "decimal_max_digits": "Número grande demais.",
    "decimal_parsing": "Número inválido.",
    "date_from_datetime_parsing": "Data inválida.",
    "date_parsing": "Data inválida.",
    "date_type": "Data inválida.",
    "enum": "Opção inválida.",
    "bool_parsing": "Valor inválido.",
    "extra_forbidden": "Campo não reconhecido.",
    "json_invalid": "Corpo da requisição inválido.",
}  # fmt: skip


def traduzir_erros_de_validacao(erros: list[dict[str, Any]]) -> dict[str, Any]:
    campos: dict[str, str] = {}
    for e in erros:
        local = [str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path")]
        nome = local[-1] if local else "requisição"
        if e.get("type") == "value_error":
            texto = str(e.get("msg", "")).removeprefix("Value error, ")
        else:
            texto = _TRADUCOES.get(e.get("type", ""), "Valor inválido.")
        campos.setdefault(nome, texto)
    primeiro_nome, primeiro_texto = next(iter(campos.items()), ("requisição", "Dados inválidos."))
    rotulo = _ROTULOS.get(primeiro_nome, primeiro_nome.capitalize())
    return {"detail": f"{rotulo}: {primeiro_texto}", "campos": campos}
