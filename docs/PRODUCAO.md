> **Atualização de hospedagem:** Render foi descartado pelo usuário por exigir cartão. Não provisionar serviços Render. O alvo é EthioDeploy Free com o MESMO Neon existente; seguir [ETHIODEPLOY.md](ETHIODEPLOY.md). As seções de Render abaixo são histórico da preparação anterior, não instruções atuais de publicação. Os procedimentos de dados continuam válidos.

# Render Free + Neon Free — orçamento R$ 0

## Estado e limites

Este projeto é exclusivo de `sousaweliton930-droid/ranking-do-detetive-novo`. O Blueprint usa **Render Free, sem disco e sem banco Render**. Os dados ficam no PostgreSQL externo do **Neon Free**, independente do filesystem efêmero da aplicação. SQLite permanece implementado para uso local e reversão. Nada acessa o V63.

Configuração pronta não significa contas conectadas, deploy realizado ou persistência externa comprovada. Antes de criar recursos, conferir plano Free nos DOIS provedores e ausência de assinatura, auto upgrade ou cobrança. Se qualquer etapa exigir pagamento ou cartão com risco de cobrança, interromper. Não contratar add-ons, disco, cron ou banco pago. Não executar o Blueprint antigo Starter.

Condições consultadas: Render Free pode dormir após 15 minutos sem tráfego e tem cotas de execução/build/tráfego. Neon Free tem 1 GB por projeto, 100 CU-h/mês e cotas de transferência; atingir cotas pode suspender processamento ou escritas. Os dados não dependem de o Render estar acordado. Não há promessa de disponibilidade permanente gratuita. Referências: [Render Free](https://render.com/docs/free), [Neon Free](https://neon.com/docs/introduction/plans).

## Primeira publicação autorizada

1. Conectar contas legítimas Render e Neon. Criar **um projeto Neon novo** no plano Free, sem reutilizar bancos/credenciais. Escolher região próxima do serviço Render (Virginia). O subdomínio gratuito do Render dispensa compra de domínio.
2. Copiar a URL PostgreSQL fornecida pelo Neon diretamente para o segredo `DATABASE_URL` do NOVO serviço Render; nunca colocar em arquivo rastreado, PR, logs ou chat. Manter TLS (`sslmode=require` ou verificação superior). A aplicação não usa fallback para SQLite se uma URL PostgreSQL falhar.
3. Se houver registros reais no SQLite deste projeto, fazer a transferência controlada descrita abaixo ANTES de iniciar o serviço no Neon. Não inicializar o destino antes da cópia: o utilitário exige um banco novo. Se o projeto estiver vazio, as migrações criam somente tabelas vazias na primeira inicialização. Não criar registros fictícios para demonstrar a publicação.
4. Revisar o PR #1 contra a autorização atual: visual aprovado, quatro páginas, SQLite preservado, PostgreSQL adicional, Render `plan: free`, nenhum disco/serviço pago ou segredo. Integrar a versão revisada em `main` somente conforme a autorização da sessão. Manter as futuras tarefas em PR separado; não aprovar automaticamente versões futuras.
5. Criar um NOVO Blueprint Render pela integração GitHub, exclusivamente deste repositório e de `main`, usando `render.yaml`. Conferir preço R$ 0 antes de confirmar. Não usar URL pública de clone como substituta da conexão GitHub, pois isso não habilita publicação automática. Informar `DATABASE_URL` como segredo. `SECRET_KEY` é gerada no ambiente do Render; não inserir senha administrativa no YAML.
6. A origem HTTPS e o host permitido vêm automaticamente de `RENDER_EXTERNAL_HOSTNAME`. O servidor inicia com `python ops/start.py`, porta `PORT`, Waitress e protocolo HTTPS do proxy Render. Essa confiança no proxy é exclusiva da rede Render; não expor essa porta diretamente em outra infraestrutura.
7. Render Free não oferece Shell/SSH: criar o administrador pelo CLI local desta versão, com `DATABASE_URL` temporariamente configurada em ambiente seguro apontando ao NOVO Neon, executando `flask --app app:create_app create-admin seu_usuario`. Digitar a senha no prompt, nunca em argumentos de comando, chat ou GitHub. Não há senha padrão, cadastro público nem endpoint de bootstrap. Até criar uma conta, as alterações administrativas permanecem inacessíveis.
8. Validar URL HTTPS real, quatro páginas e bloqueio administrativo. Conferir `/healthz`, SHA publicado e logs. Uma implantação adicional deve manter a MESMA URL do Neon e os registros existentes. Só declarar persistência de produção comprovada após essa verificação real; os testes locais não provam acesso à conta Neon.

## Futuras atualizações pelo Codex

1. Alteração em branch de tarefa → testes SQLite/PostgreSQL → push → PR para `main`.
2. O responsável aprova explicitamente a versão e integra o PR. Preservar o visual, registros e configurações gratuitas.
3. Render acompanha apenas `main`, com **After CI Checks Pass** (`checksPass`). O workflow exige testes e associação do commit a PR integrado; push direto falha no gate. Alterações em branches de tarefa não são publicadas.
4. Conferir SHA em `/healthz`, logs e comportamento público. Banco externo permanece entre deploys. Não ativar auto upgrade de plano ou ignorar cotas.

O workflow inicia PostgreSQL efêmero no runner GitHub e executa os mesmos fluxos essenciais também nesse backend; nunca recebe credenciais Neon de produção. Configurar/verificar regras de proteção de `main` exigindo PR e os checks **Testes essenciais** e **Integração aprovada em main**, sem force push ou auto merge. CODEOWNERS não ativa regras sozinho. Se um único proprietário integrar seus próprios PRs, o ato de integrar representa sua aprovação; revisão formal exige outra pessoa. Não declarar regras de proteção ativas sem conferir o GitHub.

## SQLite e PostgreSQL, sem perda ou troca automática

- Sem `DATABASE_URL`, o modo local usa SQLite (`DATABASE` opcional). Produção SQLite continua exigindo volume montado, caminhos absolutos e backups persistentes. Essa opção não é utilizável no Render Free.
- Com `DATABASE_URL`, todas as tabelas (inclusive usuários, histórico/revisões, sincronizações e limites de login) estão no PostgreSQL. Os tipos de aplicação foram preservados; IDs e relações são mantidos.
- Migrações SQLite existentes permanecem imutáveis. PostgreSQL tem migrações próprias em `migrations/postgres/`, com checksum e lock transacional compatível com pooling. As migrações atuais são aditivas e transacionais. Falha reverte o lote, sem esquema parcial; versões anteriores ao esquema ou arquivos alterados são recusados.
- Não aplicar migrações destrutivas ou editar uma já aplicada. Futuras alterações devem ser aditivas, compatíveis com o código anterior e acompanhadas de cópia/snapshot antes da aplicação. Não executar DROP para reverter a mudança de backend.

### Transferência reversível

Parar as escritas administrativas/sincronizações durante a cópia e a troca. Configurar `SOURCE_DATABASE` e `TARGET_DATABASE` no ambiente seguro do CLI, sem valores em argumentos ou arquivos rastreados, e executar:

```sh
python ops/transfer_data.py
```

Origem pode ser SQLite ou PostgreSQL; destino deve ser banco PostgreSQL novo (schema sem tabelas) ou caminho SQLite inexistente. Não adivinhar caminhos nem URLs; usar somente dados autorizados deste projeto. O utilitário lê uma visão consistente da origem, copia IDs/relacionamentos/hashes de senha sem logá-los, confere contagem e SHA-256 por tabela e grava os dados do destino em transação. Erro reverte as inserções; não há merge/sobrescrita de registros. Sequências PostgreSQL são ajustadas para novos cadastros não colidirem com IDs importados.

O arquivo SQLite de origem permanece intocado. Para retornar após novas escritas no Neon, copiar o PostgreSQL atual para um NOVO arquivo SQLite pelo mesmo procedimento, conferir e então trocar a configuração; simplesmente voltar a um arquivo antigo perderia as escritas posteriores. Não descartar origem ou cópias. Destino de uma tentativa falha pode conter tabelas vazias; usar novo destino em nova tentativa, sem excluir dados existentes.

## Backup e recuperação

- A rotina de cópia diária SQLite é mantida somente para implantação SQLite com disco. Ela não roda no Render Free/PostgreSQL: uma cópia no disco efêmero do Render não seria backup persistente.
- Neon Free oferece recuperação limitada por histórico/snapshot conforme o plano; conferir a janela no painel (documentação consultada: 6 horas de histórico e 1 snapshot manual). Antes de qualquer futura migração com dados reais, criar um snapshot/cópia externa e testar recuperação. Não assumir retenção ilimitada.
- Para uma cópia externa, configurar `DATABASE_URL` de forma segura FORA do Render Free e executar `python ops/export_data.py /caminho/seguro/backup.jsonl.gz`. A exportação usa transação consistente, contém dados privados/hashes de senha, tem permissão 0600 e recusa sobrescrever arquivos. Guardá-la em armazenamento externo protegido já autorizado; não enviar para GitHub.
- Para recuperar: `python ops/export_data.py /caminho/novo.sqlite --restore-from /caminho/seguro/backup.jsonl.gz`. O destino deve inexistir. O arquivo compactado, marcador final, contagens, colunas e vínculos são verificados; erro reverte os registros. O SQLite recuperado pode ser transferido a um NOVO Neon com `ops/transfer_data.py`, sem apagar o banco anterior.
- Agendamento externo de backups não foi ativado sem conta/destino autorizado. Exportação manual e recuperação estão implementadas e testadas. Monitorar cota e retenção. Não anunciar uma política automática externa como já funcionando.

## Segurança e integrações

Produção exige segredo externo forte, cookies Secure/HttpOnly/SameSite, CSRF, origem HTTPS fixa e host permitido; PostgreSQL exige TLS e credenciais na URL secreta. Erro de conexão não imprime a URL e não muda para banco vazio. Login, autorização e limites persistem no PostgreSQL após reinícios.

Google Sheets foi preservado, sem conectar Google ou ativar coleta. O sincronizador usa locks transacionais no PostgreSQL, compatíveis com pooling Neon, em vez de depender de arquivo no disco temporário. A futura atualização de 15 minutos pode executar fora do web service com o mesmo Neon e credencial autorizada, mas não está agendada nesta entrega. Telegram e outras fontes permanecem inativos.

## Validação realizada

SQLite e PostgreSQL real (PostgreSQL 16 local, isolado em schemas de teste): 29 casos distintos aprovados, cobrindo autenticação, CSRF, administração, quatro páginas, filtros, ROI, deduplicação/revisões, sincronização, persistência após reinicialização, migração atômica e recusa de TLS inseguro. A transferência ida/volta foi conferida por tabela, inclusive hashes de senha utilizáveis, revisões, logs e limites; a cópia de SQLite v1 preservou o SHA-256 do arquivo original. Exportação/restauro em arquivo novo também foram testados.

Chromium confirmou as cinco rotas (quatro públicas e login), navegação e ausência de overflow/erros JavaScript em 390 e 1440 px, com o servidor Waitress conectado ao PostgreSQL de teste. Nenhum arquivo de templates/estilos do visual aprovado foi alterado. A conexão Neon real, contas gratuitas e persistência após redeploy externo ainda precisam ser verificadas quando as plataformas forem conectadas.
