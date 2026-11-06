# BEES e combos — auditoria do patch 21, 30/10/2026

## arammayhem.com: inspeção ao vivo no navegador

O usuário apontou interesse nos combos dentro de Builds. Inspecionadas as páginas /build/, /build/teemo/, /augments/bees/ e /combo/teemo-mystic-punch-927/ no Chrome aberto. Overwolf não foi usado.

Na build de Teemo:

- São publicadas 18 cartas: seis prata, seis ouro e seis prismáticas. A página declara que algumas recomendações estão faltando.
- A ordem visual privilegia taxa de aparição nesse recorte: Shrink Engine aparece antes de BEES, embora BEES seja #1 entre ouros e Shrink Engine #6. Portanto a primeira carta exibida não é necessariamente a melhor avaliada.
- Há três combos, com cartas, itens e explicações. Isso atende parte do objetivo de recomendar um caminho de build, além da carta isolada.
- No exemplo Mystic Punch + Dual Wield/Runaan, o site identifica a avaliação S como editorial, sem métrica de vitória. Origem: editorial do site. O patch do combo e a data de atualização não estão registrados.
- A página BEES também identifica o guia de mecânicas como sugestão editorial, sem garantia de interações testadas.

Conclusão de produto: aproveitar o formato de explicação/requisitos dos combos e a separação de origem, mas registrar internamente confirmação mecânica, patch e teste. O catálogo de recomendações publicado não é exaustivo. Não interpretar ausência na página como carta ruim ou indisponível.

## BEES: identidade e snapshots

ID numérico3086, nome BEES!!!, ouro. Dados de Blitz/OP.GG/ARAMKit coletados em30/10, arammayhem.com publicado em29/10. Identificadores de patch16.21/26.21 usados pelas fontes. As páginas específicas de ARAMGG e ARAMKit foram conferidas novamente por HTTP público em30/10.

| Fonte | Avaliação | Popularidade reportada | Desempenho reportado |
| --- | --- | --- | --- |
| arammayhem.com | S+, #1 geral | 72,96%, #1 | Não publicado nesse dataset reutilizável/página |
| ARAMGG | T1, primeira carta na página geral | 72,64% | 70,71% de win rate |
| ARAMKit | A, #30 geral; #11 entre ouros pela ordem publicada | 9,41%, #1 entre cartas | 51,53% de win rate |
| Blitz | S geral | Não recuperada nesse endpoint | Sem WR de carta nesse endpoint |
| METAsrc | S+ geral | Não recuperada nessa inspeção | Não recuperado nessa inspeção |
| League of Graphs | A para mago, B suporte, C tanque/lutador/assassino/atirador | Não publicada nessa tela | Não publicado nessa tela |

Os percentuais de popularidade não têm denominador equivalente confirmado. Não dizer que72,96% e9,41% são a mesma probabilidade ou medir a diferença como queda de interesse. Em Teemo, as medidas por campeão ficam próximas: arammayhem.com19,34%, ARAMKit18,70%, ARAMGG19,23% no snapshot salvo.

A página arammayhem.com mantém histórico de BEES sempre #1/S+ nas três datas27–29/10; a popularidade reportada evolui71,64%,72,64%,72,96%. Isso confirma persistência do sinal publicado nesses dias, não vitória causal.

## Avaliação por campeão

Nos171 campeões com registro de BEES:

- Blitz: S89, A37, B32, C11, D2. Dois campeões do catálogo sem registro.
- OP.GG: S79, A75, B16, C1. Dois sem registro. O endpoint não publica WR; performance é outra escala.
- ARAMKit: S37, A68, B63, C3. É rank1 dentro do campeão em8 casos, usando a classificação geral de cartas do campeão.

O OP.GG registra popularidade e performance por campeão, mas não oferece número global neste levantamento. As posições em relação a todas as raridades não equivalem a posição entre ouros. Valores de performance não foram convertidos em WR.

### Exemplos ARAMKit

