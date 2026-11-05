# Escopo e manutenção

- Trabalhar exclusivamente em `sousaweliton930-droid/ranking-do-detetive-novo`. Não acessar nem modificar o V63, seus serviços, bancos ou credenciais.
- Preservar o visual aprovado. Não inserir dados fictícios na aplicação; fixtures somente em bancos temporários dos testes.
- Ler `docs/PRODUCAO.md` antes de alterar publicação ou banco. `main` é a branch estável: alterações em branch de tarefa, testes e PR. Não integrar nem publicar automaticamente em tarefas futuras sem autorização explícita da sessão para essa versão.
- Rodar `python -m unittest discover -s tests -v`, `python -m compileall -q app.py production.py storage.py postgres_storage.py ops integrations tests` e `node --check static/app.js` no ambiente virtual.
- Produção na hospedagem gratuita usa o Neon PostgreSQL existente via DATABASE_URL com TLS. SQLite continua disponível localmente; SQLite em produção exige disco persistente fora do checkout. Não excluir dados nem restaurar sobre arquivo existente. Não editar migrações aplicadas; acrescentar nova migração numerada. Backup antes de mudança de esquema.
- Orçamento R$ 0 e nenhum cartão: Render foi descartado pelo usuário. EthioDeploy é o alvo atual e deve permanecer Free, com o Neon Free existente. Não adicionar outro banco. Interromper diante de assinatura, cobrança ou verificação de cartão com risco de cobrança. Configuração versionada não significa publicação. Não integrar/publicar código sem validação e autorização; preservar os gates de aprovação do GitHub. Não reutilizar recursos do V63; manter o projeto EthioDeploy e o Neon já existentes do novo ranking.
- Não versionar segredos, bancos ou cópias de produção. Não solicitar credenciais Google até a tarefa de ativação da integração.

- O backend é Python/Flask, sem Node/NPM. Não recriar package.json na raiz para uma prévia: isso altera a detecção da hospedagem. Usar `.venv/bin/python app.py` localmente e `python ops/start.py` em produção; Nixpacks está fixado em Python.
