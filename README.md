# ServerCRON

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-portal-000000?logo=flask)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-scheduler-003B57?logo=sqlite)](https://sqlite.org/)

> **EN:** Single-file Flask portal combining file uploads and a cron-style Python script scheduler — Excel-based RBAC (`USERS`/`AUTOMACOES` sheets), SQLite run history, built for corporate Windows machines without admin rights.

Portal **Flask** único: **Uploaders** (envio de ficheiros) + **Cron** (agendamento e execução de scripts Python), com permissões e cadastro de automações na planilha **`registro_automacoes.xlsx`** (folhas **`USERS`** e **`AUTOMACOES`**), e **SQLite** local para o agendador e histórico de execuções.



Repositório mínimo: `ServerCRON.py`, `ServerCRON.html`, `ServerCRON.css`, `ServerCRON.js`.



## Pré-requisitos (máquina empresa — Windows)



- **Python 3.10+** (recomendado 3.11).

- **Ficheiro Excel** `registro_automacoes.xlsx` com as folhas esperadas, no caminho configurado (ver abaixo) ou ao lado de `ServerCRON.py` por defeito.

- **Outlook** (perfil Windows) se quiser login por código por e-mail, convite de arranque, ou monitorização de caixa.

- **Rede**: `pip install` precisa de acesso ao índice PyPI (ou mirror interno).



## Instalação rápida



```text

git clone https://github.com/abobicaduco/ServerCRON.git

cd ServerCRON

python -m venv .venv

.\.venv\Scripts\activate

copy .env.example .env

```



Ao correr **`python ServerCRON.py`**, se existir **`requirements.txt`** na pasta do projecto, o próprio script executa **`pip install -r requirements.txt`** no início (sempre que inicias o `.py`). O passo `pip install -r requirements.txt` manual acima é opcional, mas útil para validar o venv antes da primeira vez.



Edite **`.env`** (copiado de `.env.example`) com o caminho da planilha (se não usar o default) e o domínio de e-mail. O ficheiro deve ficar **na mesma pasta** que `ServerCRON.py`.



> O programa **não** usa `python-dotenv`. Carrega linhas `CHAVE=valor` de `.env` no arranque **sem** sobrescrever variáveis que já existam no Windows ou no terminal.



## Arranque



```text

python ServerCRON.py

```



Equivalente: ``python server.py`` (ficheiro fino que executa ``ServerCRON.py``).



Por defeito: **uma porta** (`SERVERCRON_DUO_PORTS=0`), Uploaders em `/` e Cron em `/cron/`. O bloco interno do Cron mantém um bootstrap `pip` para pacotes do agendador; o **`requirements.txt`** na raiz é instalado **no início** de cada `python ServerCRON.py` quando o ficheiro existe.



## Planilha `registro_automacoes.xlsx`



- **`SERVERCRON_REGISTRO_XLSX`**: caminho absoluto ao ficheiro `.xlsx`.

- **`SERVERCRON_REGISTRO_DIR`**: pasta onde está `registro_automacoes.xlsx` (nome fixo).

- Se nenhum dos dois estiver definido: **`registro_automacoes.xlsx`** na mesma pasta que `ServerCRON.py`.



Folhas usadas pelo servidor:



- **`USERS`**: colunas de permissões / login (incl. administradores na coluna de nível de acesso).

- **`AUTOMACOES`**: catálogo de jobs Cron (expressões CRON, áreas, etc., conforme o código espera).



Cache / recarregamento da folha USERS ainda aceita os envs legados `SERVERCRON_BQ_PERMS_FRESH_TTL_SEC` e `SERVERCRON_BQ_PERMS_STALE_MAX_SEC` (apenas nomes históricos; não há BigQuery).



## Onde ficam os dados



- **Raiz de dados** (árvore `automacoes`, configs): por defeito `%USERPROFILE%\Documents\ServerCRON`. Override: `SERVERCRON_DATA_ROOT` (caminho absoluto).

- **SQLite do Cron** (`server_cron.sqlite`): por defeito na **pasta do `ServerCRON.py`** (ou pasta do `.exe` em build frozen).



Lista completa de variáveis: ver **`.env.example`** e a docstring no topo de **`ServerCRON.py`**.



## Vai “rodar direitinho” só com clone + `.env`?



Quase sempre **sim**, desde que:



1. Dependências: ao correr **`python ServerCRON.py`**, o script corre **`pip install -r requirements.txt`** se o ficheiro existir (podes fazer o mesmo comando manualmente antes, para falhar cedo no venv).

2. A planilha **`registro_automacoes.xlsx`** exista no caminho esperado e tenha as folhas **`USERS`** e **`AUTOMACOES`** com o formato que o painel e o agendador assumem.

3. **Outlook / pywin32** estejam alinhados ao ambiente corporativo se usarem fluxos de e-mail.

4. Portas **5001** (e **5002** em modo duas portas) não estejam bloqueadas por firewall local.



Não há garantia sem testar no teu PC da empresa (política de rede, proxy, versão Python, perfil Outlook). Usa o checklist acima e o primeiro arranque no terminal para ver erros explícitos (planilha em falta, import, porta em uso).


---

## Autor / Author

**Carlos Eduardo (abobicaduco)** · [GitHub](https://github.com/abobicaduco) · [LinkedIn](https://www.linkedin.com/in/carlos-eduardo-20ba5740a/)

Licença: [MIT](LICENSE)
