# Comparação externa de Mayhem — 30/10/2026

## Restrição permanente

Overwolf não será usado em nenhuma hipótese na solução. A pesquisa abaixo utiliza somente HTTP público, snapshots locais e análise de conteúdo inerte. Não implementa o overlay.

## Cobertura efetivamente coletada

| Fonte | Cobertura coletada | Interseção com ambos os baselines |
| --- | --- | --- |
| ARAMKit | 173 campeões, 22.618 avaliações de cartas, catálogo 235 cartas | 20.985 pares campeão/carta |
| ARAMGG | 173 páginas de campeão, somente as 20 cartas publicadas inicialmente em cada HTML | 3.460 pares |
| arammayhem.com | 173 páginas de campeão, 18 recomendações por página (6 por raridade) | 3.105 pares; 9 nomes ficaram sem correspondência segura |

Todas as 346 páginas ARAMGG/arammayhem.com foram obtidas; uma consulta Sejuani expirou e foi obtida com sucesso em uma repetição. O manifest inicial preserva o timeout; o arquivo meta individual registra o sucesso posterior.

League of Graphs e METAsrc retornaram HTTP403 à coleta direta. Suas páginas apareceram na ferramenta de busca, mas não obtivemos uma base estruturada consistente para esta comparação. Não houve tentativa de contornar o bloqueio. Não contar essas fontes como validadas.

## Como foi feita a comparação

Baselines: snapshots anteriores de Blitz e OP.GG, contendo ambos os tiers e os campos popular/performance do OP.GG. Usamos a mesma interseção tripla por fonte externa e IDs oficiais. Nomes ingleses ARAMGG foram conferidos contra o catálogo do Blitz quando disponíveis; arammayhem.com exige correspondência única de nome normalizado, com alias explícito apenas para prefixo Quest:. Não foi usada aproximação fuzzy para Double Defense ou Rabble Rousing.

Para as letras, S=0,A=1,B=2,C=3,D=4,E=5. Os modificadores + e - do arammayhem.com foram removidos para uma comparação grosseira, não uma alegação de escalas idênticas. T1/T2 do ARAMGG não foram convertidos em S/A: 3.424 das 3.460 observações são T1 e não temos equivalência estabelecida.

Também medimos similaridade da ordem das cartas com Spearman, calculado dentro de cada campeão e depois promediado, dando o mesmo peso a cada campeão. O resultado vai de -1 a 1: 1 significa ordenação idêntica, 0 ausência de relação monotônica e -1 ordem inversa. Ties recebem midranks. Para o ranking do arammayhem.com, que é específico por raridade, as correlações são primeiro calculadas dentro da raridade, depois promediadas por campeão.

Uma verificação adicional compara somente pares de cartas da mesma raridade em que Blitz e OP.GG ordenam as cartas em direções estritamente opostas. Isso evita misturar raridades e não depende de a fonte externa usar as mesmas letras.

Os sites utilizam identificadores de patch 16.21/26.21, mas têm datas, amostras e recortes distintos. O próprio endpoint OP.GG não traz patch. Resultados descrevem estes snapshots, não uma avaliação controlada da acurácia dos produtos. Similaridade não prova independência, cópia, causalidade ou melhor desempenho no jogo.

## Resultado: ARAMKit se aproxima mais do Blitz na avaliação de força

Em 20.985 pares compartilhados:

- Mesma letra do Blitz: 10.854 (51,7%). Mesma letra do OP.GG: 6.539 (31,2%).
- Distância média em letras: 0,520 do Blitz, 0,953 do OP.GG.
- Nos casos em que os baselines discordam: 9.312 ficam mais próximos do Blitz, 2.919 do OP.GG e 1.710 empatam.
- Descartando os empates, 76,1% ficam mais próximos do Blitz.
- Agregando por campeão, Blitz vence em 171 campeões, OP.GG em 1, empate em 1.
- Ordem publicada ARAMKit versus tier Blitz: Spearman médio 0,878; versus tier OP.GG: 0,580.
- Nos 44.128 pares com ordem invertida nos baselines, o ranking ARAMKit escolhe o mesmo lado do Blitz 36.106 vezes (81,8%) e do OP.GG 8.022 vezes.

O resultado se mantém com mínimo de 1.000 partidas por observação: 20.465 pares compartilhados; 8.946 mais próximos do Blitz, 2.874 do OP.GG, 1.665 empatados. Não é consequência apenas das amostras muito pequenas.

## Os campos do OP.GG não se comportam todos da mesma forma

| Comparação dentro do campeão | Spearman médio |
| --- | ---: |
| Ranking ARAMKit × tier Blitz | 0,878 |
| Ranking ARAMKit × tier OP.GG | 0,580 |
| Win rate ARAMKit × performance OP.GG | 0,877 |
| Popularidade ARAMKit × popular OP.GG | 0,953 |
| Popularidade ARAMKit × tier OP.GG | 0,908 |
| Win rate ARAMKit × tier OP.GG | 0,501 |

