# Publicando

1. Servidor com Docker (VPS, ~1 GB de RAM basta) e um domínio apontando para o IP.
2. `git clone` do repositório, `cp .env.example .env`, defina `APP_PASSWORD` e `DOMINIO`.
3. `docker compose up -d --build` — o Caddy emite o certificado HTTPS sozinho.
4. Backup diário (cron): `docker compose exec -T app python -m app.cli backup --pasta /data/backups`.

**Demonstração pública no GitHub/LinkedIn:** suba uma segunda instância com `DEMO_MODE=1` e `REPO_URL=https://github.com/SEU-USUARIO/prumo`. Ela usa um banco temporário com dados fictícios e é somente leitura; seus dados reais nunca ficam expostos. Nunca faça commit do `.env` nem de arquivos `*.db`.
