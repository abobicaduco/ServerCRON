<div align="center">

# ⚡ ServerCRON

### 🖥️ Flask · 📤 Uploaders · ⏱️ Cron · 🧾 Registo local (sem BigQuery neste repo)

<br/>

**Escolhe o idioma / Pick your language**

<p>
  <a href="#pt-br"><img src="https://img.shields.io/badge/🇧🇷_PT--BR-clique_aqui-239a3b?style=for-the-badge" alt="Português (Brasil)"/></a>
  &nbsp;
  <a href="#en-us"><img src="https://img.shields.io/badge/🇺🇸_EN--US-click_here-2563eb?style=for-the-badge" alt="English (US)"/></a>
</p>

<br/>

[![Repository](https://img.shields.io/badge/GitHub-abobicaduco%2FServerCRON-181717?style=for-the-badge&logo=github)](https://github.com/abobicaduco/ServerCRON)
[![MIT License](https://img.shields.io/badge/license-MIT-fbbf24?style=for-the-badge)](LICENSE)
[![Issues](https://img.shields.io/badge/💬_Issues-GitHub-8b5cf6?style=for-the-badge)](https://github.com/abobicaduco/ServerCRON/issues)

<br/>

<sub>✨ Portfólio / open source · 🚀 Um painel para disparar e acompanhar automações Python</sub>

</div>

---

<a id="pt-br"></a>

<details open>
<summary><strong>🇧🇷 Português (Brasil)</strong> — clica no título para recolher / expandir</summary>

## 🎯 O que é

O **ServerCRON** (pacote `Server_NO_BQ/`) é um painel web em **Flask** com:

- 🔐 **Login** com token por e-mail (Outlook COM no Windows, se disponível)
- 📤 **Uploaders** — escolher pasta de automação, enviar ficheiros, correr scripts
- ⏱️ **Cron** — agendador embutido, histórico de execuções, fluxo unificado com Uploaders
- 🧾 **Registo** em `registro_automacoes.xlsx` (sem BigQuery neste repositório)

## 🏃 Início rápido

1. 📥 `git clone https://github.com/abobicaduco/ServerCRON.git`
2. 🐍 Python **3.11+** e dependências (Flask, openpyxl, apscheduler, etc. — vê imports em `Server_NO_BQ/Server_NO_BQ.py`)
3. ⚙️ Variáveis `SERVERCRON_*` se precisares (painel, portas, raiz de dados — vê tabela abaixo)
4. ▶️ Na raiz do clone:  
   `python Server_NO_BQ/Server_NO_BQ.py`  
   Abre o URL que aparecer no terminal.

## 📂 O que está neste repo

| Caminho | Descrição |
|--------|-------------|
| `Server_NO_BQ/Server_NO_BQ.py` | 🧠 Servidor Flask (entrada principal) |
| `Server_NO_BQ/Server.html` | 🎨 Template do painel |
| `Server_NO_BQ/server.css` · `server.js` | 🎨 Estáticos |
| `LICENSE` | 📜 MIT |
| `docs/BIGQUERY.md` | ☁️ Nota sobre âmbito (só `Server_NO_BQ/` em pipelines) |

> 💡 **BigQuery:** este clone público traz **só** o pacote `Server_NO_BQ/`. Se alguma rotina tua carregou “a pasta inteira” para o BQ, filtra o prefixo para `Server_NO_BQ/` — vê `docs/BIGQUERY.md`.

## ⚙️ Variáveis de ambiente (`SERVERCRON_*`)

| Variável | Função |
|----------|--------|
| `SERVERCRON_PANEL_DIR` | Pasta com `Server.html` (opcional) |
| `SERVERCRON_DATA_ROOT` | Raiz de `automacoes/` e `config/modules/` (defeito: `~/Documents/ServerCRON`) |
| `SERVERCRON_DUO_PORTS` | `1` = duas portas; `0` = app unificada |
| `SERVERCRON_UP_PORT` / `SERVERCRON_CRON_PORT` | Portas em modo duo |
| `SERVERCRON_UNIFIED_PORT` | Porta em modo unificado (links em e-mails) |
| `SERVERCRON_EMAIL_DOMAIN` | Sufixo de e-mail de login (ex. `@example.com`) |
| `SERVERCRON_OUTLOOK_MONITOR_MAILBOX` | Nome da mailbox Outlook (Windows) |
| `SERVERCRON_OPEN_BROWSER` | `0` para não abrir browser ao arrancar |

Nomes antigos `C6_*` **já não são lidos**.

## 💼 Texto para LinkedIn (PT-BR)

> Publiquei o **ServerCRON** em open source: um portal **Flask** para rodar, agendar e acompanhar automações Python num só sítio, com **Uploaders + Cron** e registo local.  
> 🔗 `https://github.com/abobicaduco/ServerCRON`

</details>

---

<a id="en-us"></a>

<details>
<summary><strong>🇺🇸 English (US)</strong> — click the title to expand / collapse</summary>

## 🎯 What it is

**ServerCRON** (the `Server_NO_BQ/` package) is a **Flask** web console featuring:

- 🔐 **Email token login** (Outlook COM on Windows when available)
- 📤 **Uploaders** — pick an automation folder, upload files, run scripts
- ⏱️ **Cron** — built-in scheduler, run history, unified flow with Uploaders
- 🧾 **Workbook registry** via `registro_automacoes.xlsx` (no BigQuery in this repo)

## 🏃 Quick start

1. 📥 `git clone https://github.com/abobicaduco/ServerCRON.git`
2. 🐍 Python **3.11+** and dependencies (Flask, openpyxl, APScheduler, etc. — see imports in `Server_NO_BQ/Server_NO_BQ.py`)
3. ⚙️ Set `SERVERCRON_*` env vars if needed (see table below)
4. ▶️ From repo root:  
   `python Server_NO_BQ/Server_NO_BQ.py`  
   Open the URL printed in the terminal.

## 📂 Repository layout

| Path | Description |
|------|-------------|
| `Server_NO_BQ/Server_NO_BQ.py` | 🧠 Flask app entrypoint |
| `Server_NO_BQ/Server.html` | 🎨 Panel template |
| `Server_NO_BQ/server.css` · `server.js` | 🎨 Static assets |
| `LICENSE` | 📜 MIT |
| `docs/BIGQUERY.md` | ☁️ Scope note for BQ / mirrors (`Server_NO_BQ/` only) |

> 💡 **BigQuery:** this public repo ships **only** `Server_NO_BQ/`. If a pipeline ingested the whole clone by mistake, scope your object prefix to `Server_NO_BQ/` — see `docs/BIGQUERY.md`.

## ⚙️ Environment variables (`SERVERCRON_*`)

| Variable | Role |
|----------|------|
| `SERVERCRON_PANEL_DIR` | Folder with `Server.html` (optional) |
| `SERVERCRON_DATA_ROOT` | Root for `automacoes/` and `config/modules/` (default `~/Documents/ServerCRON`) |
| `SERVERCRON_DUO_PORTS` | `1` = two ports; `0` = unified app |
| `SERVERCRON_UP_PORT` / `SERVERCRON_CRON_PORT` | Ports in duo mode |
| `SERVERCRON_UNIFIED_PORT` | Unified mode port (email links) |
| `SERVERCRON_EMAIL_DOMAIN` | Login email suffix (e.g. `@example.com`) |
| `SERVERCRON_OUTLOOK_MONITOR_MAILBOX` | Outlook store display name (Windows) |
| `SERVERCRON_OPEN_BROWSER` | `0` to skip opening a browser on startup |

Legacy `C6_*` names are **not** read anymore.

## 💼 LinkedIn blurb (EN)

> I open-sourced **ServerCRON** — a **Flask** portal to run, schedule, and track Python automations in one place, with **Uploaders + Cron** and a local workbook registry.  
> 🔗 `https://github.com/abobicaduco/ServerCRON`

</details>

---

## 📜 License

Released under the [MIT License](LICENSE).

## 🤝 Contributing

Issues and PRs: [GitHub Issues](https://github.com/abobicaduco/ServerCRON/issues).
