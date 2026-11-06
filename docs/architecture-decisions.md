# Decisões de arquitetura

## Overlay de debug de 31/10/2026

Implementada uma janela independente em Python/Tkinter para exibir campeão, ofertas e histórico de escolhas inferidas, reaproveitando o coletor local. É uma escolha temporária de implementação para testar aquisição; a tecnologia do produto final continua em aberto. Sem motores de recomendação e sem Overwolf. O painel não ativa o jogo nem recebe seus cliques; acompanha o LoL em primeiro plano e possui atalhos de ocultação/saída. A lista selecionada usa clique passivo e fechamento do painel como inferência explícita, sem confirmação independente por HUD. Instruções, persistência e limites estão em `docs/debug-overlay.md`.

## Transição para o primeiro overlay utilizável

Em 30/10/2026, o usuário decidiu iniciar a etapa de overlay para testes pessoais antes de uma pausa no desenvolvimento. A leitura automática das cartas é obrigatória: entrada manual das três ofertas não atende ao MVP. Nenhuma dependência de Overwolf, incluindo componentes integrados em apps standalone, será usada. O requisito abrange reconhecer a oferta, atualizar após rerolls e acompanhar as cartas adquiridas; essas capacidades ainda precisam de validação prática. A investigação do mecanismo do OP.GG e a proposta de captura/OCR estão em `docs/data/augment-recognition-research.md`. Esta atualização documenta o escopo; o overlay ainda não foi implementado.

## Recomendações sem IA na primeira versão

Decisão do usuário em 30/10/2026: começar sem IA, preservando a possibilidade de adotá-la no futuro conforme custo e desempenho. Esta decisão orienta o planejamento; não autoriza por si só iniciar a implementação do overlay.

As recomendações iniciais serão calculadas localmente com dados previamente coletados e regras explícitas de compatibilidade, sinergia e conflito. A consulta ao MCP do arammayhem.com é acesso a dados e não exige usar um modelo de IA.

Manter separados o contexto da partida, as evidências das fontes, as regras de recomendação e a apresentação. Uma recomendação deve identificar as evidências e regras que a sustentam, incluindo limitações. Isso facilita revisar resultados e comparar um eventual mecanismo com IA usando o mesmo contexto.

Uma integração futura com IA será opcional. Sua adoção dependerá de ganho mensurável sobre a versão por regras, latência durante as escolhas, custo por partida e comportamento quando o serviço estiver indisponível. A versão local deve continuar utilizável sem essa integração.

Continuam válidas as decisões anteriores: nenhuma dependência de Overwolf; cobertura de todos os campeões; força, popularidade, desempenho e contexto apresentados como dimensões separadas.

## Apoio à decisão antes de um ranking próprio

Decisão da etapa atual: mostrar o efeito da carta e os principais indicadores das fontes para o jogador decidir, sem exigir que reconheça nomes ou forneça a melhor escolha como rótulo de teste. A política 0.3.0 reúne tiers por campeão, posição de popularidade calculada, desempenho com amostra e evidência do caminho, preservando os escopos. Não converter índices indefinidos em win rate nem mostrar tier geral como se fosse específico da build. Ver `docs/data/card-evidence-module.md`.

## Compatibilidade antes de força

Política inicial `0.1.0`: separar X (sem efeito aproveitável no contexto), F (não pegar nesta build), COND (adaptação/interação), OK (elegível) e ? (desconhecido) dos tiers de força das fontes. Rótulo AD/AP não autoriza veto; incompatibilidades exigem fatos revisados sobre o contexto real. Tiers e popularidade não superam um veto fundamentado. Ver `docs/data/recommendation-policy.md`.

## Seleção de caminhos prontos de build

Em 02/11/2026, o usuário priorizou a integração de builds/Arsenal e adiou novas expansões de cartas. A análise salva de dados existentes e pendências de cartas está em `docs/data/cards-follow-up-2026-11-02.md`. A revisão dos requisitos e da cobertura de builds está em `docs/data/item-set-integration-research.md`.

