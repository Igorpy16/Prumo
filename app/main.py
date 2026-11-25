"""Ponto de entrada: `uvicorn app.main:app`."""

from .fabrica import criar_app

app = criar_app()
