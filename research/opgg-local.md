# OP.GG local: inspeção estática, 2026-10-30

Atualização posterior: a investigação em `docs/data/augment-recognition-research.md` acrescentou análise focal com REA e consulta a marcadores dos logs existentes. Os diagnósticos registram ofertas confirmadas e cartas escolhidas pelo fluxo GEP em 29/10/2026 e pacote `gep` pronto em 30/10/2026. Assim, a presença do caminho no pacote é agora corroborada por registros históricos de uso nessa instalação standalone; o mecanismo interno do GEP continua desconhecido. Os limites de investigação descritos abaixo referem-se à primeira inspeção.

## Escopo e identidade

Somente leitura dos artefatos instalados e do catálogo de jogo em cache. Nenhum aplicativo foi iniciado, nenhum processo foi anexado e nenhum token/cookie foi lido ou usado.

- Pacote: `C:\Users\Keita\AppData\Local\Programs\OP.GG\resources\app.asar`
- Versão em package.json: **3.2.0**.
- SHA-256 ASAR (REA): `28905aefb10180c12512c9ec0786c7638ccebed9ed09f0ada51899725f9d5231`.
- REA parent Evidence: `ev_2a9ec27ff347469322c7c679bfb3490fbd407edccf11b713db47ca6d6c12c949`.
- REA analisou somente package.json, com inventário completo e cobertura de código explicitamente parcial. Detectou divergências de integridade ASAR em vários companions nativos unpacked; executado novamente com record-and-continue para inventário, sem executar esses arquivos. Divergência pode ocorrer após assinatura/empacotamento; causa não estabelecida.
- Inspeção focal adicional: parser ASAR somente leitura, descompressão gzip em memória dos bundles React, busca textual contextual. Isso não executa o JavaScript e não prova uso em runtime.

## Catálogo de cartas já disponível localmente

`C:\Users\Keita\AppData\Roaming\opgg-electron-app\file-cache\lol_meta_aram-augments_pt_BR`

- JSON, 201235 bytes, **281 cartas**, metadado version **16.21**.
- Campos por carta: `id`, `name`, `key`, `largeIcon`, `smallIcon`, `rarity`, `desc`, `tooltip`.
- raridade no componente da aplicação: 1 prata, 4 ouro, 8 prismática.
- Exemplo de mapeamento: id 1001, key ARAM_ImTheJuggernaut, nome Determinação Titânica.
- Algumas descrições têm placeholders `?`; não são uma representação completa das fórmulas/valores dinâmicos.
- Esse catálogo NÃO contém tier/popular/performance por campeão.
- Também há caches PT-BR de campeões (3666750 bytes) e itens (697176 bytes). Não foi encontrado um banco completo de rankings por campeão no diretório file-cache; isso é uma ausência limitada a esse diretório, não a toda a aplicação.

## Endpoints observados no código empacotado

`assets/main/main.js`, função getLoLMayhemCatalog:

- GET `https://lol-api-champion.op.gg/api/meta/aram-augments`, params `hl` (locale), timeout 5000ms, User-Agent OP.GG Desktop App.
- Faz Map por nome normalizado e mantém cache em memória por locale.

`assets/react/2818.2cf5447a.bundle.js` (membro gzip) e `assets/react/stratum.addf6b47.js` (membro gzip):

- GET `https://lol-api-champion.op.gg/api/contents/stats/champions/{championId}/aram-augments`.
- O segundo componente consome campos `id`, `tier`, `popular`, `performance`.
- GET `https://lol-api-champion.op.gg/api/contents/tiers?type=aram_mayhem` para tiers de campeões.
- A existência dessas URLs no código não estabelece licença pública, estabilidade, disponibilidade atual ou metodologia do servidor. Nenhuma chamada de rede foi feita nesta subinvestigação.

## O que efetivamente calcula no cliente

No hook `qu` de stratum.addf6b47.js:

