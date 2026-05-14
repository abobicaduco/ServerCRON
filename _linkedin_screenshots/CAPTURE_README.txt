LinkedIn / portfolio — imagens geradas localmente
================================================

Ficheiros PNG (previews estáticos, não exigem o Flask a correr):
  - linkedin-01-uploaders-login-preview.png
  - linkedin-02-cron-panel-preview.png

Para voltar a gerar (Tailwind CDN + Playwright headless):
  cd _linkedin_screenshots
  python capture_preview_pngs.py

Scripts Python de demo (sem lógica de negócio) para pastas de automação:
  Ver pasta ../_linkedin_demo/automacoes/linkedin_demo/

Planilha de exemplo:
  ../_linkedin_demo/registro_automacoes.xlsx

Arranque rápido do servidor real (quando o Python tiver todas as deps):
  set SERVERCRON_SKIP_REQUIREMENTS_PIP=1
  set SERVERCRON_DATA_ROOT=caminho\\para\\_linkedin_demo
  set SERVERCRON_REGISTRO_XLSX=caminho\\para\\_linkedin_demo\\registro_automacoes.xlsx
  python ServerCRON.py

Substitua estes PNGs por capturas reais do painel quando o ServerCRON estiver a correr na empresa.
