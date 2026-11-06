# Auditoria de fontes de itens — 06/11/2026

Solicitação: ampliar o arammayhem.com, auditar OP.GG e MayhemStats e estudar as recomendações do LemonNation. O Blitz continua excluído de itens e builds; METAsrc não foi retomado. A auditoria inicial foi isolada da produção.

**Atualização posterior em 06/11:** OP.GG ampliado para 173 campeões, com 2.595 núcleos, 833 opções de botas, 2.595 conjuntos iniciais e 5.127 registros de itens. Arquivo separado em `research/item-sources/opgg-items-2026-11-06/`, sem sobrescrever os pares ARAM/Mayhem desta auditoria. ARAMKit, OP.GG, Mayhem.com e LemonNation já alimentam os [arsenais comparáveis por caminho](item-set-comparisons.md).

## Resultado e uso recomendado

| Fonte | Evidência adquirida | Próximo uso possível | Limite decisivo |
| --- | --- | --- | --- |
| ARAMKit | Base anterior, não recoletada nesta auditoria | Continua sustentando os arsenais existentes | Esta auditoria não revalida nem atualiza o snapshot anterior |
| arammayhem.com | 173 páginas, 3.126 opções estruturadas de itens | Segunda referência ampla de iniciais, botas, núcleos e posteriores | Sem contagem de jogos por opção; até cinco alternativas na página, não universo completo |
| OP.GG | Seis páginas: três campeões × ARAM/Mayhem, mesmo filtro e patch | Candidato à coleta completa de itens para todos os campeões | Dados diferentes entre modos, mas fornecedor/amostragem originais não foram demonstrados |
| MayhemStats | Agregados completos consultados para fila 2400 nos patches 26.21 e 26.22 | Evidência adicional por item e tempo de compra | Amostra recente pequena; ranking individual não equivale a build conjunta |
| LemonNation | Todas as 66 builds autorais listadas, em 63 campeões | Caminhos editoriais, alternativas e relações build/carta para revisão | Atualizações em pausa; patch das builds não especificado |

Os arquivos são uma base de pesquisa separada e consultável offline. As fontes não foram somadas em um score nem inseridas automaticamente nos arsenais.

## arammayhem.com: expansão efetiva sobre o MCP

As páginas dos **173 campeões** foram arquivadas com os dados apresentados na seção de itens. Contagem normalizada:

| Grupo | Opções |
| --- | ---: |
| Iniciais | 864 |
| Botas | 532 |
| Núcleo | 865 |
| Outros itens completos | 865 |
| Total | **3.126** |

São alternativas de grupos, não 3.126 builds completas. Preservamos a ordem dos itens dentro do núcleo e a posição da opção na fonte. Todos os slugs de itens usados nessas opções foram relacionados a IDs do jogo pelo catálogo oficial da própria fonte; não houve item sem correspondência. Malphite publica quatro opções iniciais, enquanto os demais publicam cinco. Botas variam por campeão.

O MCP anterior tinha 2.076 opções no conjunto dos campeões: a expansão acrescenta **1.050 opções, aproximadamente 50,6%** em quantidade. Essa comparação mede cobertura publicada em coletas distintas, não evolução de força entre datas.

Também fizemos consultas novas do MCP para Master Yi, Brand e Lulu, na mesma sessão da coleta HTML. Nos três, patch **26.21** e data **05/11/2026** coincidem entre canais. As três primeiras opções de cada grupo coincidem em IDs, ordem, popularidade e vitória. A página apresenta cinco iniciais, cinco núcleos e cinco posteriores; botas têm três opções no Yi/Brand e quatro na Lulu, contra até três pelo MCP. Assim, ficou demonstrado que o HTML acrescenta alternativas ao resumo do MCP. Os dois canais continuam sendo a mesma família de fonte.

O índice público coletado identifica release `website:20261106_104008:f649f1a21ba7`, patch 26.21, e descreve as estatísticas como amostra limitada de Mayhem, não mundial. Essa declaração não é comprovação independente da origem de cada partida. As páginas não fornecem o denominador/amostra de cada opção nem recorte por cartas adquiridas. O índice atual explicita escopo de licença dos downloads como popularidades; não estendemos essa licença automaticamente às taxas de vitória, ao HTML ou às respostas MCP.

