# Publicação e manutenção

## Estado desta preparação

O projeto foi preparado para um **serviço novo no Render**, com runtime Python e disco persistente próprio. Nada depende do V63. O arquivo `render.yaml` é uma configuração a aplicar, não prova de serviço criado. Não ativar antes da autorização de custo e da conexão legítima do Render/GitHub. Não utilizar URL pública de clone como substituta da conexão GitHub: ela não oferece auto deploy.

Estimativa inicial: Starter US$ 7/mês + 1 GiB de disco US$ 0,25/mês = US$ 7,25/mês, sem impostos/excedentes. Confirmar o preço no painel antes de criar. Nenhum recurso pago foi contratado nesta preparação. Referências: [planos](https://render.com/pricing), [discos persistentes](https://render.com/docs/disks), [limitações gratuitas](https://render.com/docs/free).

A hospedagem gratuita do Render perde SQLite em reinícios e não permite disco. PythonAnywhere gratuito oferece disco persistente, mas exige renovação mensal e novas contas não incluem agendamentos; sua automação também exige um fluxo específico de API/console. Para manter esta aplicação e atualizações simples sem migração de banco, a escolha é Render com um disco. Não é alegado que inexista alternativa gratuita.

## Primeira publicação (depois da autorização)

1. Conectar uma conta Render autorizada e sua integração GitHub **somente** ao repositório `sousaweliton930-droid/ranking-do-detetive-novo`. Criar um novo Blueprint a partir de `main` usando `render.yaml`. Nunca selecionar serviço ou disco existente. Manter uma instância; discos não são compartilhados entre serviços.
2. Revisar os custos antes de confirmar. `SECRET_KEY` é gerada pelo Render e guardada no ambiente do serviço; nunca copiar seu valor para o GitHub, chat ou logs. O banco usa `/var/data/ranking.sqlite`; backups ficam em `/var/data/backups`. Esse disco permanece entre releases/reinícios. O build não abre o banco; a migração só roda na inicialização, quando o disco está montado. A aplicação recusa iniciar produção sem o mount, chave externa forte ou cookies Secure.
3. A aplicação usa automaticamente `RENDER_EXTERNAL_HOSTNAME`, fornecido pelo Render, para fixar os hosts autorizados e a origem HTTPS real. Não é preciso adivinhar nem cadastrar uma URL inicial. Para domínio personalizado futuro, configurar `ALLOWED_HOSTS` e `PUBLIC_ORIGIN` no ambiente e manter também o hostname exigido pelos health checks. Render oferece HTTPS na borda; Waitress aceita o protocolo encaminhado exclusivamente dentro dessa rede. Não expor essa configuração de proxy a clientes diretos em uma VPS.
4. No Shell do **novo** serviço, criar a conta com `flask --app app:create_app create-admin seu_usuario` e digitar a senha no prompt. Não inserir senhas em comandos, YAML ou logs. Até a criação, o painel permanece inacessível. O comando não cria senha padrão nem cadastro aberto.
5. Conferir `/healthz` via HTTPS, página inicial no navegador e redirecionamento de `/admin` para login. Conferir cookies Secure/HttpOnly, HSTS, logs e um backup. Realizar uma gravação administrativa autorizada e verificar sua persistência após um deploy; não inserir dados fictícios na produção. Não declarar essa persistência externa validada somente porque testes locais passaram.
6. Ativar/revisar a proteção de `main` no GitHub: exigir PR, status **Testes essenciais** e **Integração aprovada em main**, impedir force push e exclusão. Não habilitar auto merge. Para equipe com revisor distinto, exigir aprovação de revisão e descarte de aprovações antigas. Em repositório com um único proprietário, a aprovação é o próprio ato humano de integrar o PR, após conferir os testes; ele não pode aprovar formalmente o próprio PR. Essas regras de proteção precisam ser verificadas no GitHub; CODEOWNERS por si só não as ativa.

## Atualizações futuras — procedimento curto

1. Codex cria branch de tarefa, modifica o código e executa `python -m unittest discover -s tests -v`, compilação e `node --check static/app.js`.
2. Codex envia a branch e abre PR para `main`, com resumo e resultado dos testes. **Não integrar automaticamente em tarefas futuras sem aprovação explícita do usuário.**
3. O responsável aprova a versão integrando o PR. O workflow de `main` verifica os testes e a associação a um PR integrado; push direto falha no gate de publicação. A primeira integração desta preparação também aguarda autorização explícita do usuário para o PR #1.
4. Render publica somente `main`, com **After CI Checks Pass** (`autoDeployTrigger: checksPass`). Alterações em outras branches não vão para produção. Não desligar os gates nem configurar **On Commit**. A conexão real GitHub/Render é indispensável.
5. Conferir o SHA em `/healthz`, logs e o site. O banco está fora do checkout, no disco. Com SQLite em disco, a troca de versão pode ter breve indisponibilidade; Render não promete zero downtime nessa configuração.

A automação só estará comprovada quando um merge aprovado for publicado com sucesso no serviço real. YAML e workflow preparados não equivalem a deploy funcionando.

## Migrações, backups e recuperação

- `migrations/` contém SQL versionado, executado em transação, com checksum registrado em `schema_migrations`. Não editar migrações já aplicadas; adicionar um novo arquivo numerado. O esquema inicial reconhece o banco anterior sem apagar seus registros.
- Antes de aplicar novas migrações sobre um banco existente, o processo salva uma cópia consistente com a API SQLite Backup. Se a cópia ou a migração falhar, o servidor não inicia com esquema parcial. Código anterior ao esquema também é recusado: rollback precisa ser compatível, não apenas trocar o commit.
- `python ops/start.py` cria um backup no início e a cada 24h, verificando integridade; `flask --app app:create_app backup` permite uma cópia manual. Só uma instância deve executar o serviço.
- As cópias permanecem no disco persistente, com acesso 0600. Monitorar espaço pelo painel/logs e exportar cópias regularmente por SSH/SFTP do serviço autorizado para armazenamento seguro separado. Cópias no mesmo disco permitem recuperação de erro de aplicação; não substituem backup externo para perda/exclusão do volume. A exportação externa não foi configurada sem uma conta de hospedagem.
- Não apagar registros para liberar espaço. Arquivar cópias antigas externamente; o sistema não exclui automaticamente backups ou o banco.
- Para restaurar, parar as escritas e usar `python ops/restore.py /var/data/backups/arquivo.sqlite /var/data/restaurado.sqlite`. O comando verifica integridade e **recusa sobrescrever qualquer destino existente**. Atualizar `DATABASE` para o novo arquivo no ambiente do serviço e reiniciar; preservar o banco anterior. Executar novamente `python -m unittest ...` nunca deve usar esse caminho: testes usam `TemporaryDirectory`.

## Segurança, logs e Google

Produção exige SECRET_KEY externa ≥32 caracteres, mount persistente, host autorizado, cookies Secure e origem HTTPS fixa. HTTP redireciona para a origem definida e envia HSTS. Login/CSRF/autorização continuam obrigatórios para alterações; limitação de tentativas está agora no SQLite e sobrevive a reinícios. O acesso administrativo revê a existência da conta a cada requisição. Não há segredo fixo nem senha de bootstrap.

Render reúne logs de execução e erros; o painel da aplicação contém os registros de sincronização. `/healthz` confirma acesso ao banco e informa o SHA da release, sem revelar credenciais ou conteúdo das tabelas. Evitar registrar valores de formulário ou arquivos secretos.

Google Sheets permanece implementado e desligado, sem credencial solicitada. Não criar cron externo separado com outro SQLite: um cron Render não compartilha o disco deste web service. A futura ativação deve executar o comando de sincronização no mesmo host/disco ou adaptar o agendamento de forma autorizada. Esta tarefa não ativa coleta Telegram nem altera o visual.

## Validação desta entrega

Os testes locais exercitam migrações reais, persistência entre instâncias do app, backup/restauro, transação de migração inválida, HTTPS/cookies/hosts e bloqueio de login após reinício. A detecção de mount do provedor é substituída apenas nos testes. Também foi executado o processo Waitress de produção em banco temporário, com o proxy HTTPS do provedor simulado, e a renderização foi verificada em Chromium em 390 px e 1440 px. Isso não verifica a conta Render, seu volume real ou certificado público; esses itens permanecem pendentes da ativação autorizada.
