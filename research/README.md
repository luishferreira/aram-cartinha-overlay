# Pesquisa Mayhem — Blitz e OP.GG

Downloads oficiais arammayhem.com, auditoria de cobertura e plano de uso: [documentação dos dados](../docs/data/arammayhem.md). Originais versionados em `data/sources/arammayhem/`; índices derivados em `data/derived/arammayhem/`.

[MCP arammayhem completo](../docs/data/arammayhem-mcp-full.md): 647 respostas preservadas, builds dos 173 campeões, 282 detalhes de cartas, explicações dos 666 combos e notas dos 12 patches. A seleção ativa está em `research/arammayhem-mcp/current.json`; sondagens anteriores foram preservadas.

Atualização posterior: [API de desenvolvedor ARAMGG](../docs/data/aramgg-api.md) coletada para os 173 campeões, incluindo 21.031 registros de cartas e 527 trios. Substitui o limite do HTML no pipeline; mantém proveniência e dados históricos separados. As comparações antigas abaixo continuam descrevendo seus snapshots originais.

**Restrição de produto definida pelo usuário: não usar Overwolf em nenhuma hipótese.** Referências a Overwolf nas evidências descrevem apenas o aplicativo de terceiros inspecionado; não são opções para nossa arquitetura.

Coleta em 30/10/2026. Apenas ferramentas de pesquisa, snapshots de páginas públicas e inspeção estática dos apps locais; o overlay não foi implementado. Os aplicativos instalados não foram alterados.

## Resultado observado

- Catálogo local OP.GG inclui 254 entradas: 173 campeões principais e 81 variantes Jade_* de outro modo. A coleta excluiu essas variantes.
- 346 GETs de dados por campeão (173 por fonte), todos bem-sucedidos; ambas as fontes retornaram dados para todos os 173 campeões consultados.
- 21.843 pares campeão/carta em comum.
- Catálogo de cartas Blitz coletado: 249. OP.GG: 281. Todos os 249 IDs compartilhados também têm a mesma chave interna (`name` no Blitz e `key` no OP.GG).
- A tabela global de avaliações Blitz retorna 434 IDs únicos, mais que seu catálogo atual de 249 cartas. Não assumir que todos esses rankings representam cartas atualmente disponíveis; motivo da diferença ainda desconhecido.
- Blitz identifica patch 16.21 e data 2026-10-30 em todas as respostas por campeão. O catálogo OP.GG é 16.21, mas as respostas de estatísticas por campeão não informam patch; equivalência temporal não está comprovada.

## Comparação de tiers

Os números usam escalas diferentes:

| Fonte | Mapeamento |
| --- | --- |
| Blitz | 1=S, 2=A, 3=B, 4=C, 5=D |
| OP.GG | 0=S, 1=A, 2=B, 3=C, 4=D, 5=E |

Blitz: 1/S e 2/A observados na página do campeão; 3/B, 4/C, 5/D confirmados cruzando IDs 2087, 1006, 1027 no HTML geral com o JSON embutido. OP.GG: confirmado no componente do aplicativo, ver opgg-local.md.

Entre os 21.843 pares comparáveis, 7.349 têm a mesma letra, 9.490 diferem uma posição e 5.004 diferem duas ou mais posições. Isso mede discordância de classificações, não qualidade ou acurácia. Os métodos de tier e recortes das duas fontes não são conhecidos como equivalentes.

Exemplos coletados para Master Yi (usado para conferir os links fornecidos; não limita a cobertura do projeto):

| Carta | Blitz | OP.GG |
| --- | --- | --- |
| Arma Etérea | B | S |
| Aprimorar Gume do Infinito | A | S |
| Tufão | S | S |

## O que conseguimos coletar

Blitz entrega no HTML SvelteKit as respostas JSON de:

- `https://utils.iesdev.com/static/json/lol/mayham/16.21/augments_en_us`
- `https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/aram_mayhem_augments`
- `https://data.v2.iesdev.com/api/v1/query_objects/prod/lol/aram_mayhem_champion?champion_id=11`

