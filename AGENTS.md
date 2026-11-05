# Escopo e manutenção

- Trabalhar exclusivamente em `sousaweliton930-droid/ranking-do-detetive-novo`. Não acessar nem modificar o V63, seus serviços, bancos ou credenciais.
- Preservar o visual aprovado. Não inserir dados fictícios na aplicação; fixtures somente em bancos temporários dos testes.
- Ler `docs/PRODUCAO.md` antes de alterar publicação ou banco. `main` é a branch estável: alterações em branch de tarefa, testes e PR. Não integrar nem publicar automaticamente em tarefas futuras sem autorização explícita da sessão para essa versão.
- Rodar `python -m unittest discover -s tests -v`, `python -m compileall -q app.py production.py storage.py ops integrations tests` e `node --check static/app.js` no ambiente virtual.
- Produção usa disco persistente fora do checkout. Não excluir dados nem restaurar sobre arquivo existente. Não editar migrações aplicadas; acrescentar nova migração numerada. Backup antes de mudança de esquema.
- Render com disco é pago; configuração versionada não significa recurso autorizado ou publicado. Não contratar/ativar custos sem aprovação. Manter `checksPass` e os gates de aprovação. Não reutilizar serviços existentes.
- Não versionar segredos, bancos ou cópias de produção. Não solicitar credenciais Google até a tarefa de ativação da integração.
