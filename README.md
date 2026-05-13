# ServerCRON

**[English](#english) · [Português (Brasil)](#português-brasil)**

Open-source **Flask** control plane for Python job automation: web dashboard, optional **BigQuery** integration, Outlook-style notifications, cron-style scheduling, and file upload flows. Designed for teams that run many small Python scripts and need a single place to trigger them, watch logs, and track outcomes.

**Repository:** [github.com/abobicaduco/ServerCRON](https://github.com/abobicaduco/ServerCRON)

---

## English

### Why it exists

Operations and data teams often juggle dozens of Python scripts—each with its own folder, virtual environment, and “who ran it last?” story. **ServerCRON** centralizes discovery, execution, and light observability behind one authenticated web UI so you spend less time on glue code and more on the automation itself.

### What you get

- **Unified portal** — Browse configured automations, run on demand, and inspect recent results.
- **Two deployment flavors** — Full stack with BigQuery hooks (`Server.py`) or a **no-BigQuery** variant (`Server_NO_BQ/Server_NO_BQ.py`) for air-gapped or local-only setups.
- **Security-minded defaults** — Session auth, CSRF patterns where applicable, and environment-driven secrets (never commit real keys).
- **Corporate-friendly paths** — Optional Windows home paths for shared drive layouts; override via environment variables for your org.

### Quick start (conceptual)

1. Clone this repository.
2. Create a Python 3.11+ virtual environment and install dependencies from your project’s `requirements` (if present) or follow inline/bootstrap notes in the server module you use.
3. Set required environment variables (panel directory, mail domain suffix, cron secret, etc.) as documented in the server source headers.
4. Run the chosen entrypoint (`Server.py` or `Server_NO_BQ/Server_NO_BQ.py`) and open the URL printed in the console.

For issues and improvements, use **[GitHub Issues](https://github.com/abobicaduco/ServerCRON/issues)**.

### LinkedIn blurb (EN)

> I open-sourced **ServerCRON** — a Flask-based portal to run, schedule, and monitor Python automations from one place (with optional BigQuery and a no-cloud variant). If your team lives in scripts and spreadsheets, this might save you a week of internal tooling. Repo: `github.com/abobicaduco/ServerCRON`

---

## Português (Brasil)

### Por que existe

Equipes de operações e dados costumam ter dezenas de scripts Python—cada um em sua pasta, venv e histórico de execução. O **ServerCRON** centraliza descoberta, disparo e um pouco de observabilidade num painel web autenticado, para você gastar menos tempo com “cola” e mais com a automação em si.

### O que você ganha

- **Portal unificado** — Lista automações configuradas, executa sob demanda e consulta resultados recentes.
- **Dois modos** — Stack completa com BigQuery (`Server.py`) ou variante **sem BigQuery** (`Server_NO_BQ/Server_NO_BQ.py`) para ambientes locais ou sem nuvem.
- **Defaults conscientes de segurança** — Sessão, CSRF onde aplicável, segredos por variável de ambiente (nunca commitar chaves reais).
- **Caminhos compatíveis com redes corporativas** — Segmentos de pasta sob `Path.home()` podem refletir diretórios compartilhados; ajuste via env para a sua organização.

### Início rápido (conceitual)

1. Clone o repositório.
2. Crie um ambiente virtual Python 3.11+ e instale as dependências do projeto.
3. Configure as variáveis de ambiente exigidas (diretório do painel, sufixo de e-mail, segredo do cron, etc.) conforme os comentários no módulo do servidor escolhido.
4. Execute `Server.py` ou `Server_NO_BQ/Server_NO_BQ.py` e abra a URL indicada no terminal.

Dúvidas e melhorias: **[GitHub Issues](https://github.com/abobicaduco/ServerCRON/issues)**.

### Texto para LinkedIn (PT-BR)

> Publiquei o **ServerCRON** em open source: um portal em **Flask** para rodar, agendar e acompanhar automações Python num lugar só (com BigQuery opcional e variante sem nuvem). Ideal para times que vivem de scripts e planilhas. Repositório: `github.com/abobicaduco/ServerCRON`

---

## License

Specify your license in a `LICENSE` file (e.g. MIT) when you publish—this README does not impose one.

## Contributing

Pull requests and issues are welcome on [GitHub](https://github.com/abobicaduco/ServerCRON).
