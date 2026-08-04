# ServerCRON

Agendador de scripts Python controlado por planilha Excel. Backend em Python
(Flask + Waitress); painel em HTML, CSS e JavaScript nativos (sem CDN, sem React).

Repositorio: https://github.com/caducosilva/ServerCRON

## Como funciona

1. Pasta `automacoes/` (junto de `server.py`) com os scripts `.py`.
2. Na **raiz do projeto** fica `registro_automacoes.xlsx` (copie do exemplo).
3. Dentro de `automacoes/`, organize por areas e subpastas; o servidor faz
   **pesquisa recursiva** por `{nome_automacao}.py`:

```
ServerCRON/
  server.py
  install_deps.bat
  registro_automacoes.xlsx          # local (nao versionado)
  registro_automacoes.example.xlsx  # modelo no GitHub
  automacoes/
    financeiro/
      mensal/
        backup_diario.py
    teste/
      abrir_calculadora.py
    exemplo/
      exemplo_hello.py
  static/
    index.html
    style.css
    app.js
```

4. Colunas da planilha (aba `AUTOMACOES`):

| nome_automacao | cron_schedule | is_active |
|----------------|---------------|-----------|
| exemplo_hello  | `0 8 * * 1-5` | TRUE      |
| backup_diario  | `0 2 * * *`   | FALSE     |

5. Aba `USERS` (opcional): emails autorizados para login por OTP.
6. `nome_automacao` e o nome do Python em qualquer profundidade.
7. O servidor agenda conforme `cron_schedule` (fuso `America/Sao_Paulo` por defeito).
8. `is_active` = TRUE agenda; FALSE ignora.

Na primeira execucao, se a pasta/planilha nao existirem, o ServerCRON pode criar
estrutura basica. Preferivel copiar o exemplo:

```powershell
copy registro_automacoes.example.xlsx registro_automacoes.xlsx
```

Dados de runtime ficam em `Path.home() / "Documents" / "ServerCRON"` (ou
`SERVERCRON_DATA_ROOT`):

- `server_cron.sqlite` (ultimas execucoes do painel)
- `logs/historico_execucoes.csv` (historico completo)

## Instalacao

```bash
git clone https://github.com/caducosilva/ServerCRON.git
cd ServerCRON
copy registro_automacoes.example.xlsx registro_automacoes.xlsx
python server.py
```

No arranque, o `server.py` pode correr o `install_deps.bat` (`pip install -r
requirements.txt`), reiniciar o processo e subir o servidor.

Para saltar a instalacao (deps ja instaladas):

```bash
set SERVERCRON_SKIP_REQUIREMENTS_PIP=1
python server.py
```

Painel: http://127.0.0.1:5001/

## Autenticacao

- Uso local em `127.0.0.1`: painel pode ficar aberto.
- Expor na rede (`SERVERCRON_HOST=0.0.0.0`): obrigatorio `SERVERCRON_API_TOKEN`
  **ou** pelo menos 1 email ativo na aba `USERS` (login por codigo no email).
- Copie `.env.example` para `.env` e preencha SMTP / token. **Nunca** commit o `.env`.

## Estrutura

| Ficheiro / pasta | Funcao |
|------------------|--------|
| `server.py` | Backend Flask + agendador + SQLite |
| `install_deps.bat` | Instala deps via pip |
| `static/` | Painel (HTML/CSS/JS + fontes locais) |
| `automacoes/` | Scripts agendados + `_servercron_log.py` |
| `registro_automacoes.example.xlsx` | Modelo da planilha |
| `.env.example` | Modelo de configuracao |
| `INSTRUCOES_AUTOMACAO_PYTHON.md` | Padrao para escrever automacoes |
| `AGENTS.md` / `CLAUDE.md` | Contrato para agents de codigo |
| `requirements.txt` | Dependencias Python |

## API (resumo)

| Metodo | Caminho | Descricao |
|--------|---------|-----------|
| GET | `/api/auth` | Diz se o painel exige auth (nao revela segredos) |
| GET | `/api/status` | Estado do servidor |
| GET | `/api/scripts` | Linhas da planilha |
| POST | `/api/reload` | Recarrega planilha e fila |
| GET | `/api/history` | Historico de execucoes |
| POST | `/api/run` | Disparo manual |
| POST | `/api/kill` | Para processo em curso |

Rotas `/api/*` protegidas conforme token/sessao OTP. Detalhes em `.env.example`.

## Variaveis de ambiente

Ver `.env.example`. Principais:

- `SERVERCRON_DATA_ROOT` - root de dados (default `~/Documents/ServerCRON`)
- `SERVERCRON_AUTOMAOES_DIR` - pasta das automacoes (opcional)
- `SERVERCRON_PORT` / `SERVERCRON_HOST`
- `SERVERCRON_API_TOKEN` - protege API (modo legado sem USERS)
- `SERVERCRON_SMTP_*` - envio do codigo de login por email
- `SERVERCRON_JOB_TIMEOUT_SEC` - timeout por job
- `SERVERCRON_TZ` - fuso dos crons (default `America/Sao_Paulo`)

Paths em env aceitam `~` (`Path.expanduser()`). Nunca hardcode `C:\Users\<nome>`.

## Codigos de saida (retcode)

| Exit code | Status   | Significado |
|-----------|----------|-------------|
| `0`       | success  | Processou com sucesso |
| `1`       | error    | Falha tecnica |
| `2`       | no_data  | Rodou bem, sem material |

Padrao completo: `INSTRUCOES_AUTOMACAO_PYTHON.md`.

## Logs por automacao

```text
<SERVERCRON_DATA_ROOT>/logs/<AREA>/<stem_lower>_<YYYYMMDD_HHMMSS>.log
```

Historico agregado: `<SERVERCRON_DATA_ROOT>/logs/historico_execucoes.csv`.

## O que nao sobe para o GitHub

- `.env` (tokens, SMTP, senhas)
- `registro_automacoes.xlsx` (emails reais da aba USERS)
- `*.sqlite`, `logs/`, `*.log`
- `__pycache__/`, `.venv/`
- testes locais `_test_*.py`

## Apoie

**PIX (chave aleatoria):** `f74458dc-2a36-49bd-9250-1cef4365ebb8`

Titular: Carlos Eduardo, Mogi das Cruzes.

## Contato

Autor: Carlos Eduardo ([@caducosilva](https://github.com/caducosilva))

- LinkedIn: https://www.linkedin.com/in/carlos-da-silva20ba5740a
- Instagram: https://www.instagram.com/caducosilva
- Email: abobicarlo@gmail.com

## Licenca

MIT. Veja [LICENSE](LICENSE).
