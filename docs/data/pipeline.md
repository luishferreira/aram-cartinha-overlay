# Fluxo unificado de dados Mayhem

Implementado em 30/10/2026. Esta etapa reúne dados e permite consultas locais; não implementa overlay, captura do jogo ou recomendações por IA. Overwolf está excluído. League of Graphs e METAsrc estão fora das cartas por enquanto. Cinco fontes ativas: Blitz, OP.GG, ARAMKit, arammayhem.com e ARAMGG.

## Os cinco passos

1. **Identidade central:** campeões, cartas e itens usam IDs `champion:game:11`, `augment:game:2010`, `item:game:3508`. Aliases de cada fonte e nomes por idioma ficam separados. Correspondências por nome precisam ser exatas após normalização e únicas. Correspondências desconhecidas conservam namespace próprio, como `augment:arammayhem:slug`.
2. **Observações padronizadas:** cada registro preserva fonte, snapshot, artefato original, contexto, patch, data, métrica, unidade e limitações. Os tiers mantêm a escala da fonte e nunca são promediados. Campos sem definição continuam sem definição.
3. **Adaptadores e aquisição:** cinco fontes ativas; o adaptador METAsrc fica desativado na configuração. Há aquisição pública com retomada para as quatro fontes iniciais prioritárias, e ARAMGG tem coletor autenticado próprio. Originais arquivados por SHA-256, sem alterar as pesquisas anteriores.
4. **Relações e regras próprias:** pares observados e conjuntos editoriais são evidências distintas. Regras locais têm pré-requisitos, alternativas, itens, conflitos, explicações PT-BR/inglês, proveniência e revisão explícita.
5. **Validação e publicação:** integridade, referências, amostras, probabilidades e cobertura são verificadas antes de publicar SQLite. A troca de `current.json` é atômica. Uma atualização rejeitada não substitui a base válida.

## Comandos

Na raiz `C:\Projects\lol-overlay`, Python 3.12 usado na validação:

```powershell
python tools/data/pipeline.py build
python tools/data/pipeline.py status
python tools/data/pipeline.py verify
python tools/data/pipeline.py changes
```

Esses comandos são offline e usam a biblioteca padrão. `build` transforma os snapshots existentes; não disfarça sua idade como uma nova coleta. Rodar novamente com os mesmos dados, código e configuração reutiliza a versão verificada.

Consultar evidência de uma carta por campeão e idioma:

```powershell
python tools/data/pipeline.py evidence augment:game:2010 --champion champion:game:11 --locale pt-BR --limit 10
python tools/data/pipeline.py evidence augment:game:2010 --champion champion:game:11 --locale en-US --source aramkit --limit 10
```

Consultar referências de contexto, sem produzir um ranking de escolha:

```powershell
python tools/data/pipeline.py context --champion champion:game:11 --augments augment:game:2010 --offered augment:game:1002 --limit 10
```

O retorno distingue conjuntos de requisitos desconhecidos, pares observados e regras locais revisadas. Uma lista editorial de 15 cartas não vira automaticamente 105 pares positivos.

## Atualizar dados públicos

O comando abaixo cria uma área de aquisição independente, com cópias dos dados não selecionados. Não modifica a pesquisa original nem publica resultados automaticamente:

```powershell
python tools/data/pipeline.py fetch --sources blitz opgg aramkit arammayhem --workspace C:\Projects\lol-overlay\data\intake\atualizacao-001
```

O workspace precisa ser um novo subdiretório de `data/intake/`. A coleta é sequencial, com intervalo e checkpoint de arquivos verificados. Em caso de falha, corrigir a condição e retomar com os mesmos argumentos, acrescentando `--resume`. HTTP 403/429 ou mudança de formato interrompem a aquisição; não há contorno de bloqueios.

```powershell
python tools/data/pipeline.py fetch --sources blitz opgg aramkit arammayhem --workspace C:\Projects\lol-overlay\data\intake\atualizacao-001 --resume
python tools/data/pipeline.py build --input-root C:\Projects\lol-overlay\data\intake\atualizacao-001
```

Uma aquisição incompleta é recusada pelo `build`. Fontes não selecionadas preservam datas e cobertura anteriores; o relatório indica idade desconhecida ou dados antigos. Uma nova rodada independente deve usar outro workspace. Retomar o mesmo workspace não significa consultar novamente arquivos já confirmados pelo checkpoint.

Blitz e OP.GG usam os endpoints públicos identificados na pesquisa. ARAMKit descobre o release na configuração pública, sem executar JavaScript externo, e fixa os arquivos desse release. ARAMKit atualiza o catálogo antes das consultas por campeão; a identidade inclui novos campeões encontrados nesse catálogo. Atualizar apenas ARAMKit quando há campeão novo pode bloquear publicação até as outras fontes primárias cobrirem esse campeão.

