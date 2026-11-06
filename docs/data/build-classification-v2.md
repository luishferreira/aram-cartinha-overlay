# Classificação automática de caminhos de build

Implementada em 06/11/2026, versão `build-path-classifier-2`. A execução atual é um artefato de pesquisa offline, separado da geração de arsenais e do overlay. Não requer IA, rede ou revisão manual de cada build.

## Modelo e comportamento

O modelo incorpora os **1.851 perfis gerais filtrados do ARAMKit**, nos **433 caminhos dos 173 campeões**, e o catálogo de itens disponível no snapshot ativo. Perfis condicionados a cartas não foram transformados em exemplos de caminhos gerais. A origem, o patch nativo, o seletor e o hash de evidência de cada perfil permanecem no modelo.

A identidade da build é comparada com todos os perfis do **mesmo campeão**. Cada caminho recebe o melhor resultado de seus perfis, sem votação por quantidade de rotas, jogos, popularidade ou vitória. Duplicatas não ganham peso.

O score de similaridade usa:

- **80% correspondência de itens**: Jaccard ponderado; itens presentes em menos caminhos daquele campeão distinguem mais. A ordem de compra não altera a identidade, mas permanece intacta no registro original.
- **20% características publicadas dos itens**: similaridade de categorias como AP, crítico, efeitos ao contato, defesa, mana etc. As categorias vêm do catálogo ARAMGG salvo, e não das builds de fila 450 descartadas desse fornecedor. O catálogo arammayhem.com complementa tipo e identidade dos itens.

Botas, consumíveis, trinkets, iniciais e componentes conhecidos são desconsiderados apenas no cálculo da identidade. Itens completos não são descartados por um rótulo isolado de raridade: há, por exemplo, Gume do Infinito marcado como `epic` em um catálogo. IDs sem características conhecidas são preservados, não aproximados por outro ID, e reduzem a confiança. Pelo menos dois itens relevantes compartilhados são necessários para uma atribuição.

As características também geram sugestões de caminhos, inclusive quando o campeão não possui aquele caminho publicado. Essas sugestões **não criam automaticamente caminhos novos** e não substituem a exigência de referências do mesmo campeão.

Os resultados são distintos:

| Estado | Campo | Significado |
| --- | --- | --- |
| `assigned` | `assignments` contém um caminho | Melhor candidato supera os mínimos de similaridade e separação |
| `ambiguous` | `assignments` vazio; `compatible_paths` contém possibilidades | Mais de um caminho compatível; não é confirmação de uma build híbrida |
| `unclassified` | `assignments` vazio | Núcleo insuficiente, pouca correspondência, excesso de possibilidades ou ausência de referência |

Uma ambiguidade não vira duas atribuições definitivas silenciosamente. As possibilidades continuam acessíveis para futura apresentação em mais de um arsenal, com identificação explícita. Sem correspondência suficiente, o sistema não força o único caminho que o campeão eventualmente possui.

Limiares iniciais: similaridade mínima 0,50; diferença mínima entre os dois melhores caminhos 0,10; similaridade alta a partir de 0,75, com características conhecidas. **Similaridade e confiança não são probabilidades de acerto**, nem avaliação de força. Não houve ajuste desses parâmetros para perseguir um resultado melhor na validação.

## Aplicação às fontes coletadas

| Fonte | Núcleos/blocos analisados | Caminho único | Ambíguos | Sem classificação |
| --- | ---: | ---: | ---: | ---: |
| arammayhem.com | 865 | **831** | 16 | 18 |
| OP.GG Mayhem | 45 | **38** | 3 | 4 |
| LemonNation | 71 | **15** | 3 | 53 |
| Total | **981** | **884** | **22** | **75** |

Os 45 núcleos OP.GG são dos três campeões auditados, não de todos os campeões. As páginas ARAM normal foram excluídas. As 865 alternativas do arammayhem.com cobrem os 173 campeões.

Os 71 registros do LemonNation são **blocos editoriais de caminhos**, vindos das 66 páginas de builds; não são 71 builds completas. Alternativas `choose_one` não foram expandidas em combinações artificiais. O classificador usa apenas os itens obrigatórios publicados no bloco, preserva os tokens de alternativas no registro original e sinaliza quando essa representação é parcial. Isso explica parte da cobertura menor e evita fingir certeza sobre condições descritas em texto.

O MayhemStats não foi convertido em sequências: seus registros de itens individuais e tempo médio de compra não demonstram uma build conjunta. Iniciais, botas e listas gerais de itens das outras fontes também não viraram novos núcleos sintéticos.