Interpretação: há forte alinhamento do campo popular OP.GG com popularidade externa e do campo performance com desempenho externo. O tier OP.GG acompanha popularidade mais fortemente do que o desempenho nesta comparação. Isso sugere uma diferença importante de significado/prioridade entre tier e performance; não recupera nem prova a fórmula do tier no servidor. Não chamar performance de win rate: os valores numéricos podem ultrapassar 100.

## ARAMGG tem dois comportamentos conforme a métrica

Nas 20 cartas por campeão disponíveis no HTML:

| Métrica ARAMGG | Relação com Blitz/OP.GG |
| --- | --- |
| Ordem publicada na tabela | Mais próxima do tier OP.GG (rho0,570) do que tier Blitz (0,169) |
| Popularidade | Correlação com popular OP.GG 0,787 |
| Win rate | Mais próxima do tier Blitz (0,621) do que tier OP.GG (0,007) |
| Win rate | Correlação com performance OP.GG 0,855 |

Entre 821 pares da mesma raridade em que os tiers dos baselines se contradizem, a ordem publicada ARAMGG acompanha OP.GG em 656 (79,9%); usando win rate em vez da ordem publicada, acompanha Blitz em 782 (95,2%). Não extrapolar esses percentuais às cartas fora das 20 publicadas.

A página declara win rates obtidas por partidas de clientes chineses enviadas anonimamente, com mínimo de 255 jogos para cartas por campeão e 151 para trios. Isso é declaração do fornecedor, não auditoria nossa. A API oficial do ARAMGG documenta chave para dados protegidos; não foi acessada nem contornada. Apenas config/docs públicas e HTML público foram coletados.

## arammayhem.com fica mais equilibrado

Nos 3.105 pares compartilhados das recomendações publicadas:

- Distância média de letra: Blitz0,598 versus OP.GG0,614.
- Onde os baselines discordam: 644 mais próximos do Blitz, 576 do OP.GG, 34 empates. Descartando empate: 52,8% Blitz e 47,2% OP.GG.
- Por campeão: 81 favorecem Blitz, 66 OP.GG, 26 empatam.
- Entre 415 pares da mesma raridade de ordem invertida nos baselines, o ranking próprio acompanha Blitz256 vezes e OP.GG159.

Portanto há uma inclinação moderada para Blitz na ordem publicada e apenas uma diferença pequena nas letras. Não é uma confirmação tão forte quanto ARAMKit. A seleção das 6 cartas por raridade limita a interpretação.

As popularidades ARAMGG e arammayhem.com são extremamente parecidas: 2.533 observações compartilhadas, Spearman médio por campeão0,995 e diferença absoluta média0,100 pontos percentuais. Isso é compatível com populações/fontes semelhantes ou snapshots próximos, mas não estabelece compartilhamento de banco. Não contar automaticamente esses dois sites como votos independentes.

## Exemplo concreto: Master Yi

| Carta | Blitz | OP.GG | ARAMKit |
| --- | --- | --- | --- |
| Arma Etérea | B | S | B |
| Aprimorar Gume do Infinito | A | S | B |
| Tufão | S | S | A |

Esses exemplos ilustram a comparação ampla; o estudo não limita o produto a Master Yi.

## Utilidade para a implementação futura

1. Manter força/avaliação, popularidade e encaixe da combinação como informações separadas.
2. ARAMKit é um candidato tecnicamente forte para a referência de força e contexto: 1.730 combinações de duas cartas publicadas, top10 por campeão, com amostras, além de recortes por estágio. Esses pares não são uma matriz completa e não demonstram sinergia causal.
3. Foi guardado exemplo de builds/itens condicionados por carta no ARAMKit (arquivo adicional do Yi, 6,8MB). Ainda não é uma coleta completa para os 173 campeões.
4. Usar diferenças entre fontes para priorizar validação de mecânicas, sem produzir um tier pela média cega dos sites.
5. Independência, metodologia e direitos de redistribuição continuam não verificados. Nenhuma escolha de fornecedor foi fechada; nenhum overlay foi implementado.

## Artefatos reproduzíveis

- `external-comparison-summary.json`: resultados detalhados por fonte/métrica.
- `external-sensitivity.json`: verificação com amostras mínimas e similaridade entre popularidades.
- `external-pages-normalized.json`: 6.565 observações HTML normalizadas.
- `external-pages-unmatched.json`: 9 nomes sem correspondência segura.
- `external-champions/`: 346 HTMLs e seus metadados/hash/data.
- `external-snapshots/`: páginas gerais, config, documentação e downloads.
- `aramkit-data/README.md`: origem, schema, limitações e URLs do ARAMKit.
- `aramkit-data/normalized.json`: 22.618 observações completas.
- `aramkit-data/combinations.json`: 1.730 pares publicados.
- Scripts: `collect_external_sources.py`, `collect_external_champions.py`, `normalize_external_pages.py`, `compare_external_sources.py`.