O coletor arammayhem baixa os datasets oficiais e consulta combos/builds de todos os campeões, detalhes da união de cartas do catálogo/combos, tiers de campeões e notas do patch. Respeita intervalo acima de um segundo entre consultas MCP; pode levar vários minutos. Exige `requests`, já disponível neste ambiente. Conteúdo MCP não recebe automaticamente a licença dos downloads. Uma indisponibilidade explicitamente informada é guardada; outros erros interrompem a coleta.

A [coleta completa do MCP](arammayhem-mcp-full.md) também inclui IDs históricos, notas dos 12 patches e ordens/caminhos de habilidades. Depois de auditar a área de aquisição, usar `complete_mcp.py promote` para preservar o snapshot no diretório de pesquisa e selecioná-lo nos builds futuros feitos na raiz do projeto.

**ARAMGG:** a API de desenvolvedor foi adicionada em investigação posterior. `python research/collect_aramgg_api.py --key-prompt --sync-champions` faz coleta autenticada com retomada, sem salvar a chave. Uma aquisição completa é importada pelo `build` no lugar do HTML limitado. Ver [cobertura, proveniência por métrica e quota](aramgg-api.md). Builds recebidas com fila 450 são excluídas de Mayhem.

**Fontes adiadas:** METAsrc está desativado, com os snapshots existentes preservados para eventual retomada. League of Graphs também fica fora das cartas. O recurso adicional ARAMKit `single-augments` agora está coletado para os 173 campeões, no mesmo release dos detalhes gerais. Ver [normalização e consultas de builds](data-enrichment.md). O exercício de atualização para um novo patch foi adiado por decisão do usuário até termos um patch novo para acompanhar.

## Estrutura dos arquivos

```text
data/config/
  pipeline.json                 fontes, idiomas, frescor e política de versões
  rules.json                    interpretações manuais, com status explícito
  identity-aliases.json          aliases revisados, com chave interna esperada
data/pipeline/
  current.json                  ponteiro da versão publicada
  raw/<prefixo>/<sha256>         bytes originais ou envelopes da pesquisa
  runs/<versao>/
    mayhem.sqlite3              banco somente de leitura para consumo
    manifest.json               entradas, origens e hashes das saídas
    report.json                 cobertura, validação e idiomas
    identity-mappings.json      correspondências e casos não resolvidos
    changes.json                diferenças da versão anterior
    review-queue.json           relações/regras que precisam de revisão
    catalog-state.json          estado semântico para comparação
    source-state.json           metadados de versões por fonte
    note-state.json             assinaturas das notas de patch
    config.json                 configuração usada nesta versão
    canonical-augments.json      identidades, nomes, disponibilidade e cobertura por fonte
    data-quality.json           resumo de qualidade e limitações
    source-comparisons.csv      métricas por campeão/carta, sem misturar dimensões
    source-comparisons.json     correlações descritivas dentro de cada campeão
    combo-review.json           fichas dos 666 combos, com requisitos desconhecidos explícitos
    relation-statistics.json    pares/trios com amostras e referências compatíveis
data/intake/<rodada>/            aquisição retomável, ainda não publicada
```

Os originais antigos nunca são sobrescritos. A origem de cada observação aponta para seu artefato, que pode ser lido no arquivo arquivado mesmo que o site mude. Envelopes antigos da pesquisa são identificados como tal; seu hash é o do envelope guardado. Artefatos que já tinham hash do conteúdo adquirido são conferidos contra ele.

## Contrato do banco

- `entities`: identidade e indicador de existência de metadados de catálogo. Um item observado sem catálogo continua consultável, com identidade preservada.
- `catalog`: nomes, descrições e atributos por fonte, artefato e ID nativo. Descrições HTML/estruturadas não são executadas nem tratadas como números finais.
- `observations`: entidade, contexto, patch/data e métricas. Cada métrica tem `value`, `unit`, `meaning` e `denominator` quando conhecido. Proporções são 0–1; pontos percentuais convertidos devem ser identificados separadamente. Campos OP.GG `popular_raw` e `performance_raw` ficam com unidade desconhecida.
- `relations`: `observed_pair` ou `editorial_bundle`, com semântica dos membros, métricas/texto, proveniência e estado de validação. MCP e download do arammayhem pertencem à mesma família.
- `rules`: regras locais que passaram na validação estrutural; revisão mecânica continua explícita.
- `build_profiles`: conjunto de itens, arquétipo, métricas e rotas de compra; cartas condicionantes e filtros preservados. Itens iniciais, botas e itens posteriores pertencem à sua rota, não ao campeão inteiro.
- `conditional_item_groups`: itens por carta e campeão, incluindo separação por slot. Grupos publicados são consultáveis sem expandir todos os itens em memória durante o build.
- `patch_notes`, `change_events`, `review_queue`: alterações e revisão, sem converter automaticamente uma notícia em mudança de mecânica.
- `snapshots`, `artifacts`, `artifact_origins`, `identity_mappings`: rastreabilidade.

