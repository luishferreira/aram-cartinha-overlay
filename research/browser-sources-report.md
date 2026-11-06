# METAsrc e League of Graphs via navegador — 30/10/2026

## Coleta

O usuário autorizou controlar as duas abas abertas no Chrome. Foram utilizados somente APIs documentadas do navegador para ler o DOM e navegar por links públicos observados. Não houve acesso a cookies, credenciais, estado interno de autenticação ou contorno de CAPTCHA. Os 403 anteriores pertenciam ao cliente HTTP de coleta; as páginas abriram normalmente no navegador do usuário.

METAsrc foi restaurado à página original https://www.metasrc.com/lol/mayhem ao terminar. League of Graphs permaneceu no endereço original /aram-mayhem/augments#support. Nenhuma conta/configuração foi alterada. Overwolf continua excluído do projeto.

Dados extraídos:

- League of Graphs: 228 IDs distintos, 1.338 classificações por classe (assassin221, fighter223, mage225, marksman219, support223, tank227); tiers S,A,B,C,D,F.
- League of Graphs: 88 flags de carta/classe marcadas Situational. O HTML não forneceu uma justificativa adicional para essas flags.
- METAsrc global: 230 cartas, patch26.21, All Regions/All Ranks, todos os estágios conforme texto da página; tiers S+,S,A,B,C,D.
- METAsrc por campeão: página Master Yi como inspeção diagnóstica, 147 cartas completas no elemento DOM application/json #ArenaWidget_row_data, explicitamente referenciado pelo controlador da tabela. Não é uma coleta dos 173 campeões.

Os IDs numéricos foram obtidos dos atributos DOM tooltip-var do League of Graphs, data-tooltip-select do METAsrc global e key do JSON da tabela METAsrc. A tabela renderiza progressivamente apenas parte das linhas; não confundir as 20/40 linhas iniciais com a base completa de 147 cartas que a página declara para Yi.

A página METAsrc usa o rótulo Champions Processed no contador geral. Não tratá-lo como partidas únicas nem como tamanho de amostra por carta. A página de Yi declara 1.252.036 jogos do campeão, mas não foi obtido tamanho de amostra por carta.

## METAsrc global: mais próximo de popularidade nesta comparação

Em 221 IDs compartilhados entre METAsrc, Blitz geral e ARAMKit geral, dobrando S+ em S apenas para uma escala grosseira:

| Comparação de ordem (Spearman) | Correlação |
| --- | ---: |
| Tier METAsrc × tier global Blitz | 0,809 |
| Tier METAsrc × popularidade global ARAMKit | 0,897 |
| Tier METAsrc × ranking global ARAMKit | 0,295 |
| Tier METAsrc × win rate global ARAMKit | 0,283 |

Isso mostra que a classificação global do METAsrc se aproxima mais da popularidade do que do desempenho medido pelo ARAMKit neste snapshot. Não demonstra a fórmula utilizada pelo servidor. Também revela que a associação observada anteriormente entre Blitz por campeão e desempenho não deve ser estendida automaticamente à sua tier list geral.

Não comparamos diretamente tiers globais METAsrc com tiers por campeão OP.GG, porque os recortes não são equivalentes.

## METAsrc por campeão: evidência inicial mais próxima do OP.GG

Na inspeção de Yi, há 136 cartas compartilhadas com os dois baselines:

| Comparação de ordem (Spearman) | Correlação |
| --- | ---: |
| Tier METAsrc Yi × tier OP.GG Yi | 0,912 |
| Tier METAsrc Yi × popular OP.GG Yi | 0,930 |
| Tier METAsrc Yi × tier Blitz Yi | 0,715 |
| Tier METAsrc Yi × performance OP.GG Yi | 0,655 |

Quando os baselines discordam, a letra METAsrc fica mais próxima do OP.GG45 vezes, do Blitz37, com12 empates. Resultado condicionado a um único campeão; não extrapolar a todos os campeões. Os modificadores S+ foram dobrados em S para a comparação, preservados nos arquivos raw.

| Carta | Blitz Yi | OP.GG Yi | ARAMKit Yi (coleta anterior) | METAsrc Yi |
| --- | --- | --- | --- | --- |
| Arma Etérea | B | S | B | S |
| Aprimorar Gume do Infinito | A | S | B | S+ |
| Tufão | S | S | A | S |

## League of Graphs: outro nível de contexto

As avaliações são por classe, sem filtro por campeão observado nessa tela. Não foi obtido banco por campeão, nem pick rate/win rate/amostra por carta. A contagem de partidas no rodapé lateral não está comprovada como denominador específico dessa tier list.

Por isso não atribuímos um voto de concordância direta com Blitz/OP.GG por campeão. Isso confundiria classe com campeão e penalizaria interações específicas do kit. A escala F também não foi equiparada automaticamente ao E do OP.GG.

A utilidade principal é uma referência adicional de adequação à classe e de cartas situacionais, mantendo a origem. Exemplo: Tufão é F para Support, enquanto é S para Yi em Blitz/OP.GG/METAsrc. Isso não é contradição: são contextos diferentes. Nem a classe nem o rótulo Situational demonstram uma sinergia com cartas anteriores.

## Conclusão para a base

- METAsrc adiciona uma classificação que neste global e no exemplo por campeão acompanha bem popularidade. Não é confirmação independente de força; independência e método não foram auditados.
- League of Graphs adiciona a dimensão classe/situacional. É conteúdo contextual complementar, sem evidência suficiente nesta coleta para validação estatística de força.
- Continuar separando âmbito global/campeão/classe, força, popularidade, estágio e encaixe da combinação.
- Uma coleta futura de todos os campeões do METAsrc permitiria testar se a tendência de Yi é geral; não foi executada nesta inspeção do navegador.

## Arquivos e integridade

- browser-metasrc-global.json
- browser-metasrc-masteryi.json
- browser-leagueofgraphs-classes.json
- browser-leagueofgraphs-situational.json
- browser-source-comparison.json e compare_browser_sources.py

Os três arquivos principais foram conferidos contra fingerprints FNV1a32 calculados sobre os IDs/tiers obtidos no navegador: LeagueOfGraphs324c909f; METAsrc global a9e283b5; METAsrc Yi79094b20. Isso é uma verificação de transferência dos dados, não assinatura criptográfica do fornecedor.
