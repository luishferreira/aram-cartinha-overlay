# Possibilidade de exportar caminhos para o Arsenal

**Atualização de implementação em 02/11/2026:** a primeira versão está pronta e documentada em [Arsenais estáticos](static-item-sets.md). Há cobertura local de todos os campeões, com importação LCU apenas dos caminhos do campeão selecionado no Mayhem. A pesquisa e as propostas abaixo ficam preservadas como histórico.

Pesquisa em 30/10/2026. Apenas documentação; nenhum conjunto do usuário foi alterado e não foi feita integração com o cliente local.

## Revisão de prontidão — 02/11/2026

O usuário priorizou builds/Arsenal e adiou a expansão de notas de cartas. A análise de retomada foi guardada em [cards-follow-up-2026-11-02.md](cards-follow-up-2026-11-02.md). Esta revisão não implementa exportação nem altera os conjuntos da conta.

Dados locais conferidos no run `dc9801256aed94c6069941d5`:

- Registro `data/recommendation/registries/build-paths-dc9801256aed94c6069941d5.json`: **433 caminhos gerais em 173 campeões**, de um a cinco por campeão. Distribuição: 45 campeões com um, 49 com dois, 36 com três, 33 com quatro e dez com cinco.
- Exemplos: Master Yi tem lutador, crítico, letalidade e efeitos ao contato; Senna tem AD, lutador, crítico, efeitos ao contato e utilidade; Ashe tem AP, crítico, híbrido e efeitos ao contato; Lillia tem AP. `utility` não é automaticamente uma build exclusiva de cura/escudo.
- ARAMKit: **130.580 perfis totais**, dos quais **126.844 condicionados a uma carta**; rotas preservam início, botas e itens posteriores. Contagens de perfis não são caminhos adicionais nem partidas independentes. As quantidades estão no `report.json` do run.
- Arammayhem/MCP: **2.076 opções** em grupos de início, botas, núcleo e itens posteriores para 173 campeões. São alternativas por grupo, não 2.076 builds completas nem combinações livres entre todos os grupos.
- ARAMGG: as builds adquiridas com fila 450 foram excluídas das recomendações Mayhem. Catálogo de itens não é recomendação de build.
- Não há exportador/importador do Arsenal implementado. As tabelas/registro e replays offline já oferecem a base de seleção dos caminhos.

Requisitos de implementação: montar um conjunto por caminho publicado a partir de perfis/rotas coerentes; preservar alternativas por bloco sem misturar populações; validar IDs e disponibilidade dos itens no modo, incluindo variantes específicas; associar campeão/mapa e testar a visibilidade no Mayhem; títulos estáveis por idioma e UIDs próprios; exportação revisável, importação sem apagar conjuntos alheios e restauração do estado anterior. Para automação via LCU, cliente aberto/logado, descoberta local da conexão e autenticação da sessão mantida em memória. Não depende de chave pública de desenvolvedor para a conexão local.

Prioridade proposta: exportador offline para todos os campeões; inspeção dos conjuntos gerados; prova de importação no cliente e visibilidade em uma partida; automação na seleção de campeão com controle de limite/limpeza apenas dos conjuntos do projeto. Não pré-carregar centenas de conjuntos sem verificar os limites da versão instalada.

A documentação oficial atual [Item Sets](https://support.riotgames.com/en-us/league-of-legends/gameplay/item-sets) confirma conjuntos de terceiros, blocos e múltiplos conjuntos por campeão. O [schema extraído do cliente](https://lcu.kebs.dev/) consultado ainda identifica versão 26.20; é evidência para planejar a integração, não teste na instalação atual. A [documentação da Riot sobre LCU](https://developer.riotgames.com/docs/lol#league-client-api) confirma o serviço local e sua ausência de suporte oficial a terceiros. Permanecem sem validação local: schema instalado, visibilidade no Mayhem, limites, recarga durante a partida e sincronização da seleção da loja.

## Evidência e limites

- A Riot documenta conjuntos de itens nativos, com blocos, associação a campeões/mapas, múltiplos conjuntos por campeão e conjuntos de terceiros: https://support.riotgames.com/en-us/league-of-legends/gameplay/item-sets
- O esquema LCU extraído do cliente 26.20 publica GET/POST/PUT `/lol-item-sets/v1/item-sets/{summonerId}/sets`. POST recebe `uid`, `title`, `mode`, `map`, `associatedChampions`, `associatedMaps`, `blocks` e outros campos: https://lcu.kebs.dev/
- A Riot descreve a API local do cliente e informa ausência de suporte oficial e garantias de estabilidade para terceiros: https://developer.riotgames.com/docs/lol#league-client-api
- O autor de LoL Item Sets Builder documenta conjuntos em arquivos JSON: https://www.lol-item-sets-builder.com/import
- Championify é um exemplo histórico aberto de importador; seu repositório foi arquivado em 2023. Não é comprovação de compatibilidade atual: https://github.com/dustinblackman/Championify

Não foi verificado qual mecanismo interno a versão atual do Blitz utiliza. A existência do recurso nativo e dos endpoints permite planejar uma implementação própria sem Overwolf; não comprova que o Blitz use exatamente o mesmo caminho de escrita.

## Fluxo proposto, ainda não implementado

1. Preparar antes da partida todos os caminhos prontos válidos disponíveis para o campeão, com um conjunto por caminho. O usuário cita aproximadamente 3–5 no Blitz como referência de experiência; não impor esse número nem inventar caminhos para completar uma cota.
2. Cada conjunto terá nome próprio que corresponda ao caminho mostrado pelo aplicativo e blocos de iniciais, itens principais, botas e opções posteriores, usando os IDs da base.
3. A seleção de caminho no aplicativo define o contexto ativo para avaliar cartas e recomendar itens. Ela pode ser alterada manualmente durante a partida, inclusive depois de uma carta que motive a mudança de build.
4. Ao trocar o caminho, recalcular as recomendações e os vetos contextuais com as cartas e os itens realmente adquiridos, invalidando revisões do contexto anterior. Não presumir venda, compra ou remoção de itens/cartas nem prometer que o novo caminho seja viável sem considerar o estado atual.
5. Os conjuntos dos demais caminhos já estarão disponíveis na loja; a troca de intenção no aplicativo não depende de reimportar conjuntos durante a partida. A seleção do conjunto na loja é uma ação separada até verificar eventual sincronização automática.
6. Primeiro validar exportação/importação dos múltiplos conjuntos estáticos. Depois avaliar sincronização por LCU.
7. Gerenciar somente conjuntos com identificadores próprios. Preservar conjuntos pessoais e de outros aplicativos; ao usar operações que substituem a coleção, manter as entradas que não pertencem ao projeto.
8. Validar visibilidade dos múltiplos conjuntos na loja do ARAM Mayhem, associação a mapa/modo e comportamento por idioma na versão instalada do cliente.

A primeira entrega deve preparar todos os conjuntos de caminhos antes da partida. Não foi confirmado que o jogo recarrega alterações do conteúdo de um conjunto durante uma partida: não prometer reescrita imediata da loja depois de cada carta. Essa limitação não impede o usuário de mudar o caminho ativo nas recomendações do aplicativo, pois os conjuntos alternativos já foram importados. Atualização dinâmica do conteúdo e sincronização da seleção da loja permanecem testes separados.

O conjunto apresenta itens na loja; não codifica por si só nossa lógica de cartas, confiança ou condições. Caminho pronto e suas opções continuam sendo a unidade de seleção definida pelo usuário.
