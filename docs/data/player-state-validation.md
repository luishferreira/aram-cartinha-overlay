# Validação do estado do jogador antes do motor

Escopo acordado: reconhecer automaticamente o campeão em uso, as cartas oferecidas e as cartas já adquiridas. Nenhum desses estados pode ser substituído por digitação manual para considerar o MVP funcional. A recomendação permanece desligada nesta etapa.

## Evidências dos aplicativos

### OP.GG

O código de seleção usa `localPlayerCellId` para encontrar o próprio jogador em `myTeam` e acompanhar seu `championId`. No início da partida também existe recuperação por `gameData.playerChampionSelections`, associada ao jogador local. Intenção de pick não deve ser confundida com campeão confirmado depois de trocas/rerolls.

O serviço consulta `/activeplayer`, `/playerlist` e `/gamestats` da Live Client API. No componente Mayhem de `assets/react/stratum.addf6b47.js`, o campeão é resolvido cruzando identidade do jogador ativo e lista de jogadores, depois comparando `rawChampionName`/`championName` com as chaves do catálogo. O ramo examinado aceita Riot ID, nome ou PUUID e usa `find`; para nosso coletor, exigir correspondência única evita assumir o primeiro resultado em casos ambíguos.

As ofertas e escolhas continuam chegando pelo fluxo GEP já documentado. O componente examinado usa o evento da escolha para limpar a oferta; não foi demonstrada recuperação de uma lista completa de cartas adquiridas a partir desse trecho. Isso não prova ausência de outro fluxo no restante do produto.

### Blitz

O REA analisou `src/gameHandlers/lol/liveClient.js` em uma nova seleção focal. O arquivo consulta `https://127.0.0.1:<port>/liveclientdata/allgamedata` e cruza `activePlayer` com `allPlayers`. Tenta igualdade de nome completo, depois nome sem tag e, por último, associação pelas habilidades. O trecho observado pertence ao subsistema de benchmarks, que contém restrição ao mapa 11: é evidência de uma técnica usada pelo aplicativo, não prova do caminho específico do Mayhem.

Para nosso produto não precisamos copiar os fallbacks permissivos nem a integração nativa de overlay. A Live Client API já documenta jogador ativo e lista de jogadores com chave do campeão.

Referência oficial: https://developer.riotgames.com/docs/lol#game-client-api

## Proposta para nosso coletor

| Estado | Fonte preferida | Confirmação necessária |
| --- | --- | --- |
| Campeão durante a partida | Live Client API, identidade local única e chave bruta do campeão | Conferir em jogo, inclusive reconexão/início tardio; catálogo desconhecido não vira campeão parecido |
| Campeão durante seleção | LCU e slot local, como informação preliminar | Acompanhar trocas/rerolls; confirmar novamente quando entrar no jogo |
| Oferta atual | Captura visual, OCR dos nomes e catálogo PT-BR/inglês | Tela real, três posições, estabilidade temporal, rerolls, ausência da tela e erros de leitura |
| Cartas adquiridas | Investigar primeiro payload real; se não disponível, leitura visual do estado atual e histórico de escolhas confirmadas | Distinguir oferta de escolha e recuperar estado se o app iniciar no meio da partida |

Os IDs de runas encontrados num payload não serão interpretados automaticamente como augments. Ausência de campos chamados `augment` também não prova ausência de informação codificada em outros campos.

Guardar `last_observed_at`, origem, estado de confiança e identidade da partida/contexto. A aquisição deve distinguir desconhecido, observado e desatualizado; uma falha de captura não significa que a lista de cartas ficou vazia. O diagnóstico atual grava observações independentes e não produz recomendações.

O reconhecimento por ícones exige cuidado: no catálogo OP.GG salvo, 281 cartas compartilham apenas 226 URLs grandes e 229 pequenas. Há URLs reaproveitadas entre IDs diferentes. Isso limita esse catálogo como identificador visual único; não estabelece que todos esses ícones sejam iguais na interface real do jogo. Nome/texto ou outra evidência será necessário para resolver ambiguidades.

## Diagnóstico implementado

```powershell
python tools/live/probe.py --ocr --seconds 300 --interval 5
```

- Consulta somente a API local na porta 2999, sem chave Riot nem dependência de outro overlay.
- Resolve identidade antes do campeão, recusando ambiguidade e variantes não catalogadas.
- Salva payloads com campos usuais de identificação dos jogadores removidos.
- Captura somente a área cliente do processo `League of Legends` quando sua janela está em primeiro plano e não está minimizada. Captura por pixels visíveis ainda pode incluir outro overlay ou janela sobreposta; o frame precisa ser conferido.
- Executa OCR instalado no Windows e salva linhas/palavras com coordenadas para análise. Há idiomas PT-BR e en-US instalados nesta máquina; o diagnóstico usa PT-BR inicialmente.
- Não controla mouse/teclado nem escolhe cartas.
- O leitor inicial `tools/live/offer_reader.py` associa títulos nativos ao catálogo e publica ofertas como `observed`. Usa três regiões de títulos calibradas em 1920×1080, excluindo as regiões dos títulos dos overlays externos. Resoluções não calibradas, nomes desconhecidos e leituras parciais não geram uma oferta completa. Ainda não há confirmação temporal automática nem atribuição automática completa de cartas adquiridas.
- A coleta é limitada ao tempo solicitado. O intervalo de 5 segundos é de diagnóstico e pode perder transições rápidas; não define latência/frequência do produto final.

Saídas: `research/live-validation/<sessão UTC>/`. As imagens podem conter identificadores visuais do jogo; não são publicadas. A primeira integração OCR foi verificada com imagem sintética contendo `Ashe`, `Especialista` e `BEES!`; esse teste não comprova acurácia na interface do LoL.

