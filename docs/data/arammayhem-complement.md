# Análise do complemento público MCP

Este documento descreve a sondagem inicial. A etapa posterior de [coleta completa do MCP](arammayhem-mcp-full.md) amplia a cobertura para todos os campeões e IDs identificados, preservando essas evidências anteriores.

Investigação em 30/10/2026. Endpoint: `https://arammayhem.com/mcp`. Nenhuma integração foi instalada no aplicativo, e nenhum overlay foi implementado.

## Escopo e evidência

27 respostas foram guardadas em `research/arammayhem-mcp/complement-2026-10-30/`, com parâmetros, horário de coleta e SHA-256 em `manifest.json`. `analysis.json` contém as comparações offline. As duas sondagens anteriores de Teemo permanecem na pasta superior.

- Tier list completa: seis páginas, **173 campeões únicos**. Os 173 valores de popularidade coincidem com o download do mesmo release.
- Combos: oito campeões de perfis diferentes; mesma quantidade e mesmos links do download em todas as oito consultas, incluindo Ahri e Lulu sem resultados.
- Builds: cinco campeões; todos retornaram três opções por grupo, além das ordens de habilidades.
- Cartas: seis consultas, incluindo cartas do catálogo atual e IDs ausentes dele.
- Uma busca por mecânica e as notas do patch atual.

O recorte de exemplos verifica o formato e suas limitações, não limita a cobertura pretendida do projeto. Não é uma coleta completa das builds/cartas/explicações.

