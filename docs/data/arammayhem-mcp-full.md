# Coleta completa do complemento MCP

Escopo solicitado: complementar os downloads do arammayhem.com com todos os dados identificáveis nas ferramentas públicas de leitura, sem IA, conta ou alteração de configuração de aplicativos.

## Resultado verificado em 30/10/2026

Snapshot permanente `research/arammayhem-mcp/snapshots/442810ae5f2a0d76e680/`, selecionado por `research/arammayhem-mcp/current.json`.

- **647 respostas verificadas**, nenhuma indisponível e nenhum truncamento.
- **173 campeões** com builds; **2.076 opções** de itens entre início, botas, núcleo e itens posteriores.
- **666 combos com texto e tier editorial**, correspondendo exatamente aos 666 links dos downloads. Uma explicação contém apenas `Nothing.` e foi marcada como fraca.
- **282 cartas** detalhadas: **217 marcadas como ativas** e **65 como retiradas** pelo MCP. Três descrições contêm variáveis não resolvidas: Dropkick, Infernal Conduit e Stackosaurus Rex.
- **519 prioridades de habilidades** e **1.557 sequências**. Destas, 1.548 têm 15 escolhas e nove têm 17. A faixa de níveis não é inferida nem preenchida.
- **173 campeões** na paginação completa de tiers e **12 resumos de patch**, de 26.10 a 26.21.

Há **13 cartas marcadas como ativas no MCP e ausentes do download atual de popularidade**, todas sem popularidade informada nessa resposta: Endless Decimation, Forged By The Master, Hellbent, Nature is Healing, Overextender, Shark Bait, Shark Tempest, Snowblast, Spirit Bomb, Squishy Slappy Grab, Surge Field, Tooth Fairy e Yowch, My Coins! Isso é uma diferença entre os recursos da fonte, não confirmação independente de disponibilidade no cliente do jogo.

O relatório completo e as listas de qualidade estão em `coverage.json` no snapshot. Os originais são preservados sem alterações, com origem, parâmetros, horário e SHA-256.

## Universo e consultas

Para o release `website:20261029_135745:fbaed7ce8a42`, patch publicado `26.21`, o plano tem **647 consultas de dados**:

| Ferramenta | Consultas | Escopo |
| --- | ---: | --- |
| `get_champion_build` | 173 | Builds e ordens/caminhos de habilidades de cada campeão |
| `get_top_combos` | 173 | Combos por campeão, pedindo o limite de 30 |
| `get_augment` | 282 | União dos IDs dos catálogos atuais, dos históricos e dos combos |
| `get_tier_list` | 6 | Paginação dos 173 campeões, sem duplicações |
| `get_patch_notes` | 12 | Patch atual e 11 anteriores presentes no índice oficial |
| `get_site_links` | 1 | Referências canônicas disponíveis |

A descoberta de ferramentas é guardada à parte. Não enumeramos todas as buscas textuais possíveis de `search`: os catálogos e históricos definem um universo verificável. “Completa” significa cobertura desse universo e das respostas que o endpoint publica, não acesso a dados internos não expostos.

Nos downloads, o máximo de combos por campeão é 23, abaixo do limite de 30 do MCP. Ainda assim, o auditor compara os links efetivamente recebidos aos **666 links de combos** e detecta truncamento antes de promover o snapshot.

## Dados preservados e integrados

- Nomes, descrições, disponibilidade e tiers/ranks globais de cartas, mantendo o namespace e a origem.
- Texto explicativo e tier editorial de cada combo correspondente ao download. A lista de membros continua com semântica não especificada: não vira automaticamente um conjunto de requisitos obrigatórios.
- Opções de itens por grupo, suas porcentagens publicadas e ordem das opções. O endpoint retorna até três alternativas por grupo e não condiciona a build às cartas escolhidas.
- Prioridades de habilidades e sequências exatamente como fornecidas, com suas estatísticas e quantidade de escolhas. Não preenchemos níveis ausentes nem inferimos a alocação inicial. Não inventamos contagem de partidas quando ela não vem no retorno.
- Lista de campeões associados a uma carta como evidência separada. A posição nessa lista não é convertida em força, sinergia ou win rate.
- Notas históricas, com patch e data próprios, identificadas como resumos de terceiros.
- Requisição, parâmetros, horário, resposta original e SHA-256 de cada chamada.

Os dados já extraídos anteriormente do HTML são preservados com marcação de pesquisa anterior, cobertura parcial e patch desconhecido, sem serem reapresentados como uma nova coleta. O snapshot MCP completo substitui as sondagens MCP na seleção ativa, evitando duplicar exemplos antigos como evidência nova.

## Persistência e publicação

1. A aquisição escreve em uma área isolada `data/intake/` e mantém checkpoint verificável para retomada.
2. A auditoria confere contagens de chamadas, IDs, paginação, links de combos, versões e hashes. Indisponibilidade real é registrada; erros ou truncamento impedem a promoção.
3. `promote` copia as respostas para um snapshot próprio em `research/arammayhem-mcp/snapshots/` e publica o ponteiro `current.json`. As sondagens e snapshots anteriores são preservados.
4. `pipeline.py build` compila a base local e só troca a versão ativa após validação.

Portanto, o uso futuro depende das cópias locais verificadas, não da expiração de um cache no servidor. Ler, analisar e usar os dados salvos não exige novas chamadas.

## Comandos

Coleta inicial usada nesta etapa:

```powershell
python tools/data/pipeline.py fetch --sources arammayhem --workspace C:/Projects/lol-overlay/data/intake/arammayhem-mcp-full-20261030
```

Para retomar uma aquisição interrompida, usar o mesmo comando com `--resume`. Uma rodada nova usa outro diretório. O coletor respeita intervalo de 1,25 s entre chamadas, trata falhas transitórias com espera e verifica o release ao terminar. O limite publicado é 60 requisições/minuto/IP; outros usuários da mesma conexão também podem consumir esse limite.

Auditar, promover e publicar:

```powershell
python tools/data/complete_mcp.py audit --workspace C:/Projects/lol-overlay/data/intake/arammayhem-mcp-full-20261030
python tools/data/complete_mcp.py promote --workspace C:/Projects/lol-overlay/data/intake/arammayhem-mcp-full-20261030
python tools/data/pipeline.py build
```

O relatório `coverage.json` do snapshot contém resultados efetivos: quantos campeões tinham builds, detalhes de cartas disponíveis, descrições vazias/fracas, notas disponíveis e eventuais lacunas. O plano de consultas não substitui essa verificação de respostas.

## Limites que a coleta não resolve

Combos continuam editoriais, sem desempenho medido da combinação. Um patch na resposta não comprova que cada interação foi retestada. Cartas retiradas, placeholders de efeito e explicações fracas permanecem identificados como problemas da fonte; não são corrigidos por adivinhação.

A coleta é em inglês, complementada pelos catálogos PT-BR existentes. Não houve tradução automática por IA. A licença CC BY dos downloads não é automaticamente estendida a todo o MCP; o canal continua identificado separadamente como pesquisa com atribuição.
