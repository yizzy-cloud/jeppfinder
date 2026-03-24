# Renegade Finder Online

Projeto pronto para publicar no Render e acessar pelo navegador, inclusive por terceiros.

## O que esta versão resolve
- acesso online por URL pública
- filtro padrão focado em Jeep Renegade Longitude 1.3 Turbo 2023 a 2025
- faixa de preço padrão entre R$ 90.000 e R$ 113.000
- persistência do histórico para marcar anúncios novos
- botão de varredura manual no painel
- endpoint protegido `/api/scan-secret` para disparo externo de atualização

## Como publicar no Render
1. Suba esta pasta para um repositório no GitHub.
2. No Render, crie um **Web Service** apontando para esse repositório.
3. Plano recomendado: **Starter**.
4. No momento da criação, em **Advanced**, adicione um **Persistent Disk** montado em `/var/data`.
5. Defina estas variáveis de ambiente:
   - `SECRET_KEY`
   - `SCAN_TOKEN`
   - `AUTOFORCE_TOKEN` (se tiver)
   - `DB_PATH=/var/data/renegade_finder.db`
6. Faça o deploy.

## Atualização automática
O painel já permite atualização manual. Para automação, há dois caminhos:
- usar um Cron Job do próprio Render e chamar `/api/scan-secret`
- usar outro agendador externo e chamar o mesmo endpoint com o header `X-Scan-Token`

## Observação importante
Sem disco persistente, o histórico some a cada novo deploy ou reinicialização. Nesse cenário, a marcação de anúncio novo perde confiabilidade.
