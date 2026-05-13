<div align="center">

# ⚡ ServerCRON

### 🖥️ Flask · 📤 Uploaders · ⏱️ Cron · ☁️ BigQuery opcional · 🧾 Registo local (modo NO‑BQ)

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

<sub>✨ Painel único para disparar automações Python, ver logs e agendar jobs</sub>

</div>

---

## 📦 O que vem neste repositório

| Entrada | Pasta / ficheiros | BigQuery |
|--------|---------------------|----------|
| 🏢 **Produção / dados em nuvem** | `Server.py` + `Server.html`, `server.js`, `server.css` na **raiz** | ✅ Sim (configura `SERVERCRON_BQ_*`) |
| 🎒 **Portfólio / air‑gapped** | `Server_NO_BQ/Server_NO_BQ.py` + templates na mesma pasta | ❌ Não (xlsx local) |

> ☁️ **Pipelines (GCS → BQ, etc.):** usa prefixo `Server_NO_BQ/**` se só quiseres o pacote sem nuvem — vê [`docs/BIGQUERY.md`](docs/BIGQUERY.md).

---

<a id="pt-br"></a>

<details open>
<summary><strong>🇧🇷 Português (Brasil)</strong> — clica para expandir / recolher</summary>

## 🎯 Resumo

O **ServerCRON** é um painel **Flask** com **Uploaders** (upload + execução) e **Cron** (agendador + histórico), com sessão e e-mail token (Outlook COM no Windows, quando disponível).

## 🏃 Como correr

**Com BigQuery (raiz do clone):**

```bash
python Server.py
```

**Sem BigQuery (só pacote NO‑BQ):**

```bash
python Server_NO_BQ/Server_NO_BQ.py
```

Abre o URL indicado no terminal. Variáveis `SERVERCRON_*` documentadas no topo de cada `.py`.

## ⚙️ Variáveis `SERVERCRON_*` (resumo)

| Variável | Função |
|----------|--------|
| `SERVERCRON_PANEL_DIR` | Pasta com `Server.html` (opcional) |
| `SERVERCRON_DATA_ROOT` | Raiz de `automacoes/` e `config/modules/` (defeito: `~/Documents/ServerCRON`) |
| `SERVERCRON_DUO_PORTS` | `1` duas portas · `0` app unificada |
| `SERVERCRON_UP_PORT` / `SERVERCRON_CRON_PORT` | Portas em modo duo |
| `SERVERCRON_UNIFIED_PORT` | Porta unificada (links em e-mail) |
| `SERVERCRON_EMAIL_DOMAIN` | Sufixo de login (ex. `@example.com`) |
| `SERVERCRON_OUTLOOK_MONITOR_MAILBOX` | Mailbox Outlook (Windows) |
| `SERVERCRON_OPEN_BROWSER` | `0` não abre browser |
| `SERVERCRON_BQ_*` | Apenas em `Server.py` — prefixo BQ, tabela de permissões, TTL de cache |

## 💼 LinkedIn (PT‑BR)

> Lançámos o **ServerCRON**: portal **Flask** com **Uploaders + Cron**, opcionalmente com **BigQuery**, e variante **sem nuvem** em `Server_NO_BQ/`.  
> 🔗 https://github.com/abobicaduco/ServerCRON

</details>

---

<a id="en-us"></a>

<details>
<summary><strong>🇺🇸 English (US)</strong> — click to expand / collapse</summary>

## 🎯 Summary

**ServerCRON** is a **Flask** console with **Uploaders** (upload + run) and **Cron** (scheduler + history), with session + email OTP (Outlook COM on Windows when available).

## 🏃 How to run

**With BigQuery (repo root):**

```bash
python Server.py
```

**No BigQuery (NO‑BQ package only):**

```bash
python Server_NO_BQ/Server_NO_BQ.py
```

Open the printed URL. See `SERVERCRON_*` headers inside each entrypoint.

## ⚙️ `SERVERCRON_*` (cheat sheet)

| Variable | Role |
|----------|------|
| `SERVERCRON_PANEL_DIR` | Folder with `Server.html` (optional) |
| `SERVERCRON_DATA_ROOT` | Root for `automacoes/` + `config/modules/` (default `~/Documents/ServerCRON`) |
| `SERVERCRON_DUO_PORTS` | `1` two ports · `0` unified app |
| `SERVERCRON_UP_PORT` / `SERVERCRON_CRON_PORT` | Duo ports |
| `SERVERCRON_UNIFIED_PORT` | Unified port (email links) |
| `SERVERCRON_EMAIL_DOMAIN` | Login suffix (e.g. `@example.com`) |
| `SERVERCRON_OUTLOOK_MONITOR_MAILBOX` | Outlook store (Windows) |
| `SERVERCRON_OPEN_BROWSER` | `0` skip browser |
| `SERVERCRON_BQ_*` | `Server.py` only — BQ prefix, permissions table, cache TTL |

## 💼 LinkedIn (EN)

> **ServerCRON** — a **Flask** portal for **Uploaders + Cron**, optional **BigQuery**, plus an **offline** build under `Server_NO_BQ/`.  
> 🔗 https://github.com/abobicaduco/ServerCRON

</details>

---

## 📜 License

[MIT License](LICENSE)

## 🤝 Contributing

[GitHub Issues](https://github.com/abobicaduco/ServerCRON/issues)
