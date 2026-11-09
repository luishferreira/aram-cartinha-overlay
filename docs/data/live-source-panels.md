# Dados das fontes nas cartas — interface compacta de 02/11/2026

Os três painéis acima das cartas exibem os tiers por campeão (AK/BL/OP/AM), a posição de pick calculada do OP.GG e o **Keitinha Score**. Resumos de combos ficam abaixo das cartas. WR, cobertura do score e comparação por fonte aparecem ao clicar em `Comparar fontes`, abaixo do histórico lateral. O reconhecimento continua independente, e uma leitura parcial não autoriza aquisição. Não é necessário executar Blitz, OP.GG ou outro overlay.

## Conteúdo

| Fonte | Exibição | Escopo |
| --- | --- | --- |
| ARAMKit | Tier no compacto; WR e popularidade na comparação | Geral do campeão, sem inferir etapa/build |
| ARAMGG | WR de uploads na comparação | Desempenho WORLD; popularidade CN permanece na base, sem exibição no overlay |
| Blitz | Tier publicado | Campeão, sem ajuste por build |
| OP.GG | Tier e posição calculada de popularidade | Campeão; índice bruto preservado apenas nos registros |
| arammayhem.com | Tier do campeão por raridade e trecho editorial quando disponível | Coleta parcial: até seis cartas por raridade por campeão; sem fallback global; editorial é hipótese, não interação confirmada |

WR e popularidade em proporção são formatados como porcentagem; amostras não são somadas. Zero é preservado. `—` significa falta de dado, sem inferir fraqueza ou veto. A posição OP.GG é calculada entre entradas publicadas não vazias, com empates preservados; não é probabilidade de selecionar uma carta oferecida.

As recomendações contextuais aparecem abaixo das cartas: verde para conjunto observado, dourado para caminho incompleto e azul para nota editorial. Pares ARAMKit e trios ARAMGG são consultados somente para o campeão atual. Quando a opção oferecida completa um conjunto observado com as cartas adquiridas, aparece `Forma par/trio observado`, com fonte e cartas envolvidas; o WR da combinação fica na comparação detalhada. Um conjunto incompleto aparece como `Caminho de par/trio`, com `Com` e `Falta`, sem exibir seu WR como se descrevesse a situação atual. A ordenação prioriza conjuntos completos, número de cartas já adquiridas e tamanho da amostra, nunca a maior WR como vencedor.

Notas editoriais arammayhem que também listam cartas adquiridas são priorizadas, sem afirmar que a sinergia está ativa. Outros membros aparecem como `Outras citadas`: listas editoriais podem conter alternativas e não são convertidas em requisitos obrigatórios. Não há extração automática de requisitos de itens. O texto original aparece como `Nota Mayhem (EN)`, sem tradução automática. Explicações vazias ou `Nothing.`, identidades sem correspondência/nome e conjuntos com membros declarados retirados são descartados. Pares/trios históricos ou sem patch compatível com o snapshot da própria fonte também são excluídos. Isso não atualiza os snapshots para o patch instalado no jogo.

As consultas e o cache rodam no worker existente, fora do OCR e da interface, com atualização ao mudar as cartas adquiridas. O compacto prioriza um conjunto observado contextual ou uma nota editorial, sem inventar um resumo mecânico. A comparação mostra os tiers, WR individual por fonte, popularidade ARAMKit, posição OP.GG e WR do conjunto completo. Um conjunto incompleto não recebe WR de previsão. Todos os conjuntos e notas permanecem em `combo_evidence` no JSON local, com amostras, membros, fonte e proveniência. Quando necessário, o texto termina em reticências para respeitar o espaço disponível acima da carta; o conteúdo completo permanece no JSON. A descrição mecânica principal continua visível na carta nativa do jogo. Nenhuma relação observada é tratada como efeito causal ou previsão de vitória, e ausência de combo não significa incompatibilidade.

Desde 09/11/2026, o [Keitinha Score](keitinha-score.md) acrescenta uma média explícita de quatro entradas com pesos iguais: tiers ARAMKit/Blitz/Mayhem e popularidade normalizada OP.GG. O tier OP.GG é preservado para consulta e excluído dessa média. Não há tier próprio, escolha automática ou estimativa condicionada ao caminho de itens. As informações são gerais do campeão. Dados por etapa e perfis de build permanecem na base para evoluções futuras.

## Base e execução

O módulo `tools/live/source_cards.py` abre o run apontado por `data/pipeline/current.json` com SQLite `mode=ro` e `query_only=ON`. A entrega foi validada na base `dc9801256aed94c6069941d5`, de 30/10. Não há coleta externa nem atualização automática por patch nesta etapa. Datas e patches são os publicados pelas fontes; diferenças como `16.21` e `26.21` são preservadas nos registros, sem presumir alinhamento. A interface não exibe datas, patches, cabeçalho de snapshot ou quantidade de jogos. Amostras continuam preservadas nos dados locais. WORLD aparece como `global`; a popularidade CN não é exibida.

Um worker separado consulta a base usando índices e mantém cache por campeão/carta/cartas adquiridas. A interface apenas solicita e lê o cache; o OCR não aguarda o SQLite. A troca de campeão não reutiliza estatísticas do anterior. Sem identificação do campeão, os indicadores específicos ficam sem dado e nenhuma recomendação contextual é produzida; não há fallback visual para tiers globais. Falha da base local é sinalizada no painel e nos registros.

Cada par exibido gera `source-card-<campeão>-<carta>.json` na sessão, com observações originais, artefatos, contexto e nota editorial completa. O arquivo guarda o último contexto mostrado para esse par. Os snapshots originais e os releases offline não foram alterados.

## Verificação

Os testes conferem dados reais de Tristana/O Boom e o Grave, separação de geral e etapa, escopos WORLD/CN, preservação de WR versus índice OP.GG, ranking de popularidade, ausências e zeros, texto editorial, isolamento do cache e consulta em background. Também conferem trio real de Teemo, combinações completas e parciais, rejeição de históricos/retirados/identidades desconhecidas, ausência de requisitos editoriais inventados, atualização do contexto e limites de texto. O preview nativo usa Master Yi com uma oferta simulada e dados reais, mostrando um par completo, um caminho incompleto e uma recomendação editorial; verifica que os painéis cabem acima do início das cartas, sem invadir a região de OCR dos títulos. A latência em uma partida com fontes ativas ainda precisa ser medida.
