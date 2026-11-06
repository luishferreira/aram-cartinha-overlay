# Builds do Blitz — sondagem de 06/11/2026

Solicitação: verificar aquisição das builds/caminhos do Blitz para futura comparação por fonte no Arsenal. Nenhuma build nova foi importada no cliente e a base ativa de Mayhem não foi alterada.

## Aquisição e evidência

Arquivos permanentes em `research/blitz-builds/probe-2026-11-06/`: HTML público atual, metadados da coleta, JSON de builds incorporado nas páginas, respostas de três consultas do endpoint e hashes em `checksums.json`. As páginas foram obtidas por requisições HTTPS normais, sem login, cookies privados ou execução de código dos aplicativos.

O HTML atual usa scripts `application/json` com `data-sveltekit-fetched`/`data-url`. O envelope contém um `body` JSON com os dados. O recurso observado é:

`https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/champion_builds_tags?champion_id=<id>&queue_id=HOWLING_ABYSS_ARAM`

Nas três páginas com rota `/aram-mayhem` examinadas, os dados de builds retornam **queue_id 450, ARAM normal**, patch **16.22**:

| Campeão | Caminhos publicados |
| --- | --- |
| Master Yi | AD; Crítico; Crítico + On-hit; On-hit |
| Tristana | On-hit; Crítico; AD |
| Nilah | Crítico |

O snapshot antigo do Master Yi já continha o mesmo recurso de builds da fila 450 no patch 16.21. Separadamente, os dados de tiers de cartas/itens de `aram_mayhem_champion` são outro recurso; não autorizam atribuir o modo Mayhem às builds acima.

Consultas do endpoint com `queue_id=2400` e `queue_id=ARAM_MAYHEM` retornaram HTTP 200 com lista vazia. Isso **não prova que inexista outro recurso de builds específico de Mayhem**. O comportamento do aplicativo desktop não foi estabelecido por esta sondagem do site. Não foi feita coleta em massa das builds de todos os campeões enquanto o modo da fonte permanece essa questão aberta.

## Conteúdo disponível

- `name_tags`, `build_id`, `build_type_name`: caminhos/rótulos nativos. Nomes como `Crit + On-Hit` permanecem distintos de um caminho canônico próprio até haver correspondência revisada.
- `startingItems`: conjuntos iniciais, IDs, jogos, vitórias, popularidade e campos de desempenho publicados.
- `coreItems`: alternativas de núcleo ordenadas e métricas próprias; preservar os três itens como núcleo, sem fabricar seis itens completos.
- `itemsAfterCore`: opções posteriores condicionadas ao conjunto de núcleo e ao slot publicado.
- `itemOrders`: sequências de componentes por item-alvo, com métricas. Componentes repetidos devem permanecer repetidos. Não é automaticamente uma rota global única de seis itens.
- `situationalItems`: itens, popularidade, campos de desempenho/índices e contagens; escopo permanece o caminho da fonte.
- Métricas gerais do caminho, patch e queue_id. Há dados adicionais de runas/feitiços/habilidades, que não serão aplicados no cliente por esta tarefa.

No Master Yi On-hit da coleta, há três núcleos, 112 conjuntos iniciais publicados, 65 entradas situacionais e 26 itens-alvo com sequências de componentes. São registros/opções da fonte, não 112 builds completas ou novas partidas independentes.

## Unidades a esclarecer

Há valores negativos em `situationalItems.win_rate`. Esse campo não pode ser rotulado como probabilidade de vitória apenas por seu nome. `averageIndex`, `adjusted_win_rate` e diferenças publicadas também exigem interpretação contextual antes de ordenar uma linha como “maior win rate”.

Algumas taxas publicadas em subconjuntos não coincidem com `wins/games`. Preservar ambos, sem substituir a taxa original por um cálculo próprio nem atribuir uma fórmula de ajuste não demonstrada.

## Próximo uso possível

Decisão do usuário em 06/11/2026, após a comparação das rotas: **excluir o Blitz das fontes de itens e builds do projeto**, incluindo os tiers de itens específicos de Mayhem. Não integrar esses dados ao Arsenal, à comparação de builds ou às recomendações de itens. O Blitz permanece como fonte de cartas.

Os arquivos da pesquisa permanecem arquivados como evidência. A coleta em massa e a investigação adicional do aplicativo para itens deixam de ser próximos passos. Nenhum desses dados havia sido integrado à geração ativa de arsenais.

## Comparação direta `/aram` × `/aram-mayhem` — 06/11/2026

Nova coleta pareada das seis páginas públicas, preservada separadamente em `research/blitz-builds/route-comparison-2026-11-06/`. `comparison.json` contém o resultado e a diferença estrutural; os seis HTMLs e todos os recursos JSON incorporados foram salvos com metadados e checksums. O coletor reproduzível é `research/blitz-builds/compare_routes.py` (o diretório de destino deve ser novo).

| Campeão | Caminhos presentes nas duas rotas | Comparação de `payload.data` |
| --- | --- | --- |
| Master Yi | AD; Crit; Crit + On-Hit; On-Hit | Idêntico, quatro registros completos |
| Tristana | On-Hit; Crit; AD | Idêntico, três registros completos |
| Nilah | Crit | Idêntico, um registro completo |

Em cada par, a URL de `champion_builds_tags` é exatamente a mesma, com `queue_id=HOWLING_ABYSS_ARAM`. Todos os oito registros contêm `queue_id=450`, patch `16.22`. A igualdade foi verificada recursivamente em todos os campos da lista `data`, incluindo iniciais, núcleos, componentes, opções após o núcleo, situacionais, jogos, vitórias e taxas. As respostas completas diferem **somente em `/meta/generated_at`**, ou seja, no horário de geração, sem diferença de conteúdo das builds nesta coleta.

As únicas URLs de recursos incorporados adicionais na rota Mayhem, nos três pares, são:

- `aram_mayhem_champion?champion_id=<id>`: objeto específico de Mayhem com patch, data, tiers de cartas, tiers de itens e tier do campeão. Não contém os caminhos e sequências do recurso de builds.
- `https://utils.iesdev.com/static/json/lol/mayham/16.22/augments_en_us`: catálogo de cartas em inglês.

Portanto, a rota Mayhem **reutiliza os mesmos dados de builds de ARAM normal nesta amostra**, mas acrescenta recomendações de tiers de cartas e itens específicas de Mayhem. A existência desse tier de item não transforma as sequências nem suas taxas em estatísticas de Mayhem. Os recursos de estatísticas de campeão de ARAM incorporados também usam a mesma URL nos dois modos; a inclusão de recursos genéricos de navegação não implica que todos estejam visíveis na interface.

Escopo da conclusão: dados incorporados nas páginas públicas dos três campeões na data da coleta. Não houve inspeção do renderizador para determinar cada bloco efetivamente mostrado, nem validação do aplicativo desktop ou de todos os campeões. Não importar as duas rotas como fontes independentes: isso duplicaria a mesma evidência de builds.
