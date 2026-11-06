# Classificação por afinidade de itens

Versão atual: `build-path-classifier-3`, implementada em 06/11/2026. O usuário aprovou uma política mais permissiva: tolerar caminhos adicionais e priorizar referências úteis, sem exigir semelhança exata com um núcleo do ARAMKit. A análise da versão anterior está preservada em [build-classification-v2.md](build-classification-v2.md).

**Integração atual:** a release `112987fe81bd9f54056f7fb4` contém 3.531 registros, com a coleta OP.GG ampliada para 173 campeões/2.595 núcleos. O gerador já consome suas classificações nos [arsenais comparáveis](item-set-comparisons.md). A tabela de comparação com v2 abaixo preserva a cobertura da sondagem original de três campeões do OP.GG.

## O que significa a porcentagem

A porcentagem é uma **afinidade heurística com um caminho**, calculada pelas contribuições dos itens. Não é win rate, porcentagem dos atributos, probabilidade de acerto ou uma distribuição que precise somar 100%.

Cada item pode contribuir para vários caminhos simultaneamente. A Coletora do catálogo salvo possui AD, crítico e letalidade publicados: contribui para os três. Esses campos são interpretados a partir dos dados arquivados, sem inventar números atuais do patch. O score de um item não é uma divisão física entre seus atributos; 25 pontos de crítico e 10 de letalidade não são unidades comparáveis.

Para uma sequência sem alternativas:

`afinidade(caminho) = 100 × soma das contribuições dos itens relevantes / quantidade de posições relevantes`

Contribuições vão de zero a um. Alguns sinais são inteiros, outros parciais: armadura/resistência em item puramente defensivo contribui mais para Tanque que vida em item ofensivo; AP de item de cura/escudo contribui menos para um caminho AP ofensivo que AP de item de dano.

Adicionar um item pode aumentar ou reduzir a afinidade média. Isso permite que um item de crítico isolado não transforme uma lista inteira de itens AD em um caminho Crítico. Os detalhes e origens de cada contribuição estão em `item_contributions`.

## Famílias e especializações

As famílias são **AD, AP, Tanque, Utilidade e Híbrido**. Crítico, Letalidade e On-hit são especializações; Lutador é uma compatibilidade adicional. Elas não concorrem cegamente com a categoria genérica AD.

O classificador calcula todas as afinidades e então determina:

- `primary_family`: família predominante, considerando o papel de suporte e misturas AD/AP;
- `primary_path`: especialização predominante quando há suporte suficiente; caso contrário, a família;
- `assignments`/`compatible_paths`: caminhos adicionais permitidos pela política permissiva;
- `mechanics`: características auxiliares, por exemplo `healing_on_attack`.

Assim, AD 100% não impede Letalidade e Crítico de serem caminhos relevantes. Em empates entre especializações, a prioridade inicial determinística é Letalidade, Crítico e On-hit; as alternativas continuam acessíveis. Isso é uma convenção de apresentação, não prova de força.

Especializações exigem afinidade mínima de 35% e pelo menos duas posições de itens com sinal suficiente. Uma especialização secundária precisa atingir pelo menos 60% da afinidade da mais forte. Os valores são parâmetros heurísticos iniciais, registrados no artefato e no código. A política pode ser alterada em releases futuras sem cadastro manual de cada build.

Utilidade recebe tratamento de papel: cura/escudo e suporte não viram AP ofensivo apenas porque seus itens têm AP. Spellblade e efeitos genéricos sem velocidade de ataque têm sinal menor de On-hit; isso evita tratar a progressão normal do Ezreal como uma build dedicada a ataques com efeitos ao contato.

## Dados e alternativas

Os 1.851 perfis gerais, 433 caminhos e 173 campeões do ARAMKit permanecem como referência auxiliar e diagnóstico. As melhores correspondências antigas ficam em `prototype_candidates`; não controlam mais a classificação final. Ausência de um caminho no ARAMKit não bloqueia uma identidade sustentada pelas propriedades dos itens; essa diferença é sinalizada.

Os catálogos locais fornecem IDs, tipos e descrições. O texto dentro de `<stats>` permite distinguir letalidade de penetração percentual de armadura. Categorias genéricas como `ArmorPenetration` não bastam para declarar letalidade.

Tooltips de itens nas páginas já arquivadas do LemonNation complementam lacunas, com hash e origem preservados. Foi possível reconhecer a Espada do Alvorecer como item de cura por ataques sem criar uma regra exclusiva para a build da Lulu. Quando faltam propriedades, existe um fallback de pertencimento aos perfis de referência; essa origem fica explícita e diminui a cobertura dos metadados.

Transformações são reconhecidas somente quando a descrição da fonte publica explicitamente o item de destino e há correspondência inequívoca de nome. Manamune/Muramana, Abraço do Inverno/Fimbulwinter e outras relações detectadas recebem uma família de comparação. **IDs nativos nunca são substituídos nos dados ou itens exportáveis**; não há aproximação por prefixos numéricos de modos diferentes.

