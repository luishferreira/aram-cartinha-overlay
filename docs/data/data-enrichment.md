# Identidade, builds e análise das cinco fontes

Trabalho de 30/10/2026, limitado à camada de dados. Sem overlay, captura do jogo, IA ou novas fontes. A atualização para um novo patch fica adiada até haver um patch novo para acompanhar; os rótulos de versões atuais continuam preservados sem equivalências presumidas.

## Catálogo e qualidade

Cada publicação contém `canonical-augments.json`, com identidades, nomes por idioma, atributos originais, disponibilidade declarada e cobertura de métricas por fonte/escopo/etapa/patch. A presença no catálogo ou em estatísticas não confirma que uma carta está disponível para escolha no jogo.

Três aliases foram revisados com base na chave interna e na descrição, em `data/config/identity-aliases.json`:

| arammayhem | ID do jogo | Nome OP.GG | Evidência |
|---|---|---|---|
| Double Defense | 2144 | Bolstered | Chave `DoubleDefense`, escudo de habilidade maior conforme vida faltante do alvo |
| Rabble Rousing | 1067 | Rejuvenation | Chave `ARAM_RabbleRousing`, cura ao usar habilidade |
| Void Immolation | 1361 | Icathia's Fall | Chave `ARAM_Quest_VoidImmolation`, mesma missão com Sunfire Aegis e Hollow Radiance |

O alias une a identidade, não os valores de efeito, as datas ou a disponibilidade. As descrições que divergem continuam distintas. Se a chave interna esperada mudar, a importação interrompe para revisão. O arquivo de aliases também é arquivado como evidência.

Os identificadores sem evidência suficiente continuam em namespace da fonte. A auditoria distingue casos declarados retirados pela fonte dos casos declarados ativos sem correspondência. Campos conflitantes, cartas ausentes do download atual e tokens de efeito não resolvidos ficam explícitos em `data-quality.json`.

A revisão reduziu os IDs arammayhem não resolvidos de 42 para 39. Destes, 38 são declarados retirados pelo próprio MCP; o único declarado ativo sem correspondência é `yowch_my_coins` (Yowch, My Coins!), também sem popularidade publicada. Isso não confirma que esteja disponível no jogo. Há ainda 72 IDs numéricos vistos em estatísticas sem metadados nos catálogos coletados: são identificados como `statistics_only`, separados das 320 entidades com catálogo. Esses IDs não viram automaticamente cartas atuais nem lacunas de tradução de cartas atuais.

## ARAMKit: coleta completa de builds por carta

Release fixado: `16.21-20261030-5f02d4c12c0d`. Foram adquiridos os 173 recursos `champion-details/<id>-single-augments.json`, totalizando 598.489.425 bytes de payload (aproximadamente 571 MiB). A coleta foi sequencial, com intervalo e retomada por hash, sem consultar um patch novo.

Os arquivos publicados ficam em `research/aramkit-data/conditional-snapshots/19c101c962cb82f77df8/`. O ponteiro `conditionals-current.json` só é escrito depois de verificar todos os campeões. O manifesto preserva URL, data de coleta, tamanho e hash por arquivo. Os originais também passam ao arquivo de conteúdo do pipeline.

A contagem independente dos arquivos brutos encontrou 21.918 grupos de itens condicionados (4.048.665 linhas entre geral/slots), 126.844 perfis de builds condicionadas, 227.479 rotas e 2.403.861 opções ligadas às rotas. Todos os 173 campeões têm alguma build condicionada publicada. Esses números são registros hierárquicos, não partidas distintas e não combinações de todas as cartas possíveis.

```powershell
python tools/data/collect_aramkit_conditionals.py
python tools/data/pipeline.py build
python tools/data/pipeline.py builds --champion champion:game:11 --augment augment:game:1058 --limit 3
python tools/data/pipeline.py builds --champion champion:game:11 --selection filtered --limit 3
```

O primeiro comando usa a versão fixada no manifesto já existente; repeti-lo retoma/reutiliza arquivos conferidos. Não equivale a atualizar o projeto para outro patch.

A normalização preserva:

- Arquétipo e população do grupo, separando `filtered`, `unfiltered` e `single_augment`.
- Perfis com conjunto de itens e métricas próprias.
- Rotas com ordem de compra, amostra e popularidade próprias.
- Itens iniciais, botas e itens posteriores ligados à rota correspondente.
- Itens condicionados a uma carta, separados em geral e por slot.

Componentes repetidos nos itens iniciais permanecem repetidos. A opção de botas com ID zero vira uma opção explícita sem item, nunca um item de jogo fictício. As proporções são validadas em 0–1. Os denominadores são rotulados pela hierarquia publicada; a definição exata da elegibilidade dos filtros e slots continua desconhecida.

