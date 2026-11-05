# Ranking do Detetive

Projeto independente, exclusivo de `sousaweliton930-droid/ranking-do-detetive-novo`.
Flask + SQLite/PostgreSQL + Waitress, sem build de JavaScript, CDN, dados iniciais ou serviços obrigatórios adicionais. Python 3.12+ em Linux. As migrações criam tabelas vazias na primeira execução, sem recriar dados existentes.

## Execução local

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.lock
COOKIE_SECURE=0 .venv/bin/python app.py
```

Abra http://localhost:8000. As quatro áreas públicas dispensam login. Para criar a primeira conta, use o comando abaixo e digite uma senha própria de no mínimo 12 caracteres; nada é salvo em texto simples.

```sh
.venv/bin/flask --app app:create_app create-admin seu_usuario
```

Acesse `/admin`. É possível cadastrar/editar canais, rascunhar/publicar/editar publicações, cadastrar/editar e ativar/desativar planilhas e visualizar os últimos 50 registros de sincronização. Sem conta criada não há acesso administrativo. Não existe cadastro público nem senha padrão. Conteúdo editorial é texto simples, escapado no HTML.

## Prévia em ambiente remoto

O projeto oferece `npm run dev` para ferramentas de prévia; esse comando inicia o mesmo servidor Flask/Waitress, sem instalar dependências Node. Prepare a `.venv` conforme as instruções acima. A porta é definida por `PORT` (padrão 8000).

`http://localhost:8000` só funciona no computador/ambiente que executa o servidor. Não é um link remoto compartilhável. No ChatGPT, a prévia exige o encaminhamento fornecido pelo ambiente. Se `sites-preview start /workspace/ranking-do-detetive-novo` retornar `preview relay unavailable`, o encaminhamento está indisponível; iniciar ou reiniciar Flask não resolve essa falha de infraestrutura. Não publicar externamente nem desabilitar as proteções administrativas para contornar esse problema.

## Testes e verificação

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q app.py integrations tests
node --check static/app.js
# Opcional, com Playwright e Chromium instalados e servidor local ativo:
node tests/browser.cjs
```

Os testes usam banco temporário e entradas sintéticas exclusivamente dentro dos testes; nenhum dado é inserido na aplicação real. Não substituem um teste real da API Google.

## Google Sheets (não conectado nesta etapa)

1. Em um projeto Google novo, habilite a API Google Sheets e crie uma conta de serviço exclusiva com acesso somente de leitura às planilhas desejadas. Não reutilize recursos do V63.
2. Compartilhe cada planilha aprovada com essa conta de serviço. Instale a credencial JSON fora do repositório, legível apenas pelo usuário do serviço. Defina `GOOGLE_APPLICATION_CREDENTIALS` com esse caminho no servidor.
3. Cadastre o canal e o ID da planilha na administração; informe intervalo A1 contendo uma linha de cabeçalho. Mapeie cabeçalhos exatos para `id`, `date`, `stake` e `profit`. Todos são obrigatórios; `id` precisa ser estável e único dentro da planilha. Stake e lucro devem estar na mesma unidade.

Formato do mapeamento (exemplo de configuração, não dados):

```json
{"id":"ID","date":"Data","stake":"Unidades","profit":"Lucro","date_format":"%d/%m/%Y %H:%M","decimal":",","timezone":"America/Sao_Paulo"}
```

Sem `date_format`, a data deve ser ISO 8601; sem fuso explícito, aplica-se `timezone` (padrão America/Sao_Paulo). Datas são armazenadas em UTC. O importador usa FORMATTED_VALUE; escolha um formato de data consistente e configure separador decimal. Fórmulas são lidas pelo resultado calculado pelo Google. Valores vazios, não finitos, stake não positiva, perdas maiores que stake, datas futuras ou IDs repetidos rejeitam a importação inteira. Não são inferidos resultados a partir de texto livre. ROI = soma dos lucros / soma das stakes × 100. Sem entradas, ROI e resultado aparecem como indisponíveis.

4. Ative a planilha somente após conferir o mapeamento. Execute `.venv/bin/flask --app app:create_app sync` e confira o registro administrativo e os valores reais. Sem credenciais, o comando registra erro; nenhuma sincronização real foi validada nesta entrega.
5. Agende esse comando em cron a cada minuto; a aplicação respeita `SYNC_INTERVAL_MINUTES` (padrão 15) entre tentativas por planilha. Use caminhos absolutos, mesmo ambiente e banco do servidor web. Exemplo de estrutura de cron:

```cron
* * * * * cd /srv/ranking-do-detetive-novo && /srv/ranking-do-detetive-novo/.venv/bin/flask --app app:create_app sync
```

Configure variáveis no serviço/arquivo de ambiente restrito, não na linha de cron ou no Git. O comando importa apenas IDs cadastrados e ativados; não descobre arquivos na conta. Upsert por `(sheet_id, external_id)` evita duplicação; alterações geram revisão com valores anteriores. Linhas removidas da fonte permanecem no histórico. Logs distinguem tentativa, sucesso e erro sem persistir respostas remotas ou tokens. Bloqueio local impede sincronizadores simultâneos. Use uma instância de aplicação e um disco local persistente, não vários hosts com cópias independentes do SQLite.

## Produção gratuita e atualizações pelo GitHub

`render.yaml` usa **Render Free sem disco**, com PostgreSQL persistente **Neon Free** em `DATABASE_URL` (segredo com TLS). `SECRET_KEY` é gerada no serviço. SQLite continua suportado para desenvolvimento e reversão; não usar SQLite efêmero em produção. Nenhum serviço pago está autorizado.

Publicação de `main` somente após PR aprovado e checks. Estado de conexão/publicação deve ser confirmado nas plataformas: arquivos prontos não significam site publicado. Consulte [docs/PRODUCAO.md](docs/PRODUCAO.md) para ativação, criação de administrador sem Shell Render, transferência reversível de dados, backup e recuperação.

Para os testes reais de PostgreSQL, configure `TEST_POSTGRES_URL` para um banco **exclusivo de testes**. A suíte cria e remove schemas temporários próprios; nunca usar banco Neon de produção. O workflow GitHub já fornece uma instância PostgreSQL efêmera. Sem essa variável, os testes desse backend são explicitamente ignorados, não simulados.

## Integrações futuras e limites

`integrations.SourceAdapter` define o contrato inicial de adaptadores; `integrations/sheets.py` contém o único importador implementado. Telegram/redes sociais não possuem coleta, credenciais ou bot ativo. Extensões devem normalizar dados para o mesmo modelo, com fonte autorizada e IDs estáveis.

Esta versão não inclui recuperação de senha por e-mail, múltiplos perfis administrativos ou edição manual de entradas; provisione novas contas pelo CLI. Datas na tabela pública são identificadas como UTC. Gráfico e tabela usam os mesmos registros e filtros; histórico vazio não desenha resultados. O volume de dados deve ser monitorado; paginação e agregação no banco serão necessárias antes de históricos muito grandes. Nenhum Worker, banco, site ou credencial antigo é usado.