Fontes primárias: [Master Yi](https://arammayhem.com/build/masteryi/), [Brand](https://arammayhem.com/build/brand/), [Lulu](https://arammayhem.com/build/lulu/), [índice de dados](https://arammayhem.com/data/v1/index.json), [MCP](https://arammayhem.com/use-with-ai/).

## OP.GG: ARAM e Mayhem diferem nesta amostra

Comparamos **Master Yi, Ashe e Lulu**, sempre `region=global`, `tier=all`, patch **16.22**, conforme os dados incorporados nas próprias páginas. Foram extraídas quatro tabelas por página: 15 núcleos, cinco botas, 15 conjuntos iniciais e 30 itens. São limites das tabelas coletadas, não comprovação de ausência de outras opções no backend.

Os componentes serializados identificam `mode=aram` na página normal e `mode=aram_mayhem` na página Mayhem. **As listas ordenadas dos núcleos e os registros completos diferem nos três pares.** É uma situação diferente do Blitz, onde todos os dados de builds comparados eram idênticos entre rotas.

Exemplos da primeira opção publicada — sem assumir que ela seja a mais popular:

| Campeão | ARAM normal | Mayhem |
| --- | --- | --- |
| Master Yi | Coletora → Rei Destruído → Gume; 610 registros | Coletora → Gume → Lorde Dominik; 24 registros |
| Ashe | Yun Tal → Runaan → Gume; 1.316 registros | Mesmos três IDs nessa opção; 101 registros |
| Lulu | Lágrima → Pedra Lunar → Diadema → Turíbulo; 856 registros | Mesmos quatro IDs nessa opção; 31 registros |

A primeira opção igual na Ashe/Lulu não torna a tabela igual: métricas e outras sequências diferem. Preservamos inclusive a Lágrima no núcleo da Lulu; não presumimos que cada núcleo seja composto de exatamente três itens lendários.

**O que a auditoria confirma:** dados de itens diferentes, rotulados por modo, no mesmo patch e filtros. **O que não confirma:** acesso às partidas originais, método de coleta, região de origem efetiva ou contagem independente por jogo. Também não localizamos por esta sondagem uma documentação pública de metodologia dos itens. Uma tentativa de endpoint com sufixo `/aram-mayhem` retornou 404; isso não é evidência de inexistência de API e não foi substituído por respostas de ARAM normal.

Manter as porcentagens e contagens publicadas. Os denominadores das tabelas podem ser diferentes; não somar opções sobrepostas nem usar a popularidade de uma tabela como probabilidade de uma sequência completa de seis itens.

Fontes primárias: [Yi Mayhem](https://op.gg/lol/modes/aram-mayhem/masteryi/items), [Yi ARAM](https://op.gg/lol/modes/aram/masteryi/items), [Ashe Mayhem](https://op.gg/lol/modes/aram-mayhem/ashe/items), [Lulu Mayhem](https://op.gg/lol/modes/aram-mayhem/lulu/items).

## MayhemStats: origem mais transparente, cobertura recente pequena

O site declara partidas recebidas de jogadores via LCU, contribuição opcional e deduplicação. A maior parte histórica vem de uma carga inicial. Consultamos somente as mesmas **views agregadas públicas** que o frontend usa, com a chave anônima publicada pelo próprio site; não acessamos partidas individuais nem instalamos seu aplicativo.

A chave de acesso público não foi registrada em manifests nem cabeçalhos de logs. Ela existe no JavaScript público arquivado, como no site original. Não é uma credencial da conta do usuário.

Os dados completos desta coleta filtram explicitamente **queue_id=2400** e patches **26.21/26.22**, preservados separadamente:

| Conteúdo | 26.21 | 26.22 |
| --- | ---: | ---: |
| Jogos na distribuição de patches publicada | 596 | 50 |
| Campeões com observações | 173 | 150 |
| Registros campeão/item no inventário final | 7.132 | 1.799 |
| Registros campeão/item em eventos de compra | 9.557 | 3.297 |

São **8.931 registros de inventário e 12.854 de compras**, não 21.785 jogos ou builds. A soma de participações dos campeões foi 5.960/500, consistente com dez participações por jogo e as contagens 596/50. O total comunitário geral de 139.421 jogos cobre 26 patches e não deve ser usado como N de uma recomendação atual. No patch 26.22, **nenhum registro campeão/item coletado alcança 20 observações**, em nenhuma das duas views.

Arquivamos e lemos o SQL e o código de ranking publicados no commit `aa61489b83a590007b9dbd29c1bd866eb4d6dda4` do repositório oficial:

- `item_stats`: conta ocorrências dos IDs nos sete slots do inventário final, agrupadas por patch/fila/campeão/item. `picks` é contagem de ocorrências em slots, não garantia de participantes únicos se o mesmo item ocupar dois slots. Não mede ordem de compra.
- `item_purchase_stats`: considera o primeiro evento `add` por participante/item/partida, agregando contagens, vitórias e tempo médio da primeira aquisição em segundos. Ordenar médias pode sugerir uma progressão, mas não comprova que aquela sequência tenha sido comprada junto.
- `rankForBuild`: filtra por amostra mínima e registro sem saldo negativo de vitórias, ordena pelo limite inferior de Wilson e seleciona até o limite solicitado. A lista resultante é um ranking de itens, não uma combinação conjunta testada.
- As views são agregados materializados. A política de atualização no código prevê recomputação periódica; a leitura atual não é uma transmissão de partidas em tempo real.

O código é evidência auditável do método publicado, não prova independente de integridade de cada upload ou de que o deploy remoto corresponde integralmente ao commit. As mesmas partidas também podem aparecer em outras bases comunitárias; não assumir independência entre fornecedores.

As primeiras páginas sem filtro foram preservadas como **sondagem parcial** e marcadas `complete=false` quando truncadas. A coleta filtrada foi completada por paginação, com contagens totais e chaves únicas verificadas. Timeouts de transferência foram resolvidos retomando em lotes de 500; os arquivos anteriores não foram descartados.

Fontes primárias: [metodologia](https://mayhemstats.com/about/), [guia](https://mayhemstats.com/guide/), [repositório](https://github.com/MyNamesEMurray/MayhemStatsTracker), [SQL dos agregados no commit auditado](https://github.com/MyNamesEMurray/MayhemStatsTracker/blob/aa61489b83a590007b9dbd29c1bd866eb4d6dda4/supabase/migrations/20260824120000_materialize_stats_rollups.sql), [ranking](https://github.com/MyNamesEMurray/MayhemStatsTracker/blob/aa61489b83a590007b9dbd29c1bd866eb4d6dda4/src/shared/score.ts).

## LemonNation: caminhos e interações editoriais

Coletamos todas as **66 URLs de builds autorais** que o índice listava, abrangendo **63 campeões**. As builds da comunidade não foram coletadas. Há:

- 66 textos de notas, com referências aos itens preservadas e tooltips repetidos removidos apenas na versão normalizada;
- 1.097 recomendações de cartas vinculadas a builds, preservando ID nativo, raridade e marcações de prioridade;
- 51 grupos explícitos de escolha entre itens;
- blocos de início, botas, núcleo, opções e caminhos nomeados pelo autor, inclusive variantes de AD/AP e ajustes contra tipos de oponentes.

Mantivemos `item`, `choose_one` e separadores como tipos distintos. Uma alternativa “Nashor OU Cajado OU Pedra Lunar” não vira uma obrigação de comprar os três. As notas não foram convertidas automaticamente em regras executáveis.

Exemplo útil: a Lulu de velocidade de ataque tem escolhas de itens conforme a intenção de dano ou suporte, recomendações ligadas a cartas de cura/escudo e uma advertência sobre mudar de direção com Purist–Caster. Esse é material diretamente relevante para nosso futuro seletor de caminhos e avaliação contextual de cartas. Continua sendo hipótese editorial a revisar, não proibição confirmada pelo jogo.

O autor anunciou pausa em 20/10/2026. As datas `dateModified` coletadas vão de **14/08 a 29/09/2026**. Data de modificação não informa patch de balanceamento; todas as builds normalizadas mantêm patch desconhecido e estado de revisão pendente. O catálogo de cartas e descrições da página pode estar em outra versão que o texto da build.

Fontes primárias: [índice e aviso do autor](https://lemonnation.gg/builds), [Lulu](https://lemonnation.gg/builds/lulu?build=build-1), [Ashe](https://lemonnation.gg/builds/ashe?build=build-1), [Gragas](https://lemonnation.gg/builds/gragas?build=tank-build).

## Artefatos e verificações

Tudo está em `research/item-sources/2026-11-06/`, com HTML/JSON/JS/SQL originais, URL, horário, hash e status; derivados por fonte em `normalized/`. A verificação offline cobre hashes de 347 artefatos, presença das 239 páginas planejadas (173 + 66), todos os IDs de itens do arammayhem.com, IDs dos 63 campeões do LemonNation, faixas de métricas, diferenças entre modos do OP.GG, concordância entre MCP/HTML nos três pares e completude/unicidade da paginação filtrada do MayhemStats.

Reproduzir a normalização e a validação sem rede:

```powershell
python research/normalize_item_source_audit.py
python research/validate_item_source_audit.py
```

Os coletores são ferramentas de pesquisa com arquivos arquivados e retomada, não uma rotina automática de atualização de patch. As definições de mudanças de cartas/patch notes continuam adiadas. Antes de integrar: ampliar a coleta do OP.GG para todos os campeões; revisar a admissão de fontes e versões; manter caminhos observados, rankings individuais e notas editoriais separados na apresentação.