Documentação primária: [guia oficial](https://arammayhem.com/use-with-ai/) e [repositório oficial da conexão](https://github.com/arammayhem/arammayhem-mcp). O repositório contém uma ponte, não a base completa nem a lógica remota. A documentação informa que o MCP usa os mesmos dados publicados no site: não é uma fonte independente para confirmar o próprio site.

## Dados adicionais e utilidade

| Consulta | Adiciona ao download | Uso sugerido | Limitação |
| --- | --- | --- | --- |
| `get_augment` | Descrição, disponibilidade, tier/rank globais, campeões associados | Catálogo mecânico, terceiro parecer de força global, identificação de conteúdo retirado | Não recebe campeão/cartas anteriores; sem win rate nas seis respostas examinadas; critério dos campeões associados não explicado |
| `get_top_combos` | Texto explicativo e tier editorial por combinação | Descobrir interações, itens necessários, alternativas e condições de execução | Lista resumida, até 30 resultados, sem paginação; texto não é uma regra formal nem estatística |
| `get_champion_build` | Início, botas, núcleo e itens posteriores, com pick/win rate; ordens de habilidades | Build de referência e alternativas por campeão | Até três opções por grupo; não condiciona às cartas; não fornece contagem da amostra |
| `get_tier_list` | Tier e win rate dos campeões | Contexto do campeão, comparação descritiva entre fontes | Não é desempenho de uma carta nem do combo; método de tier não demonstrado |
| `search` | Busca em nomes, aliases e textos de efeitos | Descobrir cartas por mecânica, ajudar a mapear identificadores | Correspondência textual não comprova interação; limite de 30 |
| `get_patch_notes` | Mudanças de patch resumidas | Sinalizar regras e descrições que precisam de revisão | Até 15 entradas por seção; não substitui as notas completas/primárias |

## Exemplos que explicam o valor

**Master Yi / Mystic Punch:** a explicação associa redução de recarga, aceleração e sustentação de mana, citando Essence Reaver. Isso sugere um caminho de build com um requisito além da carta. O número de aceleração e a alegação de Q praticamente contínuo são afirmações da fonte, não resultados validados por nós. O texto serve para produzir uma hipótese revisável.

**Nautilus:** um combo lista apenas Courage of the Colossus, mas sua explicação recomenda também Cruelty, ausente de `augmentIds` dessa entrada. Logo, o campo de IDs sozinho perde uma relação importante. Outra entrada menciona Heartsteel no texto, embora não haja campo estruturado de itens no combo.

**Teemo:** o exemplo anterior menciona Runaan no texto do combo com Mystic Punch. Uma integração pode relacionar cartas e item, explicar a direção da build e evitar recomendar a carta isoladamente. Isso ainda exige revisar a interação e seus requisitos no patch.

**Xayah:** uma lista de 15 cartas recebe tier S, mas a descrição resume prioridades de atributos de forja. É um conceito de build; o retorno não identifica quais cartas são núcleo, alternativas ou apenas compatíveis.

**Lulu:** nenhum combo retornado, mas a build está disponível. Precisamos representar disponibilidade por tipo de evidência: falta de combo não é falta de dados sobre o campeão.

## Problemas concretos encontrados

1. **Conteúdo retirado ainda aparece em combos.** Cerberus e Dropkick retornam `availability: retired`, mas permanecem em listas editoriais. Ambos também retornam `sourceStatus: live`. Os campos não são intercambiáveis; preservar os valores e verificar seu significado. Não tratar `sourceStatus` como autorização de disponibilidade em jogo.
2. **Popularidade antiga pode sobreviver à retirada.** Clown College retorna `availability: retired`, tier/rank nulos e popularidade preenchida. A resposta leva a data atual, mas isso não demonstra que aquele valor seja popularidade corrente de uma carta selecionável.
3. **Ranking de força e de popularidade diferem.** Mystic Punch retorna rank 25 no MCP contra posição 27 por popularidade no download; Marksmage 85 contra 78. Não substituir um pelo outro, nem inventar a metodologia do rank MCP.
4. **Descrições podem conter variáveis sem resolução.** Dropkick inclui `@Calc_Execute_Threshold@`, `@Calc_Damage@` e outros tokens. Não extrair números que não existem nem exibir esse texto cru como explicação final.
5. **Qualidade editorial varia.** Há descrições explicativas, mas também uma com apenas `Nothing.`. Algumas têm caracteres mal codificados. Preservar o original; uma versão tratada deve registrar a transformação.
6. **Mesmo tier pode avaliar coisas distintas.** Tier global da carta, tier do campeão e tier editorial do combo têm alvos diferentes. O fato de todos usarem letras não os torna comparáveis.
7. **Não existe consulta de recomendação contextual no schema examinado.** Nenhuma ferramenta aceita as três cartas oferecidas, inventário, cartas anteriores, inimigos ou estado da partida. Esse raciocínio será responsabilidade nossa.

## Como incorporar sem perder a qualidade dos dados

Usar o MCP como **canal de coleta e enriquecimento**, com cache local por release/patch e proveniência. MCP é o protocolo de acesso; não há necessidade de um modelo de linguagem rodando em cada escolha durante a partida.

Separar os registros em três camadas:

1. **Observado na fonte:** campos e textos originais, alvo do tier, unidade, data, link, disponibilidade e escopo da amostra quando informado. MCP e download pertencem à mesma família de fonte e não contam como dois votos independentes.
2. **Interpretação nossa:** mecânicas e regras extraídas, cartas núcleo, alternativas, itens citados, estilo da build e conflitos. Cada relação precisa de estado `hipótese`, `revisada` ou `verificada em partida`, com patch e justificativa. Uma extração por IA pode propor relações; não deve confirmá-las automaticamente.
3. **Apresentação futura:** mostrar separadamente força por fonte, popularidade, desempenho observado e encaixe com o estado atual. Diferenciar `já ativa`, `depende de item/carta futura`, `alternativa de build`, `conflito` e `sem evidência`.

As builds agregadas podem fornecer um ponto de partida para todos os campeões com dados. As regras editoriais revisadas ajustam esse ponto de partida. Não interpretar a win rate agregada da build como win rate com determinada carta: a fonte não oferece esse recorte.

Win rate de uma build completa também não mede o efeito causal de comprá-la. Quem consegue completar os itens pode estar em uma partida diferente de quem não consegue; duração, adversários e escolhas anteriores podem influenciar o resultado. Não selecionar cegamente a maior porcentagem, especialmente sem contagem de partidas.

## Prioridades sugeridas

1. Expandir a coleta a todos os campeões e aos IDs de cartas da união download/combos, preservando vazios e retirados. A API é limitada a 60 requisições/minuto/IP; usar cache, ritmo moderado e retomada de erros.
2. Conferir truncamento. `get_top_combos` tem limite 30 sem offset; comparar sempre `total` com a quantidade recebida. Builds são intencionalmente resumidas e podem precisar do site para alternativas ausentes.
3. Estruturar primeiro relações explícitas nos textos, com revisão e rótulo de confiança. Não expandir uma lista de 15 cartas em todas as relações positivas possíveis.
4. Cruzar com os dados existentes de Blitz, OP.GG e ARAMKit, verificando versão, entidade e recorte antes. Usar dados condicionais de build de outras fontes quando de fato disponíveis; o MCP não os substitui.
5. Verificar interações prioritárias em jogo e registrar escolhas/resultados nossos para avaliar utilidade real do overlay.

A licença MIT do repositório cobre a ponte/documentação, não automaticamente os datasets ou todo o conteúdo retornado. As respostas ficam em pesquisa com atribuição; o escopo CC BY dos downloads permanece separado.

Para repetir a auditoria offline:

```powershell
python research/analyze_arammayhem_complement.py
```

Para repetir a coleta de sondagem, com rede e dependência `requests` já disponível:

```powershell
python research/probe_arammayhem_complement.py
```
