import sqlite3

import pytest


def test_migracao_aplicada_e_idempotente(container):
    assert container.db.versao() == 1
    container.db.migrar()
    assert container.db.versao() == 1


def test_data_invalida_e_recusada_pelo_banco(container):
    with pytest.raises(sqlite3.IntegrityError):
        with container.db.transacao() as con:
            con.execute(
                "INSERT INTO lancamentos(data,descricao,valor_centavos,tipo,categoria_id,conta_id,pago) "
                "VALUES('2026-13-45','x',100,'despesa',(SELECT id FROM categorias WHERE tipo='despesa' LIMIT 1),1,1)"
            )


def test_categoria_precisa_combinar_com_o_tipo(container):
    with pytest.raises(sqlite3.IntegrityError):
        with container.db.transacao() as con:
            rec = con.execute("SELECT id FROM categorias WHERE tipo='receita' LIMIT 1").fetchone()[0]
            con.execute(
                "INSERT INTO lancamentos(data,descricao,valor_centavos,tipo,categoria_id,conta_id,pago) "
                "VALUES('2026-01-01','x',100,'despesa',?,1,1)",
                (rec,),
            )


def test_valor_precisa_ser_positivo(container):
    with pytest.raises(sqlite3.IntegrityError):
        with container.db.transacao() as con:
            cat = con.execute("SELECT id FROM categorias WHERE tipo='despesa' LIMIT 1").fetchone()[0]
            con.execute(
                "INSERT INTO lancamentos(data,descricao,valor_centavos,tipo,categoria_id,conta_id,pago) "
                "VALUES('2026-01-01','x',0,'despesa',?,1,1)",
                (cat,),
            )


def test_rollback_em_erro(container):
    with pytest.raises(RuntimeError):
        with container.db.transacao() as con:
            con.execute("INSERT INTO contas(nome, chave) VALUES('Temp','temp')")
            raise RuntimeError
    with container.db.leitura() as con:
        assert con.execute("SELECT COUNT(*) FROM contas WHERE chave='temp'").fetchone()[0] == 0


def test_backup_consistente(container, tmp_path):
    destino = tmp_path / "copia.db"
    container.db.copia_de_seguranca(destino)
    assert sqlite3.connect(destino).execute("PRAGMA quick_check").fetchone()[0] == "ok"