O relatório distingue observações e partidas. Registros por slot, estágio e condicionamento não são partidas adicionais nem amostras independentes para somar.

## Patches, cartas novas e alterações

As versões são registradas como informadas: `16.21` e `26.21` não são consideradas equivalentes só pelo sufixo. `patch_aliases` é reservado a equivalências com evidência; o matcher atual exige versão exata por fonte e não aplica aliases implicitamente. No OP.GG, patch do catálogo não preenche o patch ausente das estatísticas.

Ao comparar duas publicações:

- Entrada nova gera `catalog_entry_added` e uma tarefa de inspeção para cartas.
- Entrada ausente gera `catalog_entry_missing`; **não significa retirada do jogo**.
- Descrição/tooltip diferente gera `effect_text_changed`.
- Mudança em valores de efeito, disponibilidade, raridade ou outros atributos gera `attributes_changed`.
- Alteração de tradução/identidade fica distinta de alteração de efeito.
- Mudança do patch da fonte ou apenas de seu catálogo tem eventos separados.
- Notas de patch alteradas geram tarefa de revisão; o resumo de terceiros pode ser incompleto.

Relações dependentes são enviadas à fila. Regras revisadas afetadas ficam com `pending_review`, inclusive em hotfix no mesmo patch. A fila persiste entre builds; não desaparece porque alguém corrigiu um texto. Depois de rever a mecânica, incrementar `review_revision` e conferir os patches em `data/config/rules.json`.

A primeira importação cria uma baseline. Não apresenta todo o catálogo como cartas recém-lançadas. Cada alteração observada no snapshot continua sendo uma alteração de dados da fonte; não prova sozinha que houve mudança real da mecânica.

As notas guardadas atualmente vêm do arammayhem e estão identificadas como resumo de terceiros. Não há ingestão automática das notas oficiais da Riot nesta etapa. Confirmar mudanças relevantes na fonte primária continua sendo parte da revisão, sobretudo antes de validar regras mecânicas.

## Formato de regra local

Exemplo **somente estrutural**, sem alegação sobre a mecânica das cartas usadas:

```json
{
  "id": "identificador-estavel",
  "status": "reviewed",
  "review_revision": 1,
  "champions": ["champion:game:11"],
  "required_augments": ["augment:game:2010"],
  "alternative_augment_groups": [["augment:game:1002"]],
  "required_items": ["item:game:3508"],
  "conflicting_augments": [],
  "validated_patches": {"aramkit": "16.21"},
  "evidence": ["URL-ou-referencia-da-evidencia"],
  "explanation": {"pt-BR": "Explicação revisada", "en-US": "Reviewed explanation"}
}
```

Estados aceitos: `hypothesis`, `reviewed`, `verified_in_match`. As primeiras quatro interpretações editoriais estão como `hypothesis`; não há regras verificadas em partida. Os 2.923 registros de relações são evidências, não sinergias verificadas. O matcher distingue ativa, condicional, conflito e revisão pendente. `context_requirements` mantém condições externas explícitas e impede ativar uma regra revisada cuja condição de equipe/jogo não foi avaliada. Não produz uma média de tiers nem um score fictício.

## Idiomas

Nomes PT-BR e inglês são consultados pelo mesmo ID. O resultado informa a origem, o idioma realmente usado e se houve fallback. Ordem: idioma pedido → inglês → português → ID. Ausências e correspondências não resolvidas são listadas no relatório. As explicações de regras locais revisadas precisam dos dois idiomas; não há tradução automática por IA.

## Verificações executadas

```powershell
python -m unittest discover -s tests -v
python tools/data/pipeline.py verify
```

A suíte cobre semântica de métricas, ambiguidades de nomes, diferenças de patch, requisitos/alternativas/conflitos, bloqueio de regras após alterações, cobertura obrigatória, corrupção de arquivos, fallback de idioma, retomada de cache e preservação da publicação válida após erro. A base real também passa por integridade e chaves estrangeiras do SQLite.

Foram feitas leituras HTTP de verificação para OP.GG, Blitz e configuração de release ARAMKit, todas com HTTP 200. Também foi baixado e integrado o catálogo OP.GG em inglês (281 entradas), verificando patch e identidade contra o PT-BR. Isso não equivale a executar uma nova coleta completa das quatro fontes. As estatísticas publicadas nesta etapa vêm dos snapshots previamente preservados.