Consultas com carta não voltam silenciosamente a builds sem condicionamento. Uma base por uma carta não informa automaticamente a melhor build com duas ou três cartas: não combinamos as estimativas como se fossem independentes. Perfis de builds concluídas também sofrem viés de duração e seleção de partidas.

As tabelas mantêm grupos e rotas estruturados para processar um campeão por vez. Isso evita carregar milhões de opções como objetos simultaneamente em memória. As contagens dessa camada ficam em `report.json`, campo `builds`, separadas das observações anteriores.

## Combos e regras

`combo-review.json` contém fichas dos 666 conjuntos editoriais. Lista de membros, explicação, tier editorial, campeão e artefato são preservados. Requisitos, alternativas, itens e conflitos desconhecidos ficam como `null`; uma lista de várias cartas nunca vira automaticamente uma regra que exige todas elas, nem todos os pares possíveis.

Há quatro interpretações manuais iniciais em `data/config/rules.json`: Vladimir com Ethereal Weapon/Mystic Punch; Katarina com Jeweled Gauntlet/Vulnerability; Yuumi com Circle of Death/Tank Engine; Aatrox com Protein Shake/Iceborn Gauntlet. Todas continuam hipóteses editoriais com explicações PT-BR/inglês. Não adotamos multiplicadores de dano não verificados. Em Aatrox, a lista também menciona Critical Healing, mas a explicação não prova que seja requisito: ele não foi adicionado à regra.

A triagem aponta 254 dos 666 conjuntos com algum membro declarado retirado pela fonte, 158 com alguma identidade não resolvida e uma explicação insuficiente (`Nothing.`). As categorias se sobrepõem. Portanto, o acervo editorial é útil para explicar ideias, mas não deve ser usado integralmente como recomendação atual. Esses sinais não provam por conta própria que o jogo retirou as cartas.

Condições externas, como aliado tanque e coordenação, são explícitas. Mesmo que uma regra passe a `reviewed`, condições não avaliadas impedem classificá-la como ativa. Os demais combos ainda precisam de revisão semântica: ter a ficha pronta não significa ter 666 regras mecânicas confirmadas.

## Comparações e estatística

`source-comparisons.csv` cruza métricas pelo mesmo campeão e ID de carta. Etapas específicas, listas restritas por raridade e desempenho ARAMGG de patches históricos ficam fora dessa comparação geral. Artefatos, versões, datas e população/região publicada acompanham as métricas.

`source-comparisons.json` calcula Spearman dentro de cada campeão, tratando empates. A média dos coeficientes é descritiva, não uma votação de fontes nem um teste de independência. Popularidade, desempenho OP.GG, win rate e tier continuam dimensões distintas. O patch desconhecido das estatísticas OP.GG está marcado; essas comparações não validam concordância no patch atual.

Na coleta atual, a média dos coeficientes por campeão foi:

| Dimensões | Correlação de Spearman média | Registros pareados |
|---|---:|---:|
| Tier OP.GG × popularidade OP.GG | 0,963 | 35.797 |
| Tier OP.GG × win rate ARAMKit | 0,461 | 22.617 |
| Tier Blitz × win rate ARAMKit | 0,861 | 20.985 |
| Tier Blitz × win rate ARAMGG | 0,800 | 19.303 |
| Tier Blitz × tier OP.GG | 0,598 | 21.843 |

Esses resultados sustentam manter força e popularidade separadas; não revelam a fórmula proprietária dos tiers. A comparação OP.GG é exploratória porque seu patch estatístico é desconhecido. O indicador próprio de desempenho OP.GG continua sem ser tratado como win rate. Dados de fontes potencialmente relacionadas não comprovam validação independente.

`relation-statistics.json` preserva pares e trios publicados, suas amostras, o caráter de lista limitada e referências individuais compatíveis. Diferenças entre win rate da combinação e de um membro são descritivas, em pontos percentuais, com amostras sobrepostas. Para ARAMGG, a referência exige patch, data, origem e região iguais. Dados históricos continuam identificados como históricos.

Intervalos Wilson de 95% só são calculados quando há amostra. Eles usam a taxa arredondada publicada e pressupõem resultados binomiais independentes; não corrigem vieses de coleta, jogadores repetidos, escolha de campeões/cartas ou sobreposição de partidas entre fontes. Não calculamos significância causal nem somamos amostras de fontes, etapas, perfis ou rotas.

## Verificação

```powershell
python -m unittest discover -s tests -v
python tools/data/pipeline.py verify
```

Os testes adicionais cobrem preservação da hierarquia condicional, componentes repetidos, opção sem botas, integridade dos recursos, unidades, empates, falta de amostras, exclusão de etapas/históricos da comparação e bloqueio de regras com condições externas não avaliadas.
