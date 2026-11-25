# Prumo — controle financeiro pessoal

**[▶ Ver demo](https://prumo-demo.onrender.com)** — somente leitura, com dados fictícios. No plano gratuito, a primeira visita pode levar até ~1 min enquanto o servidor acorda.

Veja para onde vai o seu dinheiro: receitas, despesas, metas por categoria, importação/exportação de CSV e indicadores do mercado (Selic, CDI, IPCA, dólar) vindos do Banco Central.

- **Front-end:** site de rolagem contínua em JavaScript puro (módulos ES), gráficos em SVG, tema claro/escuro, sem CDN.
- **Back-end:** FastAPI organizado em camadas orientadas a objetos: `Configuracoes` → `Database` → `Repositorios` (só SQL) → `Servicos` (regras) → rotas HTTP.
- **Banco:** SQLite com tabelas `STRICT`, chaves estrangeiras (inclusive composta categoria+tipo), `CHECK`, view, trigger, índices parciais, CTE recursiva para a série mensal, migrações versionadas e dinheiro em centavos inteiros.
- **Docker:** imagem multi-stage, usuário sem privilégios, sistema de arquivos somente leitura, volume de dados e HTTPS automático com Caddy.

## Rodando sem Docker

```bash
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Abra http://127.0.0.1:8000. Sem `APP_PASSWORD` o app fica aberto (uso local) e cria dados de exemplo na primeira execução (`SEMEAR_DEMO=0` desliga).

## Demonstração online

A demo roda no plano gratuito do Render a partir do [`render.yaml`](render.yaml), com `DEMO_MODE=1`: somente leitura, dados fictícios e nenhum dado real exposto. Para publicar sua própria cópia, use o botão:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Igorpy16/Prumo)

## Rodando com Docker

```bash
cp .env.example .env            # defina APP_PASSWORD (mín. 8 caracteres)
docker compose up -d --build
```

Acesse https://localhost (ou o domínio definido em `DOMINIO`). Backup: `docker compose exec app python -m app.cli backup --pasta /data/backups`.

## Configuração (variáveis de ambiente)

| Variável | Para quê |
|---|---|
| `APP_PASSWORD` | Senha de acesso. Obrigatória no Docker (`REQUIRE_AUTH=1`). |
| `SECRET_KEY` | Chave de assinatura da sessão (padrão: derivada da senha). |
| `DATABASE_PATH` | Arquivo SQLite (`/data/prumo.db` no Docker). |
| `SEMEAR_DEMO` | `0` não cria dados de exemplo. |
| `DEMO_MODE=1` | Versão pública: somente leitura, dados fictícios, banco temporário isolado, sem login. |
| `REPO_URL` | Link mostrado na faixa da demonstração (https). |
| `INDICADORES=0` | Desliga a consulta ao Banco Central. |

## Indicadores de mercado (API externa)

Os valores vêm da API de Dados Abertos do Banco Central (SGS), com cache de 1 hora, tolerância a falhas por indicador e último valor salvo no banco quando o BCB não responde (a tela avisa que está desatualizado). Códigos das séries: Selic meta 432, CDI 4389, IPCA mensal 433 (acumulado em 12 meses calculado por encadeamento) e dólar PTAX venda 1. Ficam em `app/integracoes/bcb.py`.

Para conferir ao vivo na sua máquina:

```bash
python -c "from app.integracoes.bcb import ClienteBCB; print(ClienteBCB().buscar())"
```

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Créditos

- **Dados de mercado:** [Banco Central do Brasil — Dados Abertos (SGS)](https://dadosabertos.bcb.gov.br), licença [Open Data Commons Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/). Este projeto não é afiliado nem endossado pelo Banco Central do Brasil.
- **Fontes:** [Bricolage Grotesque](https://github.com/ateliertriay/bricolage) e [Figtree](https://github.com/erikdkennedy/figtree), licença SIL OFL 1.1, distribuídas via [Fontsource](https://fontsource.org). As licenças estão em `web/assets/fonts/`.
- **Tecnologias:** [FastAPI](https://fastapi.tiangolo.com), [Starlette](https://www.starlette.io), [Uvicorn](https://www.uvicorn.org), [Pydantic](https://docs.pydantic.dev), [SQLite](https://sqlite.org), [Docker](https://www.docker.com), [Caddy](https://caddyserver.com).
- **Autoria:** [Seu Nome](https://github.com/SEU-USUARIO). Construído com apoio do Claude (Anthropic).