| Campeão | WR com BEES | WR geral do campeão | Diferença descritiva |
| --- | ---: | ---: | ---: |
| Kai'Sa | 60,38% | 49,56% | +10,82pp |
| Tahm Kench | 62,27% | 54,23% | +8,04pp |
| Gwen | 64,20% | 57,03% | +7,17pp |
| Viego | 59,56% | 52,78% | +6,78pp |
| Teemo | 60,79% | 54,71% | +6,08pp |
| Ekko | 61,47% | 55,48% | +5,99pp |
| Master Yi | 58,64% | 55,28% | +3,36pp |
| Ashe | 44,20% | 43,87% | +0,33pp |
| Brand | 48,36% | 48,58% | -0,22pp |

São diferenças observacionais: seleção de jogadores/cartas, combinações, estágio, itens e composição não estão controlados. Não representam aumento causal de chance de vitória.

## Estágio no ARAMKit

| Escolha | WR BEES | Tier | Rank dentro do estágio |
| --- | ---: | --- | ---: |
| 1 | 52,26% | A | 23 |
| 2 | 51,41% | A | 42 |
| 3 | 51,18% | A | 34 |
| 4 | 50,50% | A | 48 |

Esse agregado não controla quais campeões/jogadores chegaram à escolha ou escolhem BEES em cada estágio. Não é evidência causal suficiente para determinar quanto a carta perde de valor ao longo do jogo.

## Combinações com BEES

O arquivo ARAMKit de top10 pares por campeão inclui110 registros com BEES em41 campeões; seleção truncada, não matriz completa de interações.

Exemplos reportados:

- Teemo, BEES + Ethereal Weapon: WR65,46%, sampleCount83.696.
- Teemo, BEES + Infinite Recursion: WR64,28%, sampleCount32.188.
- Kai'Sa, BEES + Back To Basics: WR65,82%, sampleCount40.432.
- Kai'Sa, BEES + Ethereal Weapon: WR63,93%, sampleCount79.743.

As amostras são quantidades declaradas pelo fornecedor. Par bom não prova ganho de interação além do valor individual de cada carta. Não usar WR do par menos WR de BEES como estimativa causal de sinergia.

## Divergência que precisa de auditoria

ARAMGG informa70,71% geral; ARAMKit51,53%. É uma diferença grande e sem explicação estabelecida. Não fazer média entre elas. Recorte, janela, origem, unidade estatística, filtros ou erro de métrica continuam hipóteses.

Também verificamos os111 campeões nos quais BEES aparece nas20 cartas publicadas do ARAMGG: WR varia45,19%–65,80%, média não ponderada51,97%. Essa cobertura é parcial e não permite refutar matematicamente o70,71% global sem os campeões restantes e seus pesos, mas reforça a necessidade de esclarecer como a estatística global foi construída.

Já no ARAMKit, sampleCount global20.822.744 é exatamente a soma das amostras dos171 campeões. A média ponderada dessas WR reproduz51,53294%, compatível com51,53% global por arredondamento. Isso valida a leitura e a coerência interna desse agregado; não comprova representatividade, origem real das partidas ou correção do pipeline.

Conclusão: popularidade de BEES tem forte apoio em várias fontes. Boa/alta força geral é apoiada por vários tiers publicados; o consenso sobre ser a melhor carta universal de desempenho não está estabelecido. Os dados ARAMKit apoiam fortemente alguns campeões e combinações, enquanto sua classificação agregada é menos extrema. Esse caso deve ser uma validação prioritária das fontes antes de escolher o provedor principal.

## Artefatos

- bees-analysis.json: resultados completos e observações por campeão.
- analyze_bees.py: extração reproduzível dos snapshots.
- external-snapshots/aramgg-bees.html e .text.txt: página específica atual.
- external-snapshots/aramkit-bees.html e .text.txt: página específica atual.
- Dados anteriores por campeão e combinações permanecem preservados em champion-snapshots/, external-champions/ e aramkit-data/.

URLs públicas relevantes: https://arammayhem.com/build/teemo/ ; https://arammayhem.com/augments/bees/ ; https://arammayhem.com/combo/teemo-mystic-punch-927/ ; https://aramgg.com/en/augments/3086 ; https://aramkit.com/en-US/augments/bees .