A resposta por campeão contém `data.augments`, `data.items`, `data.tier`. Avaliações de cartas oferecem tier, sem a justificativa/metodologia do servidor. Catálogo inclui nomes, descrições, raridade, enabled e valores de efeitos. Coleta sem parâmetro champion_id retornou HTTP 400; portanto foi usado um GET por campeão.

OP.GG: rotas identificadas no app instalado e confirmadas por GET sem cookies/chave:

- `https://lol-api-champion.op.gg/api/meta/aram-augments?hl=pt_BR`
- `https://lol-api-champion.op.gg/api/contents/stats/champions/11/aram-augments`

Campos do segundo: `id`, `tier`, `performance`, `popular`. Não chamar performance de taxa de vitória: há valores maiores que 100 e a definição não foi estabelecida. O denominador de popular também permanece desconhecido; preservado como valor bruto.

O HTML OP.GG também fornece dados de hidratação, mas inclui entradas com defaults zerados. Para a comparação foi usada a resposta direta de estatísticas; não converter defaults da página em observações de desempenho.

## Bancos e pacotes locais

Blitz 3.0.17:

- `C:\Users\Keita\AppData\Local\Programs\Blitz\resources\app.asar`
- SHA256 `41ae887fb6e213722ae66e764c09fb2b6bc590800a32c0c4d587f98a0de4d579`
- `src/db.js` usa `Level` e caminho `app.getPath("userData")/appdb`: confirma LevelDB local.
- Pasta observada `C:\Users\Keita\AppData\Roaming\Blitz\appdb`.
- Não foi decodificado o conteúdo do LevelDB. Não está comprovado que esse banco armazene rankings completos. `src/getBaseURL.js` monta uma URL remota versionada; inspecionar o pacote instalado não garante conter o frontend completo e atualizado.
- REA inventário: parent `ev_4314b02fd2f79e25d059ab5cbb52e2af608215471179dfcdc7ccb858d995e8db`.
- REA fontes selecionadas db/getBaseURL/createWindow: parent `ev_ef83299ce2ea4831d9cf0dcd59bbc1049c2359743c24018e89b2ea1227372bef`. Cobertura parcial; análise estática não observa execução.

OP.GG: ver `opgg-local.md`. Catálogo local PT-BR confirmado; rankings completos não encontrados no file-cache inspecionado. A recomendação do componente examinado usa tier, desempate por ranking de performance, sem incorporar cartas anteriores. Isso não demonstra ausência de outros motores em todo o produto.

## Consequência para o desenho do produto

É viável criar uma base de referência para o universo de campeões consultado, exibindo avaliações das duas fontes separadamente, popularidade e discordâncias. Não fazer média cega de tiers nem apresentar consenso como verdade.

O motor próprio precisa adicionar interações verificadas entre campeão, cartas e itens. Tiers publicados não bastam para deduzir sinergia causal. A fórmula que transforma partidas em tier/performance está no servidor e não foi recuperada.

Atualização e cobertura precisam registrar patch, timestamp, fonte, carta habilitada, correspondência de IDs e ausências. Evitar tratar cartas removidas, dados ausentes ou diferenças de patch como discordância mecânica.

## Arquivos e repetição

- `public-snapshots/`: HTML, scripts inertes, respostas públicas e manifests com hashes/timestamps.
- `champion-snapshots/`: respostas por fonte/campeão e manifest; sem credenciais.
- `coverage-summary.json`: cobertura e limitações.
- `all-champion-comparison.json`: comparação normalizada dos pares compartilhados.
- `inspect_public_pages.py`, `inspect_endpoints.py`, `collect_champion_rankings.py`: coleta de pesquisa.
- `summarize_collection.py`: valida identidade das cartas e gera comparação; executar após completar coleta.

As rotas internas acessíveis sem autenticação não têm contrato de estabilidade confirmado. Este relatório não estabelece licença de redistribuição das bases de terceiros. Os snapshots se destinam à pesquisa local autorizada.
