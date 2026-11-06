# Módulo de apoio à decisão por carta

Política **0.3.0**; módulo `card_evidence` **0.1.0**. A primeira entrega útil é reconhecer a carta e reunir as referências que o jogador consultaria. O usuário não precisa saber os nomes das cartas nem fornecer uma escolha correta para usar o módulo.

**Decisão posterior a este release:** priorizar ARAMKit/ARAMGG como evidência quantitativa e dar destaque às descrições e explicações relevantes do arammayhem.com/MCP, mantendo Blitz/OP.GG como referências complementares. A ordem da tabela abaixo documenta o protótipo 0.3.0, não a prioridade definitiva do produto. Ver `docs/architecture-decisions.md`, seção Papéis das fontes na recomendação.

## Conteúdo por carta

| Camada | Conteúdo | Escopo |
|---|---|---|
| Identificação | Nome PT-BR, nome inglês e efeito em texto | Descrição da fonte; fallback explícito |
| Referências rápidas | Tier Blitz e tier OP.GG | Campeão, não caminho de build |
| Popularidade | Posição calculada a partir do campo `popular` OP.GG | Todas as entradas não vazias publicadas para o campeão |
| Desempenho | ARAMKit: win rate e amostra da etapa, ou geral se a etapa faltar | Sem condicionamento ao caminho |
| Outra leitura de desempenho | ARAMGG: win rate e amostra de uploads do patch do snapshot | Geral do campeão; histórico não entra no destaque |
| Contexto | Veto/condição quando houver regra revisada; cobertura de perfis do caminho | Estado atual e evidência disponível |
| Detalhes | Perfil de itens, patch/data, índices indefinidos e conjuntos editoriais arammayhem | Escopos preservados |

Os indicadores servem para apoiar a decisão. Não há tier agregado, votação de fontes ou vencedor automático nesta versão. Fontes com possíveis populações compartilhadas não são votos independentes.

## Decisões de apresentação

- O efeito acompanha o nome: não pedir ao jogador para reconhecer cartas apenas pelo nome.
- Tiers Blitz/OP.GG não mudam artificialmente quando o usuário troca de caminho; eles continuam sendo as classificações publicadas por campeão.
- O campo OP.GG `performance` tem unidade não confirmada. Fica nos detalhes como índice bruto e nunca vira win rate ou porcentagem.
- A posição de popularidade é derivada do valor publicado, com empates preservados. Não é afirmada como um ranking copiado literalmente do site nem como probabilidade de escolher a carta quando oferecida. Registros com ambos os índices OP.GG zerados não participam dessa posição calculada.
- ARAMKit por etapa e ARAMGG geral aparecem identificados: não são a mesma população. Um valor ausente é `sem dado`; win rate zero continua sendo zero.
- O tier global arammayhem fica nos detalhes. Ele não substitui o tier específico do campeão. Conjuntos editoriais continuam hipóteses, mesmo quando listam cartas atuais.
- Descrições HTML são convertidas em texto. Valores dinâmicos não resolvidos são preservados e sinalizados. Falta de descrição/tradução não autoriza inventar texto.
- Falta de perfil no caminho não vira F/X. Perfis de builds concluídas não estimam por si só o efeito de escolher uma carta.

O índice de popularidade indefinido, um WR de perfil de itens e um tier editorial têm significados distintos. A apresentação deve tornar essa diferença legível, não simplesmente despejar todos os números na mesma hierarquia. No futuro, expandir detalhes é preferível a aumentar permanentemente a densidade de informação.

## Uso offline

```powershell
python tools/recommendation/offline.py replay --scenarios data/recommendation/scenarios/build-paths-0.2.1.json
python -m unittest discover -s tests
```

A mesma suíte de replays agora produz seções por carta com efeitos e indicadores. O JSON contém `evidence_card` em cada carta oferecida, com identidades, métricas, escopos e artefatos de origem. O relatório Markdown mostra as referências abaixo do nome/efeito e deixa os detalhes de build em seção expansível. Nenhum overlay ou importação no cliente foi implementado.

O arquivo opcional `judgments.json` agora também permite registrar se as informações foram suficientes e quais indicadores ficaram confusos. Escolher uma carta ou rotular a resposta correta não é requisito de uso. Anotações anteriores não são sobrescritas ao repetir uma execução.

## Validação

Os testes verificam: efeito PT-BR e alias inglês; remoção de HTML; preservação de valores não resolvidos; fallback de idioma; tier por campeão estável após troca de caminho; indicador indefinido nunca convertido em WR; seleção correta de etapa; histórico fora do destaque atual; posição de popularidade com empates; dados ausentes sem falso veto; e separação de tier global/editorial.

A suíte completa passou com **102 testes**. Isso valida o contrato dos indicadores e o fluxo offline; ainda não demonstra melhora em resultados de partidas ou acerto de um ranking próprio.