Exemplos do resultado atual:

- Ashe, OP.GG, Yun Tal + Runaan + Gume: Crítico, correspondência exata com referência.
- Master Yi, OP.GG, Mata-Cráquens + Rei Destruído + Guinsoo: On-hit, correspondência exata com referência.
- Lulu, OP.GG, Lágrima + Pedra Lunar + Diadema + Turíbulo: Utilidade, com Lágrima ignorada apenas no cálculo e confiança média.
- Kayle, LemonNation, bloco “vs tanks”: On-hit; o bloco “vs squishies” é classificado AP. São blocos editoriais separados, sem converter isso em estatística observada dessas builds.

As métricas originais ficam em `source_record`, com comparação de igualdade antes de publicar. Classificar a identidade não altera o denominador nem transforma popularidade geral de um item em popularidade dentro do caminho. Patch de origem e patch de referência continuam nativos; a igualdade entre versões/notações diferentes não é presumida.

## Validação sem vazamento de núcleos repetidos

Cinco partições determinísticas são formadas pelo **conjunto não ordenado dos itens relevantes**. O mesmo núcleo inteiro, em qualquer ordem, campeão ou rótulo, fica na mesma partição. A cada rodada, esse grupo completo é removido dos exemplos e das características agregadas usadas para classificar os casos ocultos.

| Resultado | Casos |
| --- | ---: |
| Total de casos ocultos | 1.851 |
| Receberam caminho único | 1.096 — **59,21% de cobertura** |
| Caminho único concordou com a referência | 1.052 — **95,99% dos atribuídos** |
| Ficaram ambíguos | 498 |
| Ficaram sem classificação | 257 |

O número de 95,99% se refere às **atribuições únicas**, não a todas as entradas e nem aos dados externos sem rótulo conhecido. A validação mede concordância com a taxonomia do ARAMKit, não verdade independente em partidas. Os exemplos de categorias pouco numerosas são particularmente incertos:

| Caminho | Atribuições únicas | Concordantes |
| --- | ---: | ---: |
| AP | 406 | 404 |
| Crítico | 165 | 161 |
| On-hit | 62 | 56 |
| Tanque | 265 | 262 |
| Utilidade | 55 | 55 |
| Lutador | 98 | 81 |
| Letalidade | 37 | 28 |
| AD | 7 | 5 |
| Híbrido | 1 | 0 |

A avaliação ocultando núcleos completos não produziu casos de confiança alta: as correspondências exatas/mais próximas também foram retiradas. Portanto, **não há estimativa independente de precisão para a faixa alta**. A alta confiança nas fontes externas significa proximidade com perfis conhecidos, não acerto validado em 96% dessas linhas.

Antes de aplicar classificações automaticamente no Arsenal, a política de admissão deve considerar essas diferenças. AD, Híbrido, Letalidade e Lutador exigem atenção adicional; os rótulos podem se sobrepor e o resultado agregado não deve esconder suas limitações. Não foi introduzida uma fila obrigatória de trabalho manual para manter a base.

## Artefato e reprodução

Entrada e lógica:

- `tools/items/classification.py`: classificador determinístico, sem dependência de LCU.
- `tools/items/classification_cli.py`: coleta local de referências, classificação, avaliação e publicação isolada.
- `tests/test_build_classification.py`: contratos de independência de métricas, ordem, duplicação, ambiguidade, ausência de referências, IDs desconhecidos e isolamento das partições.

`data/build-classification/current.json` aponta para uma release própria. Não substitui nenhum ponteiro de produção. Cada release tem modelo autocontido, classificações com evidências, validação por caso, resumo, CSV e Markdown para revisão. O manifest registra hashes dos artefatos, dos dados de entrada e do código usado. Releases anteriores são preservadas.

```powershell
# Gerar a partir dos snapshots locais já coletados
python -m tools.items.classification_cli build

# Conferir integridade dos artefatos
python -m tools.items.classification_cli verify

# Reexecutar classificações e validação só com o modelo salvo, sem rede/base ativa
python -m tools.items.classification_cli replay

# Inspecionar um campeão, exemplo: Ashe
python -m tools.items.classification_cli inspect --champion 22

python -m unittest tests.test_build_classification tests.test_static_item_sets -v
```

O replay exige a mesma versão/política e os mesmos hashes de código registrados. Alterações futuras geram uma nova release, em vez de modificar o resultado antigo. A reprodução das 981 classificações e da avaliação foi verificada offline. Os testes incluem regressão dos arsenais existentes; nenhuma importação real no cliente foi executada por esta tarefa.
