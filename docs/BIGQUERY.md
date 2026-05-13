# BigQuery & repo layout

Este repositório tem **dois modos** de servidor:

| Caminho | Uso |
|---------|-----|
| `Server.py` + `Server.html` / `server.js` / `server.css` na raiz | Stack **com BigQuery** (permissões, registo em BQ, etc.). |
| `Server_NO_BQ/` | Variante **sem BigQuery** (registo local em `registro_automacoes.xlsx`). |

## Ingestão / pipelines

- Se carregas o repositório (ou um zip) para **Cloud Storage → BigQuery** ou ferramentas semelhantes, define o prefixo para **só o que precisas**, por exemplo:
  - só o pacote no‑BQ: `Server_NO_BQ/**`
  - ou ficheiros Python concretos: `Server_NO_BQ/**/*.py`
- Evita indexar `node_modules`, `.git` ou cópias duplicadas desnecessárias — isso costuma ser o que “incha” a carga, não o Git em si.

## Onde está o código sensível a GCP

- Prefixo de dataset e tabela de permissões: variáveis `SERVERCRON_BQ_*` e ficheiro opcional `servercron_bq_dataset_prefix.txt` junto a `Server.py` (ver docstring no ficheiro).
