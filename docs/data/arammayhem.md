# arammayhem.com: dados disponíveis e uso no projeto

Coleta em 30/10/2026. Pesquisa e preparação de dados; nenhum overlay implementado. O projeto não usará Overwolf.

## O que foi guardado

Fonte: [downloads oficiais](https://arammayhem.com/data/) e [índice de arquivos](https://arammayhem.com/data/v1/index.json).

Snapshot `20261029T205745Z-abf89a005fb2`, release `website:20261029_135745:fbaed7ce8a42`. Patch informado pelo publicador: **26.21**; data das estatísticas atuais: **29/10/2026**. A data da coleta é outra informação.

| Dataset atual | Registros | Utilidade | Limite principal |
| --- | ---: | --- | --- |
| Campeões | 173 | Catálogo, popularidade global, variação entre patches | Não traz taxa de vitória no download |
| Cartas | 207 | Nomes, raridade, popularidade global, introdução/retirada | Não traz descrição de efeito nem popularidade por campeão |
| Combos | 666 | Referências de campeão/cartas, tags editoriais, links | Não traz explicação, desempenho ou data de validação por combo |
| Itens | 200 | IDs do jogo, nomes, categoria e custo | Não traz efeitos nem builds no download |
| Histórico | 12 patches, 26.10–26.21 | Séries de popularidade de campeões/cartas | Datas históricas podem ser estimadas; não há histórico de combos/itens |

Foram preservados JSON e CSV: **56 datasets**, em **28 pares**. O snapshot tem 61 arquivos com hash no manifesto, além do próprio manifesto, aproximadamente 5,1 MiB. Os dados originais não foram alterados.

## Cobertura real e inconsistências

- Combos cobrem **157 de 173 campeões**. A ausência dos outros 16 não significa que não tenham sinergias.
- Há **152 IDs de cartas diferentes** nos combos: **110** estão no catálogo atual de popularidade; **42** não estão. Outros **97 dos 207** registros do catálogo não são citados em combos. Isso não permite concluir sozinho se uma carta foi removida: o catálogo de popularidade pode ser incompleto.
- Dos 207 registros, **3 possuem `retiredPatch`**. Não rotular automaticamente os 207 como cartas ativas.
- **311 entradas de combo têm uma carta**: representam também recomendações campeão/carta. Outras têm até **15 cartas**; podem representar alternativas ou um conceito de build. Não converter a lista em uma exigência de possuir todas simultaneamente.
- Tags são editoriais (`god`, `strong`, `trap`, `blackTech`, `entertainment`, `bug`); várias entradas não têm tags. Não são probabilidades ou tiers estatísticos.
- O download tem sete idiomas, **sem PT-BR**. Usaremos IDs para cruzar com catálogos traduzidos de outras fontes, preservando a origem de cada tradução.
- O publicador declara amostra limitada e não mundial. Não há contagem de partidas suficiente para calcular intervalos de confiança.
- `pickRate` vem em porcentagem; `pickRateChange` em pontos percentuais. O denominador da popularidade de cartas não é definido com precisão no arquivo. Não comparar numericamente com outra fonte antes de verificar esse denominador.
- O site informa patch `26.21`; os dados Blitz já coletados informam `16.21`. Guardar ambas as versões como recebidas e verificar equivalência antes de comparar. A coincidência do sufixo não é comprovação.

## O que já está pronto para reutilizar

`data/sources/arammayhem/current.json` aponta para o snapshot original. Cada snapshot contém índice, licença, atribuição, metadados, arquivos oficiais e manifesto com URLs, timestamps de coleta e SHA-256.

`data/derived/arammayhem/current.json` aponta para os derivados offline:

- `catalog.json`: dicionários por ID e metadados de cada dataset, preservados separadamente.
- `combo-index.json`: busca de IDs de combos por campeão e por carta.
- `popularity-history.json`: séries por entidade, com patch, data e indicação de data estimada.
- `audit.json`: cobertura, referências ausentes, idiomas e validação dos IDs entre JSON/CSV.
- `provenance.json`: origem, licença, transformações e regras de interpretação.

Os IDs de cartas são próprios do site. Não são IDs numéricos da Riot. Os índices mantêm esse namespace; o mapeamento com Blitz/OP.GG deve ser explícito, revisável e admitir correspondências desconhecidas.

## Como usar no recomendador futuro

1. Usar o catálogo como uma fonte de identificação e a série como **popularidade**, exibida separadamente de força e desempenho.
2. Recuperar os combos do campeão e das cartas já escolhidas como **candidatos a sinergia**. Abrir a explicação original, identificar requisitos, alternativas, itens necessários e possíveis conflitos.
3. Transformar apenas os candidatos revisados em regras estruturadas: campeão/mecânica compatível, cartas obrigatórias, cartas alternativas, itens, benefício, conflito, origem e patch verificado. Uma sugestão editorial pode aparecer identificada mesmo antes de haver estatística.
4. Cruzar cada candidato com tiers Blitz/OP.GG e outras evidências mantendo dimensões e fontes distintas. Discordância gera investigação; não uma média de letras.
5. Quando faltar combo, mostrar a evidência individual disponível e indicar que a sinergia é desconhecida. Isso mantém todos os campeões cobertos sem inventar relações.
6. Na validação com partidas nossas, registrar opções oferecidas, escolha, campeão, cartas/itens anteriores e resultado. Dados agregados de popularidade não substituem esse contexto.

O ganho imediato é grande para organização, busca, tendências e descoberta de sinergias. É insuficiente sozinho para recomendar a melhor carta entre três opções ou ajustar a build conforme as cartas obtidas.

## Complemento público via MCP

Análise aprofundada posterior, com 27 respostas adicionais, cobertura completa dos tiers de campeões e problemas observados: [análise do complemento](arammayhem-complement.md).

A [documentação oficial](https://arammayhem.com/use-with-ai/) oferece endpoint público somente leitura `https://arammayhem.com/mcp`. A sondagem inicial guardou a descoberta de ferramentas e dois exemplos de Teemo, sem limitar a cobertura pretendida do produto. A [coleta completa posterior](arammayhem-mcp-full.md) foi concluída: 647 respostas, 173 campeões, 282 cartas e explicações dos 666 combos, preservadas em snapshot próprio.

`get_top_combos` inclui descrição e tier editorial; `get_champion_build` inclui builds de itens, ordens de habilidades, popularidade e taxa de vitória. Esses complementos já foram coletados para todos os campeões. Nenhuma integração de IA ou configuração de aplicativo foi instalada.

As respostas de combo incluem patch/data no nível da resposta; isso não prova que cada explicação foi retestada nesse patch. Também não oferecem estatística de desempenho da combinação. A licença dos downloads não foi automaticamente estendida a todo o conteúdo do MCP; as amostras ficam como evidência de pesquisa separada.

## Atualização e verificação

Na raiz do projeto, com Python 3:

```powershell
python tools/data/sync_arammayhem.py
python tools/data/sync_arammayhem.py --verify
python tools/data/prepare_arammayhem.py
```

O primeiro comando usa rede e baixa todos os arquivos declarados pelo índice. Uma release nova cria outro snapshot; snapshots anteriores são preservados. Se o índice não mudou, verifica e reutiliza os arquivos. Não há agendamento automático. Os outros comandos são offline e usam somente a biblioteca padrão do Python.

A verificação confere hashes, presença dos datasets e contagem de linhas. A preparação confere também duplicidade, igualdade dos IDs entre JSON/CSV e intervalo de popularidade. Referências de combo fora do catálogo são registradas como lacunas da fonte, sem descarte silencioso. Os derivados são reproduzíveis a partir do snapshot.

## Licença e atribuição

Os datasets oficiais são publicados sob **CC BY 4.0**, com crédito **Data: [arammayhem.com](https://arammayhem.com/data/)** e link para a [licença](https://creativecommons.org/licenses/by/4.0/). O texto da declaração foi salvo em `LICENSE.source.json` e cada snapshot tem `ATTRIBUTION.md`. Os derivados identificam as transformações. Isso não licencia automaticamente imagens, descrições de terceiros ou outros dados já coletados no projeto.
