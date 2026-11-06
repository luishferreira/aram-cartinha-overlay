# Retomada das cartas — 02/11/2026

Decisão do usuário: guardar esta análise e priorizar builds de itens/Arsenal. Não expandir a interface de cartas nesta etapa.

## O que já está integrado

Reconhecimento de campeão/ofertas/escolhas, interface compacta com tiers por campeão e posição OP.GG, comparação de fontes, pares/trios observados e notas editoriais por campeão. O compacto prioriza um resumo por opção. Todas as relações elegíveis e notas ficam em `combo_evidence` no JSON de evidência, não apenas o resumo visível. Ausência de combinação não é evidência de incompatibilidade.

Sem tiers globais, popularidade CN ou quantidade de jogos na interface. Amostras e proveniência continuam na base. Índice OP.GG não entra na interface compacta/comparação atual. Sem IA e sem Overwolf.

## Dados salvos versus trabalho pendente

| Conteúdo | Dados locais | Trabalho necessário |
| --- | --- | --- |
| Outros combos e notas completas | Salvos, com fonte/proveniência | Permitir consultar alternativas e explicações longas na interface |
| ARAMKit por etapa 1–4 | Salvos | Identificar a etapa com segurança, selecionar o contexto e rotular o fallback geral |
| Caminhos prontos de builds | Registro de 433 caminhos em 173 campeões | Integrar seleção, conjuntos do Arsenal e associação às cartas |
| Builds condicionadas a uma carta | Perfis, rotas e itens preservados | Consultar dentro do caminho ativo, sem inventar condicionamento conjunto a múltiplas cartas |
| Itens necessários, alternativas, condições e conflitos | Parte presente em textos editoriais; poucos exemplos estruturados | Extrair/revisar semanticamente; lista de membros não é requisito obrigatório |
| Vetos mecânicos X/F/COND | Estrutura e cenários offline existentes | Construir regras/perfis reais revisados com cobertura suficiente; não há matriz completa validada |

## Princípios para a retomada

- Priorizar o contexto das cartas adquiridas e do caminho escolhido, sem média de tiers nem vencedor fictício.
- Manter observado estatístico, recomendação editorial e regra mecânica revisada como evidências distintas.
- Não converter WR de um conjunto incompleto em previsão para o estado atual.
- Não usar conteúdo retirado, identidades desconhecidas ou registros históricos como evidência atual.
- Texto original inglês permanece identificado até haver tradução revisada.
- A cobertura estatística/editorial é parcial; não requer nova coleta para simplesmente expandir notas e combos salvos.

Referências: [painéis atuais](live-source-panels.md), [módulo offline](card-evidence-module.md), [política de compatibilidade](recommendation-policy.md) e [dados de builds](data-enrichment.md).