## Critérios de validação em partida

1. Conferir o campeão observado sem depender de nome digitado, incluindo outro campeão em nova partida.
2. Conferir os três nomes e sua ordem espacial em ofertas reais.
3. Fazer um reroll natural e conferir atualização sem reaproveitar a oferta anterior.
4. Selecionar uma carta e conferir a carta adquirida, não apenas o desaparecimento do painel.
5. Reconhecer uma oferta posterior preservando as cartas anteriores.
6. Reiniciar o coletor com cartas já adquiridas e verificar recuperação; histórico local sozinho não atende esse caso.
7. Conferir comportamento em Alt-Tab, telas de transição e falha temporária da API.

Não considerar validação de um campeão como cobertura visual de todos. Chaves/catálogos cobrem todos os campeões conhecidos, mas a coleta precisa registrar casos reais variados antes de afirmar robustez geral.

## Arquivos e evidências

- `research/augment-recognition/player-tracking-installed-20261030.json`: hashes, fontes exatas e excertos dos dois apps.
- `research/augment-recognition/blitz-live-client-rea-summary.json`: recibo da análise REA focal.
- REA parent Blitz: `ev_75eea2c905f33195ea163de0ba0c14fe8c0f9027730f1438327e7dc505608735`.
- OP.GG reutiliza a análise do mesmo pacote documentada em `augment-recognition-research.md`; a inspeção focal do renderer é leitura/descompressão de bytes, não execução.
- `tools/live/probe.py` e `tools/live/capture_game.ps1`: diagnóstico independente dos aplicativos investigados.
- `tests/test_live_probe.py`: sete casos de identidade, idioma, ambiguidade, variante desconhecida e remoção de identificadores no payload.

## Resultado do primeiro teste real

Evidência consolidada em `research/augment-recognition/live-validation-results-20261030.json`. Em uma partida de Lillia, PT-BR, 1920×1080, modo `KIWI`, mapa 12:

- A associação por Riot ID completo e chave bruta resolveu Lillia em 201 observações coletadas até o fechamento desse resultado. Isso não equivale a testar 201 jogadores ou todos os campeões.
- Foram lidas 14 ofertas completas em frames, correspondentes a cinco combinações diferentes de três IDs, incluindo mudanças de slots por reroll. O número de frames não representa 14 rodadas independentes.
- Houve leitura de títulos com uma e duas linhas. Um exemplo real: Passo Rápido / Aprimorar Ápice da Tempestade / Brilhante. Outro: Alvorada Flamejante / Engenho do Encolhimento / Aprimoramento – Fulgor.
- Após a implementação inicial, o coletor reconheceu em execução Faculdade de Palhaço / Sobrecarga / Pacto Nefasto e depois Faculdade de Palhaço / Forma Final / Pacto Nefasto.
- O usuário abriu o próprio placar e exibiu os tooltips de Eureca (1030), Engenho do Encolhimento (1373) e Pacto Nefasto (1332). O OCR leu os três nomes e os ícones foram capturados. Isso valida a leitura desses tooltips em contexto assistido; não valida uma lista automaticamente atribuída ao jogador sem essa ação.
- O OpenAPI local foi preservado em `research/live-validation/20261030T223723.902327Z/openapi.json`: 26 rotas, sem rota nomeada para augments/Mayhem/Arena. O payload desta partida não trouxe campos de augment; `activePlayer.fullRunes` estava vazio e as runas da linha local não forneceram a lista. Não generalizar essa busca para toda interface interna possível do jogo.

O primeiro coletor isolado não enxergava o processo/porta local. A coleta passou a funcionar quando executada fora do sandbox do agente. Isso não demonstra necessidade de executar o produto como administrador. Nenhum componente do LoL foi alterado.

Os overlays terceiros permaneceram ligados durante as ofertas reais. O leitor usa somente os títulos nativos em y≈400–478, não os rótulos do OP.GG em y≈142. Um teste negativo desloca os mesmos títulos para essa região superior e confirma rejeição. A coexistência foi observada neste layout; ainda precisamos testar oclusão/posição de outros overlays.

Os 13 testes focais de identidade e leitura visual passaram. A fixture de oferta contém apenas os três títulos e suas coordenadas, sem o chat/nomes dos jogadores do frame original. A leitura de cartas adquiridas integralmente automática permanece pendente.

## Melhor caminho após essas evidências

1. Manter a Live Client API como fonte principal do campeão durante a partida. LCU serve para antecipar a seleção e identificar a sessão, sem tratar intenção de pick como campeão definitivo.
2. Executar captura e OCR em um worker persistente, restrito aos títulos quando a tela de ofertas for detectada. O processo PowerShell por amostra é um diagnóstico; não é a arquitetura final de baixa latência.
3. Confirmar ofertas por leituras consistentes, atualizar por slot após reroll e separar perda de visibilidade de mudança de escolha.
4. Para adquiridas, correlacionar escolhas com evidência posterior do HUD/placar e manter histórico por partida. Cliques naturais podem fornecer pistas, mas sozinhos não confirmam aquisição. Não usar eventos GEP de outro aplicativo como fonte do nosso produto.
5. Validar recuperação ao iniciar no meio da partida. O placar mostra ícones, e tooltips mostram nomes; ainda falta resolver automaticamente a linha local, ambiguidades dos ícones e recuperação sem exigir hover manual. Até resolver isso, o terceiro requisito não deve ser marcado como concluído.

Nenhum motor de recomendação será necessário para essas validações. Não avançar a apresentação de recomendações como se o estado completo já estivesse confiável.