Implementação inicial em 02/11/2026: gerar a cobertura local dos 173 campeões, mas importar na conta somente os caminhos do campeão selecionado em `ChampSelect` de Mayhem. Ao trocar de campeão, substituir apenas os conjuntos gerenciados pelo aplicativo. O usuário esclareceu que não quer a instalação simultânea dos 433 conjuntos na conta. Os conjuntos permanecem estáticos durante a partida. Ver `docs/data/static-item-sets.md`.

Decisão do usuário: na primeira versão, selecionar somente caminhos predefinidos presentes nas referências de ARAM Mayhem, específicos para cada campeão. Não haverá personalização manual de itens no overlay nesta etapa.

O caminho escolhido orientará tanto a prioridade contextual das cartas quanto a recomendação de itens. Cartas e itens já adquiridos complementam esse contexto; não substituem silenciosamente a intenção selecionada. A recomendação de itens poderá variar entre os perfis disponíveis dentro desse caminho, conforme as cartas escolhidas, sem mudar automaticamente para outro caminho.

O jogador poderá trocar manualmente o caminho ativo durante a partida. A mudança recalcula cartas, itens e vetos de compatibilidade usando o estado real atual; não apaga compras ou cartas anteriores e invalida avaliações do contexto antigo. Uma carta atraente para outro caminho pode motivar essa troca, mas o sistema não a executa silenciosamente.

Importar para o Arsenal todos os caminhos prontos válidos disponíveis para o campeão, um conjunto por caminho, antes da partida. Aproximadamente 3–5 caminhos é a referência de experiência citada pelo usuário, não uma quantidade obrigatória. Não limitar a importação ao caminho ativo. Os nomes no aplicativo e na loja devem corresponder. A troca de caminho nas recomendações não depende de reimportação durante a partida; sincronizar automaticamente o conjunto selecionado na loja é uma capacidade ainda não validada. Ver `docs/data/item-set-integration-research.md`.

Preservar fonte, chave nativa do arquétipo, campeão, release e perfis associados. O ARAMKit já fornece arquétipos por campeão e perfis condicionados a cartas. Não presumir que caminhos com nomes parecidos em fontes diferentes sejam equivalentes, nem traduzir automaticamente `utility` como uma build exclusivamente de cura/escudo. Caminhos sem cobertura específica continuam com evidência limitada explícita; builds de ARAM normal permanecem excluídas.

## Cinco fontes ativas

Decisão do usuário: adiar METAsrc e manter League of Graphs fora das cartas. As fontes ativas são Blitz, OP.GG, ARAMKit, arammayhem.com e ARAMGG. Os snapshots de pesquisa das fontes adiadas são preservados, mas seus adaptadores não são executados e seus registros não integram novas publicações enquanto estiverem desativadas.

## Papéis das fontes na recomendação

Decisão acordada com o usuário: a familiaridade com os overlays Blitz/OP.GG não determina a hierarquia das evidências. A principal base quantitativa é ARAMKit (amostras, etapas, pares e perfis de builds); ARAMGG acrescenta outra leitura de desempenho com origem, região e patch preservados. Blitz e OP.GG são referências complementares de classificação e popularidade, sem votação entre fontes ou equivalência presumida de populações.

O arammayhem.com/MCP é uma fonte central de descrições e ideias de interação. Suas explicações devem ajudar a responder por que uma carta pode servir ao campeão, às cartas atuais e ao caminho selecionado. Conteúdo editorial não deve ficar relegado apenas a uma contagem de combos: apresentar a explicação relevante, a origem e as condições conhecidas. Separar efeito descrito, hipótese editorial e interação mecanicamente revisada. Quando não houver tradução disponível, identificar o idioma; não inventar uma explicação em português.

Uma carta marcada como retirada não invalida o acervo editorial inteiro, mas restringe o uso de exemplos que dependem dela. Em 30/10/2026, o usuário confirmou que Void Rift realmente não existe mais no modo. Essa confirmação específica está em `data/config/availability-observations.json`; não determina o patch da remoção nem confirma todas as outras entradas marcadas como retiradas.

Essa hierarquia é a orientação para a próxima evolução da apresentação. Os releases anteriores, incluindo o protótipo 0.3.0, preservam a ordem histórica em que foram gerados; não foram reescritos retroativamente.
