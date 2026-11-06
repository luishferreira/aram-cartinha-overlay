# Política de recomendação: compatibilidade antes de força

A evolução atual é a política **0.3.0**, com [efeitos e indicadores por carta para apoiar a decisão](card-evidence-module.md), além dos caminhos predefinidos e replays offline. A descrição abaixo documenta a versão inicial 0.1.0, preservada.

Versão `0.1.0`, protótipo offline. Artefato: `data/recommendation/policies/0.1.0.json`. Ponteiro e hash: `data/recommendation/current.json`. Base de referência: `dc9801256aed94c6069941d5`. Ainda não há ranking de força ou perfis automáticos de capacidades dos 173 campeões.

## Estados de compatibilidade

Força conserva os tiers originais das fontes. Compatibilidade tem classificação própria:

| Rótulo | Significado | Consequência |
|---|---|---|
| **X** | Sem efeito aproveitável neste contexto | Veto mecânico com evidência estrita |
| **F** | Não pegar nesta build | Veto por conflito de build revisado |
| **COND** | Depende de adaptação ou interação | Expor condições e custo da troca |
| **OK** | Elegível | Permite avaliar força; não significa carta boa |
| **?** | Compatibilidade desconhecida | Não inventar fraqueza ou incompatibilidade |

Tier S ou alta popularidade não podem superar um veto X/F. Desempenho baixo, amostra pequena ou ausência em uma lista não provam inutilidade.

X exige evidências revisadas de que o efeito não pode ser acionado, não há outro benefício aproveitável e o pré-requisito não pode ser adquirido dentro do horizonte avaliado. Ausência do pré-requisito agora não basta. Interações não revisadas impedem o veto definitivo. X sempre acompanha o campeão, as cartas, os itens, a build e o horizonte; não é uma proibição global permanente.

## Conversão AD/AP

Os catálogos coletados descrevem **ADAPt (1205) como conversão de AD adicional em AP**, com ganho de AP. O AD base não é descrito como convertido. A conversão inversa é escAPADe (1206). As descrições OP.GG/ARAMKit e seus hashes acompanham a política; os números não são usados para estimar dano neste protótipo.

Não excluímos cartas apenas porque um campeão é normalmente AD. Para cada conversão precisamos revisar dependência do atributo de origem, aproveitamento do atributo de destino por dano/cura/escudos/outros efeitos, interações de cartas/itens, comprometimento da build e possibilidade real de adaptação.

Conversão sem aproveitamento direto ou indireto, em build comprometida e sem adaptação viável, recebe F. Aproveitamento com perda de um atributo importante fica COND para avaliar a troca. Aproveitamento sem dependência revisada do atributo perdido permite avaliar força, sem presumir ganho líquido. Dados insuficientes produzem `?`.

Ainda precisamos construir os perfis de capacidades e escalamentos, incluindo modificações por cartas e itens. Papéis e estatísticas agregadas não substituem isso. **Não há uma lista real de campeões banidos para ADAPt nesta versão.**

## Fatos revisados e contexto

O avaliador recebe fatos booleanos com revisão, evidência e assinatura de contexto. `null`, ausência e zero numérico não viram `false`. Hipóteses não autorizam veto. Mudar campeão, candidato, cartas escolhidas, itens, etapa, build ou horizonte invalida a revisão anterior. Quantidades repetidas de itens são preservadas na assinatura.

`interaction_review_complete` significa revisão das interações relevantes para o candidato e contexto. Não pode ser verdadeiro se houver uma interação não modelada capaz de mudar a conclusão. O sistema verifica a estrutura dessas declarações, não a verdade da análise mecânica do revisor.

O resultado preserva os fatos usados/rejeitados, motivo, versão da política, hashes da política/avaliador e versão da base de referência. Não estima probabilidade de vitória.

## Teste offline

```powershell
python tools/recommendation/policy.py --scenarios data/recommendation/scenarios/compatibility-0.1.0.json
python -m unittest discover -s tests
python tools/recommendation/policy.py --context caminho/para/contexto-revisado.json
```

Os 11 cenários são **sintéticos**: build AD comprometida; caminho AP em campeão convencionalmente AD; troca híbrida; carta que cria aproveitamento de AP; adaptação viável; capacidade desconhecida; somente rótulo AD; conversão inversa; efeito impossível; pré-requisito adquirível depois; tier S incapaz de superar veto. Testam o contrato, não mecânicas de campeões reais ou melhoria de desempenho.

O formato do contexto está nos cenários. Em dados reais, cada fato precisa de `value` booleano, `review_status` (`reviewed` ou `verified_in_match`), `evidence` com referências e `context_fingerprint` calculado pela função `fingerprint`. O comando de cenários gera esses campos apenas para fixtures sintéticas identificadas.

## Versionamento

`data/recommendation/releases/0.1.0.json` registra os hashes da política, avaliador, cenários e testes. Mudanças de significado, critérios ou mecânicas revisadas devem gerar nova versão, preservando os artefatos anteriores. O hash do avaliador também acompanha cada resultado para distinguir implementações.

O próximo conjunto de dados necessário é a matriz de capacidades dos campeões e requisitos das cartas, com desconhecidos explícitos e cobertura de todos os campeões. Depois podemos aplicar a compatibilidade e avaliar força entre as opções restantes. O trabalho de atualização por patch segue adiado.
