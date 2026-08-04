# AGENTS.md — ServerCRON

Contrato curto para qualquer agent de codigo (Claude Code, Codex, Cursor, etc.)
trabalhando neste repositorio. Detalhes completos e o "porque" de cada regra
estao em `CLAUDE.md` — leia os dois, este e so o resumo operacional.

## As 3 regras que mais importam aqui

1. **Nao entregar sem testar de verdade.** "Compilou" nao e "testei". Rode o
   endpoint/script/pagina de verdade e mostre o resultado antes de dizer que
   esta pronto. Isto ja causou um incidente real neste projeto (login que
   parecia ter bug de seguranca porque ninguem avisou sobre sessao
   reaproveitada do proprio teste do agent).
2. **Mudanca em autenticacao/permissoes = testar como atacante de fora.**
   `curl` sem sessao, token forjado, token ausente. Nao vale so testar no
   navegador onde voce (agent) ja logou durante o proprio teste — isso
   esconde bugs porque o navegador ja tem sessao valida.
3. **Se algo der errado ou faltar informacao, continue tentando corrigir**
   antes de devolver a tarefa. Se bater limite de uso/sessao a meio do
   trabalho, avise claramente o que foi (e o que NAO foi) testado — nunca
   presuma ou finja um resultado que nao foi verificado.

## Paths

- `Path.home()` para qualquer dado de utilizador/runtime. Nunca hardcode
  `C:\Users\<nome>\...`.
- O codigo do projeto fica relativo a `Path(__file__).resolve().parent`, nao
  sob `Path.home()`.
- Automacoes em `automacoes/*.py`: seguir `INSTRUCOES_AUTOMACAO_PYTHON.md`
  (retcodes 0/1/2, logs por execucao, Playwright com `channel="chrome"`,
  1920x1080, sem emojis, comentarios em pt-BR). Ler esse ficheiro antes de
  criar/alterar qualquer automacao — nao ha necessidade de repetir as regras
  aqui.

## Stack e restricoes

- Backend: Python (Flask + waitress). Frontend: HTML/CSS/JS puro, sem Node,
  sem build step, sem CDN. Isto e restricao explicita do dono do projeto, nao
  sugestao — nao introduzir npm/webpack/bundlers nem dependencias de front-end.
- CSP do server bloqueia `<script>` inline. JS de paginas novas vai sempre em
  ficheiro externo `static/*.js`.
- Mudou `server.py`? Reinicie o processo (porta 5001) antes de testar —
  Python nao recarrega sozinho. Mudou so `static/*`? Nao precisa reiniciar,
  so recarregar a pagina.

## Checklist antes de dizer "pronto"

- [ ] Rodei o teste automatizado relevante e colei o resultado real.
- [ ] Testei o caminho feliz E pelo menos um caminho de erro.
- [ ] Se mexi em login/permissoes: testei via curl, sem sessao/token nenhum.
- [ ] Reiniciei o server se mudei `server.py`.
- [ ] Disse ao utilizador exatamente o que foi testado e o que nao foi.

Para arquitetura completa, decisoes de auth, e o incidente que gerou a regra 1,
ver `CLAUDE.md`.
