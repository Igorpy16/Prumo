from conftest import lancamento


def criar(cliente, **o):
    r = cliente.post("/api/lancamentos", json=lancamento(**o))
    assert r.status_code == 201, r.text
    return r.json()


def test_crud_completo(cliente):
    item = criar(cliente)
    assert item["valor"] == 100.0 and item["categoria"] == "Alimentação"
    r = cliente.put(f"/api/lancamentos/{item['id']}", json=lancamento(valor="250.55", descricao="Feira"))
    assert r.json()["valor"] == 250.55
    r = cliente.patch(f"/api/lancamentos/{item['id']}/pago", json={"pago": False})
    assert r.json()["pago"] is False
    assert cliente.delete(f"/api/lancamentos/{item['id']}").status_code == 204
    assert cliente.delete(f"/api/lancamentos/{item['id']}").status_code == 404


def test_validacao_em_portugues(cliente):
    r = cliente.post("/api/lancamentos", json=lancamento(valor="-5", descricao=""))
    assert r.status_code == 422
    assert "campos" in r.json() and "valor" in r.json()["campos"]
    assert cliente.post("/api/lancamentos", json=lancamento(valor="1.234")).status_code == 422
    assert cliente.post("/api/lancamentos", json=lancamento(data="1999-01-01")).status_code == 422
    assert cliente.post("/api/lancamentos", json={**lancamento(), "extra": 1}).status_code == 422


def test_dinheiro_sem_erro_de_ponto_flutuante(cliente):
    for _ in range(10):
        criar(cliente, valor="0.10")
    r = cliente.get("/api/resumo?inicio=2026-10-01&fim=2026-10-31").json()
    assert r["kpis"]["despesas"] == 1.0


def test_filtros_e_busca_sem_acento(cliente):
    criar(cliente, descricao="Padaria São João")
    criar(cliente, descricao="Cinema", categoria="Lazer")
    assert cliente.get("/api/lancamentos?busca=sao joao").json()["total"] == 1
    assert cliente.get("/api/lancamentos?busca=100%25").json()["total"] == 0
    assert cliente.get("/api/lancamentos?tipo=receita").json()["total"] == 0
    r = cliente.get("/api/lancamentos?inicio=2026-12-01&fim=2026-11-01")
    assert r.status_code == 422


def test_filtro_por_varias_categorias(cliente):
    a = criar(cliente)
    b = criar(cliente, categoria="Lazer")
    criar(cliente, categoria="Saúde")
    r = cliente.get(f"/api/lancamentos?categoria={a['categoria_id']}&categoria={b['categoria_id']}")
    assert r.json()["total"] == 2


def test_paginacao(cliente):
    for i in range(25):
        criar(cliente, descricao=f"Item {i}")
    r = cliente.get("/api/lancamentos?tamanho=10&pagina=3").json()
    assert r["total"] == 25 and r["paginas"] == 3 and len(r["itens"]) == 5
    assert cliente.get("/api/lancamentos?tamanho=500").status_code == 422


def test_resumo(cliente):
    criar(cliente, tipo="receita", categoria="Salário", valor="1000")
    criar(cliente, valor="300")
    criar(cliente, valor="200", pago=False)
    r = cliente.get("/api/resumo?inicio=2026-10-01&fim=2026-10-31").json()
    assert r["kpis"]["receitas"] == 1000 and r["kpis"]["despesas"] == 500
    assert r["kpis"]["saldo"] == 500 and r["kpis"]["a_pagar"] == 200
    assert r["categorias"][0]["nome"] == "Alimentação"
    assert r["mensal"]["meses"][-1] == "2026-10"


def test_resumo_vazio(cliente):
    assert cliente.get("/api/resumo").json()["vazio"] is True


def test_orcamento(cliente):
    cat = criar(cliente, valor="400")["categoria_id"]
    r = cliente.put("/api/orcamento/metas", json={"metas": [{"categoria_id": cat, "limite": "500"}]})
    assert r.status_code == 200
    o = cliente.get("/api/orcamento?mes=2026-10").json()
    item = next(i for i in o["itens"] if i["categoria_id"] == cat)
    assert item["gasto"] == 400 and item["percentual"] == 80.0
    assert cliente.get("/api/orcamento?mes=2026-13").status_code in (422,)
    cliente.put("/api/orcamento/metas", json={"metas": [{"categoria_id": cat, "limite": "0"}]})
    assert all(m["limite"] == 0 for m in cliente.get("/api/orcamento/metas").json())


def test_exportar_e_importar_ida_e_volta(cliente):
    criar(cliente, descricao="=SOMA(A1)", valor="12.34")
    csv = cliente.get("/api/exportar.csv").content
    assert csv.startswith(b"\xef\xbb\xbf") and b"'=SOMA" in csv  # fórmula neutralizada
    cliente.delete("/api/lancamentos?confirmar=true")
    r = cliente.post("/api/importar", files={"arquivo": ("l.csv", csv, "text/csv")}).json()
    assert r["importados"] == 1 and r["erros"] == []


def test_importar_formato_brasileiro_e_erros(cliente):
    texto = "data;descricao;categoria;tipo;valor\n05/10/2026;Luz;Moradia;despesa;1.234,56\nxx;Ruim;Moradia;despesa;1\n"
    r = cliente.post("/api/importar", files={"arquivo": ("a.csv", texto.encode("cp1252"), "text/csv")}).json()
    assert r["importados"] == 1 and r["ignorados"] == 1 and r["erros"]  # linha ruim é ignorada e relatada


def test_excluir_todos_exige_confirmacao(cliente):
    criar(cliente)
    assert cliente.delete("/api/lancamentos").status_code == 422
    assert cliente.delete("/api/lancamentos?confirmar=true").json()["excluidos"] == 1


def test_exemplo_nao_volta_depois_de_apagar(tmp_path):
    from fastapi.testclient import TestClient

    from app.fabrica import criar_app
    from conftest import montar

    cfg = montar(tmp_path, SEMEAR_DEMO="1")
    c = TestClient(criar_app(cfg))
    assert c.get("/api/lancamentos").json()["total"] > 50
    c.delete("/api/lancamentos?confirmar=true")
    c2 = TestClient(criar_app(cfg))  # reinício
    assert c2.get("/api/lancamentos").json()["total"] == 0


def test_cabecalhos_de_seguranca(cliente):
    r = cliente.get("/healthz")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert cliente.get("/api/meta").headers["cache-control"] == "no-store"