1. Faz ranking de popularidade ordenando `popular` decrescente (filtra valores null).
2. Faz ranking de performance ordenando `performance` decrescente (filtra valores null).
3. Enriquece cada uma das três cartas oferecidas com tier, performance, popularRank e performanceRank.
4. Escolhe recommendedIndex pelo menor tier numérico; empates são resolvidos pelo menor performanceRank; ausência de tier vira 9 e ausência de performanceRank vira MAX_SAFE_INTEGER.

**Conclusão observada:** esse trecho recomenda considerando as três ofertas e avaliações do campeão. Não consulta uma lista de cartas previamente escolhidas para calcular sinergias. O evento pickedAugment apenas limpa a oferta ativa nesse trecho. Isso não prova ausência de outro motor em toda a aplicação.

**Desconhecido:** fórmula do servidor que gera tier, popular e performance; tamanho da amostra, recortes, normalização e relação com win rate. Não chamar performance de win rate sem prova.

## Reconhecimento automático: pista técnica útil

`assets/main/main.js` contém integração Overwolf GEP e handlers de feature `augments`, keys `me`/`augments` e `picked_augment`. Mapeia nomes ao catálogo; exige três cartas confiáveis com ids positivos; publica estado `lol:mayhem.gepEvent` e escolha em `lol:mayhem.pickedAugment`.

O componente React usa mapa `KIWI` para esse fluxo e identifica o campeão a partir dos dados live do jogador. Isso demonstra uma rota implementada no pacote usando eventos GEP, não apenas OCR. Ainda não valida disponibilidade desse SDK para nosso projeto nem observa funcionamento na máquina.

## Limites da busca

IndexedDB/Local Storage/Cache possuem artefatos Chromium; busca nominal encontrou Mayhem nos blocos data_1/data_5 do Cache, mas leitura via .NET falhou por arquivo em uso. Não foi tentado desbloqueio, alteração de processo ou cópia forçada. Não foi inspecionado conteúdo de cookies, Network, autenticação ou histórico pessoal.

## Mapeamento confirmado de tiers e explicações locais

Em `assets/react/stratum.addf6b47.js`, texto descomprimido, offset de caracteres 647948, objeto `$u` define **0=S, 1=A, 2=B, 3=C, 4=D, 5=E**. O componente em offset 668784 acessa diretamente `$u[String(e.tier)]` e renderiza `a.label`; valores ausentes/inválidos caem no estilo E. O tooltip de cartas em `assets/react/8377.d0cce38e.bundle.js` também tem `Ls={0:"S",1:"A",2:"B",3:"C",4:"D",5:"E"}`. Portanto não confundir com a escala de tiers de campeões, que possui outro array OP/S/A/B/C/D no mesmo bundle stratum.

A busca focal no fluxo das cartas encontrou tier vindo diretamente do endpoint e nenhum cálculo que derive tier de popular ou performance. A fórmula do servidor continua desconhecida; não é correto inferir dependência exclusiva de um desses campos.

Há, entretanto, uma fórmula **local para o texto descritivo** mostrado embaixo da carta (offset aproximado 668850), que usa posições relativas nos rankings:

- Faixa alta: rank <= max(2, ceil(0.20 * total)).
- Faixa baixa: rank >= max(limite_alto+1, floor(0.55 * total)).
- Performance alta + popularidade alta → `strong-and-popular`.
- Performance alta + popularidade baixa → `strong-sleeper`.
- Popularidade alta + performance baixa → `popular-comfort`.
- Tier 0 ou performance alta → `high-upside-option`.
- Tier 1 ou popularidade alta → `reliable-pick`.
- Tier >=4 com performance baixa → `situational`.
- Popularidade baixa sem performance baixa → `good-in-spots`.
- Restante → `depends-on-comp`.

Essas frases não são evidência de análise real de composição: o código desse ramo usa somente tier e ranks globais dentro do campeão, sem cartas possuídas, itens ou equipes. A ordem dos casos acima é significativa. Se faltam ranks/totais retorna `checking-stats`.
