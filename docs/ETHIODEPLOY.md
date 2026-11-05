# Publicação sem cartão: EthioDeploy Free + Neon existente

EthioDeploy confirma suporte Python/Flask, HTTPS e plano Free sem cartão. São 256 MB/0,5 CPU e um projeto, com suspensão após 30 minutos sem tráfego. Esgotar a cota gratuita suspende o serviço; não contratar Pro, domínio ou modo agente pago. Referências: https://ethiodeploy.com/deploy/flask e https://ethiodeploy.com/docs/billing.

## Correção da detecção

O `package.json` da raiz era apenas um atalho de prévia, mas levava o builder à detecção Node/NPM. Foi removido; o frontend é JavaScript/CSS servido pelo Flask, sem compilação npm. A prévia local continua disponível por `COOKIE_SECURE=0 .venv/bin/python app.py`.

- `.python-version`: Python 3.12.
- `nixpacks.toml`: provider **python**, instalação em venv com `requirements.lock` e inicialização em modo produção.
- `Procfile`: inicia o mesmo servidor Waitress já implementado, com `APP_ENV=production` e cookies seguros.
- O processo usa `0.0.0.0:$PORT`. Não usar `flask run` em produção nem procurar um export `app:app`; esta aplicação usa a factory `create_app` e seu servidor existente.

A detecção foi verificada com Nixpacks 1.41.0: runtime Python 3.12, instalação por pip e nenhum comando npm. Configurações manuais antigas do painel têm prioridade sobre o arquivo; remover overrides Node/NPM no projeto existente.

## Projeto e banco existentes

Usar exclusivamente o projeto GitHub `sousaweliton930-droid/ranking-do-detetive-novo`, branch `main`. Não criar outro projeto de hospedagem se ele já existir. Não adicionar addon de banco na EthioDeploy.

Neon já provisionado, plano Free:

- Projeto `ranking-do-detetive-novo`, ID `rough-cherry-89253426`.
- Branch `production`, ID `br-green-cherry-bbb73waz`.
- Banco `ranking_novo`, papel `ranking_app`.
- Migrações versionadas 001 e 002 já aplicadas; conteúdo inicialmente vazio. Não executar comandos de limpeza, reset ou recriação.

Esses identificadores não são credenciais. A URL com senha deve ir somente às variáveis criptografadas da hospedagem. Não colar a URL em chat, commit, logs ou build.

## Configuração indispensável no painel existente

1. Abrir o projeto **Ranking do Detetive → Settings → Build**. Usar branch `main`, raiz do repositório e limpar comandos antigos `npm install`/`npm start`. O repositório declara o builder Python. Caso o painel exija comandos, usar:
   - Install: `python -m pip install --no-cache-dir -r requirements.lock`.
   - Build: vazio (não há compilação frontend).
   - Start: `APP_ENV=production COOKIE_SECURE=1 python ops/start.py`.
2. Em **Settings → Environment variables**, preservar os valores corretos já existentes e preencher somente os ausentes:
   - `DATABASE_URL`: conexão do Neon existente, com TLS (`sslmode=require` ou superior); marcar **Sensitive** e **Runtime only**.
   - `SECRET_KEY`: chave aleatória estável de pelo menos 32 caracteres, gerada com segurança; **Sensitive** e **Runtime only**. Não trocar uma chave válida a cada deploy. Para gerar uma localmente: `python -c "import secrets; print(secrets.token_hex(32))"` e transferir diretamente ao campo secreto do painel, sem publicar o valor.
   - `PUBLIC_ORIGIN`: URL HTTPS REAL mostrada pelo projeto, sem barra final. Ex.: formato `https://SEU-SLUG.ethiodeploy.app`, sem usar literalmente o exemplo. A aplicação deriva daí o host permitido; não é preciso adicionar `ALLOWED_HOSTS`, exceto para domínios extras autorizados. Se existir um override vazio/incorreto de `ALLOWED_HOSTS`, removê-lo ou corrigi-lo para o hostname real.
3. Conferir plano **Free**, nenhum cartão/cobrança/addon, salvar e clicar **Deploy/Redeploy**. O link público válido é o retornado pela hospedagem após o deploy ficar Ready, não um hostname adivinhado.

Essas variáveis são exigidas pelo guard de produção; ausência/erro faz o servidor recusar a inicialização. Essa recusa protege os dados e o painel administrativo. Não desabilitar HTTPS, autenticação ou o guard para fazer o deploy parecer saudável.

## Acesso do Codex e próxima manutenção

A integração EthioDeploy não está disponível neste chat. O CLI oficial foi verificado, mas não há sessão autenticada e a rede deste ambiente bloqueou a API EthioDeploy (CONNECT HTTP 403). Por isso não é possível afirmar que o painel foi configurado, que um deploy foi disparado ou que a URL está publicada. A sessão do usuário no navegador não é automaticamente uma credencial disponível ao agente.

Quando houver acesso autorizado à API/CLI, usar a autenticação por código descrita em https://ethiodeploy.com/docs/cli. Não pedir token em mensagem nem executar rotas de contorno para a rede bloqueada. Configuração local de CLI fica em `instance/` e não é versionada.

Atualizações: Codex → branch de tarefa → testes → PR aprovado → integração em `main`. EthioDeploy faz push-to-deploy; conferir no painel se existe espera por checks. Diferentemente do Blueprint Render, não foi comprovado um gate de CI do lado da EthioDeploy. Antes de integrar versões futuras, conferir os testes do PR e as regras de proteção de `main`; não tratar mera configuração YAML como proteção ativa. Não ativar redeploy de branches de trabalho.

## Validação obrigatória após o deploy real

- Abrir o endereço HTTPS e confirmar visualmente as quatro páginas, não só `/healthz`.
- `/admin` deve redirecionar para login; alterações exigem autenticação e CSRF. Sem administrador criado, o painel permanece fechado. A criação de conta pode ser feita pelo CLI local autorizado conectado ao mesmo Neon, com senha no prompt, sem senha padrão.
- Confirmar `DATABASE_URL` apontando ao Neon já existente. Não cadastrar registros fictícios em produção.
- Verificar migrações/contagens dos dados existentes, fazer uma segunda implantação e comparar. Não declarar persistência após redeploy externo com base apenas nos testes locais.
- Se o serviço dormir, a primeira visita pode aguardar o cold start. Não confundir isso com publicação concluída ou falha de banco.

Nenhuma mudança de esquema ou migração de dados é necessária para essa troca de hospedagem. O visual, as quatro páginas, a autenticação, a administração e o driver PostgreSQL foram preservados.