Grupos editoriais “A OU B OU C” contribuem como **uma posição**, usando a média das afinidades de suas alternativas. Não são três compras obrigatórias e não geram combinações completas fictícias. A sequência original, o grupo e suas alternativas permanecem no JSON. Botas, componentes e consumíveis conhecidos não definem a identidade. Repetições e transformações já representadas não multiplicam votos.

Vitória, popularidade e contagem de jogos não participam da classificação. O campo `source_record` permanece igual ao adquirido: uma afinidade não transforma estatísticas gerais em estatísticas condicionadas ao caminho ou às cartas.

## Exemplos discutidos com o usuário

Os cinco exemplos foram usados no desenvolvimento da política e **não são validação independente**. Não existem overrides por campeão/build para forçar seus resultados.

| Exemplo LemonNation | Caminho principal | Outras compatibilidades/afinidades |
| --- | --- | --- |
| Alistar, Mandato + quatro itens defensivos | Tanque, 77% | Utilidade 14% como sinal auxiliar |
| Soraka Support | Utilidade, 67,5% | AP ofensivo 49,5%; não promove AP como caminho principal |
| Lulu Attack Speed Support | Utilidade, 71,33% | Cura por ataques reconhecida; AP ofensivo 57,2% |
| Ezreal Traditional | AD, 100% | Lutador, 64% |
| Miss Fortune AD pen | Letalidade, 50% | Crítico, 50%; família AD, 100% |

O usuário confirmou as propostas anteriores, preferiu AD para o Ezreal tradicional e aceitou mais de uma classificação. O registro está em `data/build-classification/reviews/lemonnation-reviewed-2026-11-06.json`; a solicitação de revisão original também foi preservada.

## Cobertura e avaliação

| Fonte | Blocos/núcleos | Com classificação na v2 | Com classificação na v3 |
| --- | ---: | ---: | ---: |
| arammayhem.com | 865 | 831 | 865 |
| OP.GG Mayhem, três campeões auditados | 45 | 38 | 45 |
| LemonNation | 71 | 15 | 71 |

Os 71 registros editoriais vêm das 66 páginas de builds; não são 71 novas builds completas. A cobertura completa dessas entradas significa que todas obtiveram uma categoria pelo método, **não que todas estejam corretas**. IDs totalmente desconhecidos e núcleos sem sinal suficiente ainda podem ficar sem classificação.

A avaliação continua agrupando núcleos inteiros, independentemente da ordem, em cinco partições globais. O mesmo conjunto de itens, em qualquer campeão/rótulo, é removido dos perfis de referência durante sua rodada de teste. As propriedades publicadas dos itens continuam disponíveis; o fallback aprendido usa somente perfis de treino.

Na v3, contra os rótulos originais do ARAMKit:

- 1.851/1.851 casos receberam classificação;
- caminho principal concordante em **77,63%**;
- rótulo de referência incluído entre os caminhos permitidos em **90,44%**;
- média de **1,47 caminhos** por caso;
- igualdade estrita, sem nenhum caminho adicional, em **50,14%**.

A v2 obtinha 95,99% nas atribuições únicas, mas só atribuía 59,21% dos casos ocultos. Esses números não são a mesma métrica da inclusão permissiva da v3. A troca aceita pelo usuário aumenta cobertura e tolera caminhos extras. Persistem diferenças de taxonomia: uma build AD com características de Lutador pode receber AD como principal, enquanto a fonte a nomeia Lutador. Os resultados não comprovam precisão em partidas nem confiabilidade dos números das fontes.

“Confiança alta” indica sinal forte e disponibilidade de metadados sob estas regras. Não é probabilidade calibrada de a categoria estar certa. Metadados de patches diferentes ou desconhecidos são preservados e sinalizados, não tratados como equivalentes silenciosamente.

## Execução e revisão offline

Arquivos de implementação:

- `tools/items/classification.py`: afinidades, famílias, especializações e múltiplos caminhos;
- `tools/items/classification_prototypes.py`: comparador anterior preservado como apoio diagnóstico;
- `tools/items/classification_cli.py`: geração, avaliação, Markdown/CSV e replay;
- `tests/test_build_classification.py`: contratos e regressões do classificador.

`data/build-classification/current.json` aponta para uma release isolada. Modelo, entradas originais, percentuais por item, classificações, validação, Markdown e CSV são autocontidos e têm hashes registrados, junto com as versões dos códigos. A versão anterior foi preservada, inclusive suas cópias de código em `code-versions/v2/`.

```powershell
python -m tools.items.classification_cli build
python -m tools.items.classification_cli verify
python -m tools.items.classification_cli replay
python -m tools.items.classification_cli inspect --champion 22
python -m unittest tests.test_build_classification tests.test_static_item_sets -q
```

O replay não usa rede, LCU nem o banco ativo: usa o modelo salvo e verifica a mesma versão de código/política. A primeira entrega reproduziu 981 classificações e passou em 34 testes. Na integração atual, foram reproduzidas **3.531 classificações** e a avaliação salva; **40 testes** passaram, incluindo composição e importação dos arsenais. O banco ativo permanece no snapshot original; os conjuntos de itens passaram para a versão 3.
