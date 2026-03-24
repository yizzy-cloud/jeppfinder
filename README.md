# Renegade Finder Online

Versão aprimorada para o Render.

## O que mudou

- interface mais forte, com cards e links diretos para anúncio ou loja
- área de candidatos próximos quando o filtro principal zerar
- score de relevância por anúncio
- tentativa adicional de capturar links reais de detalhe
- modo de filtro estrito opcional

## Deploy

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Health Check Path: `/api/health`
- Variáveis mínimas:
  - `SECRET_KEY`
  - `SCAN_TOKEN`
  - `DB_PATH=/tmp/renegade_finder.db`

## Observação importante

Sem `AUTOFORCE_TOKEN`, parte das lojas AutoForce pode depender do fallback HTML público. Isso pode trazer menos detalhes que a API oficial.
