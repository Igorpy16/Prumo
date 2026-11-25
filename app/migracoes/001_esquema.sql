-- Esquema inicial do Prumo.
--
-- Decisões de modelagem:
--  * Dinheiro em CENTAVOS (INTEGER): somas exatas, sem erro de ponto flutuante.
--  * Datas em texto ISO-8601 (AAAA-MM-DD): ordenam e comparam corretamente.
--  * Tabelas STRICT: o SQLite recusa um valor do tipo errado em vez de convertê-lo em silêncio.
--  * Integridade garantida pelo próprio banco (CHECK, UNIQUE, chaves estrangeiras),
--    e não só pela aplicação.

CREATE TABLE contas (
    id        INTEGER PRIMARY KEY,
    nome      TEXT    NOT NULL CHECK (length(nome) BETWEEN 1 AND 60),
    chave     TEXT    NOT NULL UNIQUE,              -- nome sem acento/caixa: impede "Cartão" e "cartao"
    criada_em TEXT    NOT NULL DEFAULT (datetime('now'))
) STRICT;

CREATE TABLE categorias (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL CHECK (length(nome) BETWEEN 1 AND 60),
    chave TEXT NOT NULL,
    tipo  TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    UNIQUE (chave, tipo),
    UNIQUE (id, tipo)                               -- alvo da chave estrangeira composta abaixo
) STRICT;

CREATE TABLE lancamentos (
    id             INTEGER PRIMARY KEY,
    data           TEXT    NOT NULL CHECK (date(data) IS data),   -- rejeita "2026-02-30" e formatos soltos
    descricao      TEXT    NOT NULL CHECK (length(descricao) BETWEEN 1 AND 120),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    tipo           TEXT    NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    categoria_id   INTEGER NOT NULL,
    conta_id       INTEGER NOT NULL REFERENCES contas (id),
    pago           INTEGER NOT NULL DEFAULT 1 CHECK (pago IN (0, 1)),
    criado_em      TEXT    NOT NULL DEFAULT (datetime('now')),
    atualizado_em  TEXT    NOT NULL DEFAULT (datetime('now')),
    -- (categoria, tipo) precisa existir em categorias: uma despesa nunca aponta para categoria de receita.
    FOREIGN KEY (categoria_id, tipo) REFERENCES categorias (id, tipo)
) STRICT;

-- Meta mensal de gasto por categoria (só categorias de despesa).
CREATE TABLE orcamentos (
    categoria_id    INTEGER PRIMARY KEY,
    tipo            TEXT    NOT NULL DEFAULT 'despesa' CHECK (tipo = 'despesa'),
    limite_centavos INTEGER NOT NULL CHECK (limite_centavos > 0),
    FOREIGN KEY (categoria_id, tipo) REFERENCES categorias (id, tipo) ON DELETE CASCADE
) STRICT;

CREATE TABLE configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
) STRICT;

-- Índices pensados para as consultas reais do painel.
CREATE INDEX idx_lancamentos_data       ON lancamentos (data);
CREATE INDEX idx_lancamentos_tipo_data  ON lancamentos (tipo, data);
CREATE INDEX idx_lancamentos_categoria  ON lancamentos (categoria_id, data);
CREATE INDEX idx_lancamentos_conta      ON lancamentos (conta_id);
CREATE INDEX idx_lancamentos_pendentes  ON lancamentos (data) WHERE pago = 0;   -- índice parcial

-- Visão com os nomes já resolvidos: a aplicação lê daqui, sem repetir JOINs.
CREATE VIEW v_lancamentos AS
SELECT l.id,
       l.data,
       l.descricao,
       l.valor_centavos,
       l.tipo,
       l.pago,
       l.categoria_id,
       c.nome  AS categoria,
       l.conta_id,
       ct.nome AS conta
  FROM lancamentos l
  JOIN categorias c  ON c.id  = l.categoria_id
  JOIN contas     ct ON ct.id = l.conta_id;

-- Mantém "atualizado_em" correto sem depender da aplicação.
CREATE TRIGGER trg_lancamentos_atualizado
AFTER UPDATE ON lancamentos
FOR EACH ROW WHEN NEW.atualizado_em = OLD.atualizado_em
BEGIN
    UPDATE lancamentos SET atualizado_em = datetime('now') WHERE id = NEW.id;
END;
