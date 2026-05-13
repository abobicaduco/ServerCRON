# BigQuery / mirror scope (portfolio)

Este repositório contém **apenas** o pacote open source em `Server_NO_BQ/` (Flask + painel + registo local em xlsx).

- **Não** há pipeline neste repo que envie código para o BigQuery.
- Se usaste **Cloud Storage → BigQuery** (ou outra ferramenta) e carregaste a **raiz inteira** do clone por engano, restringe o prefixo do objeto para:

  `Server_NO_BQ/`

  Exemplo de wildcard GCS (ajusta bucket e caminho):

  `gs://SEU_BUCKET/caminho/Server_NO_BQ/**`

- Para **permissions / tabelas** que antes apontavam para o monólito `Server.py`, usa apenas artefactos gerados a partir deste pacote ou mantém uma cópia privada do stack completo fora deste repo.
