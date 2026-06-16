# ServerCRON

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-portal-000000?logo=flask)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-agendador-003B57?logo=sqlite)](https://sqlite.org/)

> Portal Flask de arquivo único: **upload de arquivos** + **agendador de scripts Python** estilo cron. Permissões via planilha Excel (`USERS`/`AUTOMACOES`), histórico de execuções em SQLite. Roda em máquinas Windows corporativas sem acesso admin.

---

## Funcionalidades

- **Upload de arquivos** com controle de acesso por usuário
- **Agendador cron** — cadastre scripts Python e agende execuções
- **Permissões via Excel** — planilha `registro_automacoes.xlsx` com abas `USERS` e `AUTOMACOES`
- **Histórico SQLite** — log de todas as execuções com status e saída
- **Login por e-mail** — código enviado via Outlook (sem senha, sem LDAP)
- **Sem admin** — funciona em máquinas corporativas com Python apenas

---

## Pré-requisitos

- Python 3.10+
- Planilha `registro_automacoes.xlsx` configurada
- Outlook (perfil Windows) para login por e-mail

---

## Instalação

```bash
git clone https://github.com/abobicaduco/ServerCRON.git
cd ServerCRON
pip install -r requirements.txt
python ServerCRON.py
```

---

## Arquivos

| Arquivo | Função |
|---|---|
| `ServerCRON.py` | Backend Flask + agendador |
| `ServerCRON.html` | Interface web single-page |
| `ServerCRON.css` | Estilos |
| `ServerCRON.js` | Lógica frontend |

---

## Outros Apps

| App | Descrição |
|---|---|
| [AboBI Player](https://github.com/abobicaduco/abobiplayer) | Player de vídeo local para Android |
| [AboBI Caduco](https://github.com/abobicaduco/abobi-caduco) | Baixador de vídeos e áudio para Android |
| [AboBI Ferramentas](https://abobiferramentas.com) | 90+ ferramentas online gratuitas |

---

## Apoiar

**Chave Pix (aleatória):** `f74458dc-2a36-49bd-9250-1cef4365ebb8`

Site: [abobiferramentas.com](https://abobiferramentas.com)

---

**Desenvolvido por** [Carlos Eduardo (@abobicaduco)](https://github.com/abobicaduco) · Licença MIT
