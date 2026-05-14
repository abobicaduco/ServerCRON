# ServerCRON

Portal **Flask** único: **Uploaders** (envio de ficheiros) + **Cron** (agendamento e execução de scripts Python), com **BigQuery** para permissões e cadastro de automações, e **SQLite** local para o agendador e histórico de execuções.

Repositório mínimo: `ServerCRON.py`, `ServerCRON.html`, `ServerCRON.css`, `ServerCRON.js`.

## Pré-requisitos (máquina empresa — Windows)

- **Python 3.10+** (recomendado 3.11).
- **Conta Google / ADC** com acesso ao projeto BigQuery (`gcloud auth application-default login` ou credencial corporativa equivalente), se usar permissões e `registro_automacoes` no BQ.
- **Outlook** (perfil Windows) se quiser login por código por e-mail, convite de arranque, ou monitorização de caixa.
- **Rede**: `pip install` precisa de acesso ao índice PyPI (ou mirror interno).

## Instalação rápida

```text
git clone https://github.com/abobicaduco/ServerCRON.git
cd ServerCRON
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite **`.env`** com o prefixo BigQuery real e o domínio de e-mail. O ficheiro deve ficar **na mesma pasta** que `ServerCRON.py`.

> O programa **não** usa `python-dotenv`. Carrega linhas `CHAVE=valor` de `.env` no arranque **sem** sobrescrever variáveis que já existam no Windows ou no terminal.

## Arranque

```text
python ServerCRON.py
```

Por defeito: **uma porta** (`SERVERCRON_DUO_PORTS=0`), Uploaders em `/` e Cron em `/cron/`. O bloco interno do Cron pode instalar dependências em falta via `pip` (bootstrap); mesmo assim recomenda-se `requirements.txt` antes do primeiro uso para evitar falhas de import no topo do ficheiro.

## BigQuery

- **`SERVERCRON_BQ_DATASET_PREFIX`**: `project.dataset` onde estão as tabelas. Alternativa: ficheiro de uma linha `servercron_bq_dataset_prefix.txt` ao lado de `ServerCRON.py`.
- **Permissões (Uploaders / login)**: tabela por defeito **`{prefixo}.ServerCRON`**. Se ainda usarem a tabela antiga **`server`**, definam `SERVERCRON_BQ_PERMISSIONS_TABLE=server` no `.env` até migrarem dados.
- **Cadastro de automações**: `{prefixo}.registro_automacoes` (nome fixo no código).

## Onde ficam os dados

- **Raiz de dados** (árvore `automacoes`, configs): por defeito `%USERPROFILE%\Documents\ServerCRON`. Override: `SERVERCRON_DATA_ROOT` (caminho absoluto).
- **SQLite do Cron** (`server_cron.sqlite`): por defeito na **pasta do `ServerCRON.py`** (ou pasta do `.exe` em build frozen).

Lista completa de variáveis: ver **`.env.example`** e a docstring no topo de **`ServerCRON.py`**.

## Vai “rodar direitinho” só com clone + `.env`?

Quase sempre **sim**, desde que:

1. Dependências estejam instaladas (`pip install -r requirements.txt`).
2. **`.env`** (ou variáveis de sistema) tenham **`SERVERCRON_BQ_DATASET_PREFIX`** correto (ou ficheiro `servercron_bq_dataset_prefix.txt`) e que o utilizador tenha **permissão BQ** de leitura (e admins de escrita na tabela de permissões).
3. **Outlook / pywin32** estejam alinhados ao ambiente corporativo se usarem fluxos de e-mail.
4. Portas **5001** (e **5002** em modo duas portas) não estejam bloqueadas por firewall local.

Não há garantia sem testar no teu PC da empresa (política de rede, proxy, versão Python, perfil Outlook). Usa o checklist acima e o primeiro arranque no terminal para ver erros explícitos (BigQuery, import, porta em uso).

## Licença

O ficheiro `LICENSE` foi removido na consolidação do repositório; se precisares de licença explícita para redistribuição interna, acrescenta-a de acordo com a política do banco.
