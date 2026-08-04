# CLAUDE.md — ServerCRON

Instrucoes para Claude Code (ou qualquer agent) trabalhando neste repositorio.
Leia isto antes de mexer em `server.py`, `static/*`, ou em qualquer automacao
dentro de `automacoes/`.

## Regra numero 1: nunca entregar algo sem testar de verdade

Isto ja causou um incidente real neste projeto (login que parecia burlavel por
causa de sessao reaproveitada nao avisada). Nao repetir.

- **"Testei" so conta se voce rodou o teste, viu o resultado, e o resultado bate
  com o que voce esta afirmando.** Nao afirme "corrigido" ou "testado" so porque
  o codigo compilou ou porque "parece certo".
- Para mudanca de **backend** (`server.py`): reinicie o servidor (mata o processo
  antigo na porta 5001, sobe de novo com `SERVERCRON_SKIP_REQUIREMENTS_PIP=1`) e
  chame o endpoint de verdade (curl ou browser) antes de dizer que funciona.
- Para mudanca de **frontend** (`static/*.js`, `*.html`, `*.css`): nao precisa
  reiniciar o server, mas precisa recarregar a pagina e observar o resultado —
  nao basta o JS "parecer" correto. `node --check arquivo.js` so pega erro de
  sintaxe, nao pega logica errada nem CSP bloqueando script inline.
- Para mudanca em **autenticacao/seguranca/permissoes**: o padrao minimo e
  testar como um atacante de fora testaria, nao so o caminho feliz:
  - Requisicao **sem** token/sessao.
  - Requisicao com token **forjado/chutado**.
  - `curl` puro (sem navegador, sem localStorage, sem sessao previa) simulando
    "outro PC" — isso pega bugs que testar no proprio navegador esconde,
    porque o navegador pode ja ter uma sessao valida de um teste anterior.
  - Se usar o Chrome do proprio utilizador (extensao claude-in-chrome) pra
    testar login: **avisar explicitamente** que isso deixa uma sessao valida
    salva no navegador dele. Nao deixar o utilizador descobrir isso sozinho
    e achar que e bug de seguranca.
  - CSP do server bloqueia `<script>` inline (`script-src 'self'`) — JS de
    paginas novas tem de ir em ficheiro externo `static/*.js`, nunca inline.
    Isso ja causou um bug real (login nao funcionava, formulario caia no
    submit nativo do HTML).
- Quando encontrar um erro a meio da tarefa: **continue corrigindo** ate
  resolver ou ate ficar genuinamente bloqueado por falta de informacao/decisao
  do utilizador. Nao entregue "codigo com um bug conhecido" sem avisar bem
  claro que ha um bug e qual e.
- Escreva um teste automatizado quando mexer em autenticacao, permissoes, ou
  regras de negocio com dinheiro/dados sensiveis (ver `_test_auth.py` como
  modelo: usa `Flask test_client`, sem precisar subir o server de verdade).
  Rode-o **de novo** a cada mudanca relacionada, nao so na primeira vez.

## Se bater limite de uso / sessao a meio da tarefa

- Avisar o utilizador de forma clara e direta (nao sumir, nao fingir que
  terminou). Dizer o que ja foi feito, testado e confirmado, e o que ainda
  esta pendente/nao verificado.
- Nunca inventar ou presumir o resultado de um teste que nao rodou por causa
  do limite. Se nao testou, diga "nao testado ainda" — nao "deve funcionar".
  Não fingir sucesso para o usuario.
- Ao retomar: reler o que ja foi feito antes de continuar (nao repetir
  trabalho nem contradizer decisoes ja tomadas na conversa).

## Paths: sempre `Path.home()`, nunca hardcode

- Nunca escrever `C:\Users\abobi\...` ou qualquer caminho de utilizador
  hardcoded em codigo, scripts `.bat`, ou docs que vao para o repo/GitHub.
- Dados de runtime (logs, sqlite, config) ficam sob
  `Path.home() / "Documents" / "ServerCRON"` (ver `DATA_ROOT` em `server.py`).
- O projeto em si (`server.py`, `static/`, `automacoes/`, planilha) fica na
  pasta do repo (`Path(__file__).resolve().parent`), nao sob `Path.home()`.
- Automacoes individuais (os `.py` dentro de `automacoes/`): seguem
  `INSTRUCOES_AUTOMACAO_PYTHON.md` — esse ficheiro ja define paths, retcodes
  (0/1/2), logs por execucao, Playwright, etc. **Leia-o antes de criar ou
  alterar qualquer automacao.** Nao duplicar essas regras aqui.

## Arquitetura rapida

- Backend: Flask + waitress, `server.py` unico, sem framework de front-end.
- Frontend: HTML/CSS/JS puro sob `static/` — **sem Node, sem build step, sem
  bibliotecas externas via CDN** (restricao explicita do utilizador: só
  Python + o que o Chrome ja suporta nativamente).
- Autenticacao: login por email (aba `USERS` da planilha) + token
  (`SERVERCRON_API_TOKEN` no `.env`) juntos — email sozinho NAO e segredo,
  entao nunca aceitar login so com email quando o token estiver configurado.
  Sessao por email e unica (novo login no mesmo email derruba a sessao
  anterior). Ver `_test_auth.py` para o contrato de seguranca esperado.
- Tela de login (`static/login.html` + `login.js`) e separada da app
  (`static/index.html` + `app.js`) de proposito — nunca voltar a botar
  login como dialog dentro da mesma pagina que mostra dados do painel.
- 3 superficies de dashboard (web ao vivo, HTML avulso em `dashboards/`,
  Excel em `dashboards/`) puxam a mesma logica de KPI mas tem implementacoes
  separadas — mudanca de metrica/formula precisa ser replicada nas 3 (ou
  proposta como refactor explicito, nao silenciosamente so numa).

## Antes de considerar uma tarefa concluida

- [ ] Rodei o teste automatizado relevante (`_test_auth.py` ou equivalente) e
      todos os checks passaram — colei o resultado, nao so afirmei.
- [ ] Testei manualmente o caminho principal E pelo menos um caminho de erro.
- [ ] Se mexi em auth: testei como atacante de fora (curl sem sessao).
- [ ] Se mexi em JS/HTML novo: confirmei que carrega sem erro de CSP/console.
- [ ] Reiniciei o server se mexi em `server.py` (mudanca de Python nao
      aplica sozinha; o processo antigo continua rodando o codigo velho).
- [ ] Contei ao utilizador exatamente o que testei e o que NAO testei.
