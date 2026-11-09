# Base de distribuição do overlay — 06/11/2026

O overlay agora pode consumir um pacote local separado da pesquisa. O pacote ativo, atualizado em 08/11/2026, é `2bcf3a910e6bdfeae25dc012`, derivado da base `dc9801256aed94c6069941d5` e dos arsenais `406cddcb5c5fbe18eaf7c88b`. Inclui a junção de núcleos repetidos, inícios sem poções no topo e uma linha de botas por caminho. Contém `launcher.json` com estatísticas de campeões e feitiços, mais os retratos oficiais em `champion-portraits.zip`; os dados de cartas permanecem iguais.

## Medidas

Tamanhos decimais, medidos nos arquivos gerados:

| Artefato | Bytes | Aproximadamente |
| --- | ---: | ---: |
| SQLite original de pesquisa | 4.350.971.904 | 4,35 GB |
| SQLite do overlay | 130.576.384 | 130,6 MB |
| Sete arquivos de dados descompactados | 139.996.143 | 139,8 MB |
| ZIP de dados, incluindo manifesto | 25.599.334 | 25,6 MB |

O SQLite ficou cerca de **97% menor**. Não era espaço livre acumulado: o original tem zero páginas livres. A maior parte do conteúdo era de perfis de builds e grupos de itens condicionados a cartas, cerca de 3,74 GB de valores armazenados, sem contar o overhead do SQLite. São recursos de pesquisa/futuro motor que o overlay atual não consulta. Os arsenais do aplicativo já estão calculados em JSON.

O diagnóstico por tabela e escopo está em `data/runtime/source-size-report.json`. Seus tamanhos por tabela são estimativas da soma dos valores, não ocupação física de páginas; `dbstat` não está disponível no Python desta instalação.

## O que o pacote contém

`data/runtime/runs/<geração>/` contém somente:

- `cards.sqlite3`: sete tabelas, com 128.015 observações, todas as 2.923 relações consultadas e os catálogos completos;
- `champions.json`: 173 campeões;
- `augments-ptbr.json` e `augments-enus.json`: nomes usados no reconhecimento;
- `item-sets.json`: todos os 485 caminhos e seus IDs de propriedade;
- `launcher.json`: tiers/win rates por fonte e combinações de feitiços para os 173 campeões, com proveniência;
- `champion-portraits.zip`: retratos dos 173 campeões e 34 ícones de feitiços do CDN oficial da Riot, com manifesto e hashes;
- `manifest.json`: hashes, versões, contagens, tamanhos e metadados das fontes.

As tabelas são `sources`, `snapshots`, `artifacts`, `entities`, `catalog`, `observations` e `relations`. Mantêm IDs, métricas, descrições, disponibilidade, fontes, patches, escopos, seletores e hashes de origem. Os arquivos originais apontados pelos hashes continuam no projeto de pesquisa, não no download dos amigos.

Observações são selecionadas para reproduzir as consultas atuais: cartas com ID nativo, informações gerais/do campeão e filtros de visibilidade já aplicados pelo leitor. Entradas históricas e por etapa que esse leitor não usa ficam na pesquisa. Todos os registros OP.GG usados pelo cálculo de posição de popularidade são retidos, mesmo quando não seriam exibidos individualmente. Pares, trios e conjuntos editoriais são copiados sem transformar seus significados.

Não entram nesse pacote os perfis de builds, grupos condicionais de itens, arquivos brutos, telas/vídeos de diagnóstico, logs, backups de conta, credenciais ou código/modelos de desenvolvimento do classificador. As exclusões significam que o pacote atende às funcionalidades atuais; novas funcionalidades podem exigir uma versão ampliada do formato.

## Uso e publicação local

```powershell
# Gera, compara, compacta e só então ativa o novo pacote local:
python -m tools.release.data_pack build

# Confere hashes e reproduz a comparação contra a pesquisa:
python -m tools.release.data_pack verify

# Testes do pacote isolado e das funcionalidades que o usam:
python -m unittest tests.test_runtime_data_pack tests.test_live_source_cards tests.test_static_item_sets tests.test_item_comparisons tests.test_build_classification -q
```

O build acessa a pesquisa somente para leitura, confere o hash original antes/depois e verifica integridade e referências do SQLite novo. Gera em staging, valida e publica `data/runtime/current.json` por substituição de arquivo. A geração depende dos dados e arquivos, não do horário. Uma segunda geração produziu os mesmos hashes de SQLite e ZIP.

Download preparado em `data/runtime/downloads/data-2bcf3a910e6bdfeae25dc012.zip`. SHA-256: `e99aaf5f33649236b95688e294b4b912c9578e5c6d378adfa6a5ca0943765fe6`.

O consumidor lê o ponteiro, verifica manifesto e arquivos e abre o banco em modo somente leitura. Um pacote presente mas inválido gera erro; não há fallback silencioso para uma base diferente. Na ausência de pacote, permanece o fluxo de desenvolvimento anterior.

O worker das cartas e os leitores de nomes usam o pacote ativo. O gerador dos arsenais e os leitores de pesquisa continuam usando o SQLite completo por padrão. Se um novo export de arsenais do desenvolvedor for mais recente que o pacote, ele tem precedência no ambiente de desenvolvimento; o pacote de distribuição só muda após sua regeneração.

## Validação

- Igualdade de todos os registros retidos, por tabela, usando contagem e hash das linhas ordenadas.
- **12.334 respostas iguais** entre base completa e compacta: todos os campeões, casos sem campeão/dados e todos os membros nativos dos conjuntos copiados, com contextos vazios, parciais e completos.
- Mesmas linhas renderizadas e mesmos nomes dos catálogos; regras de disponibilidade e contexto continuam no leitor original.
- Teste numa pasta contendo apenas o pacote, sem `research/` ou `data/pipeline/`: worker assíncrono, reconhecimento de nomes e carregamento dos 485 arsenais funcionam.
- Proteção contra arquivo adulterado, caminho inválido no manifesto e tentativa de gravação no SQLite.

O ZIP é **somente a parte de dados** da futura release. O executável, o launcher/updater, a organização dos dados pessoais no Windows e a publicação no GitHub continuam como etapas seguintes. Nenhum arquivo foi publicado no GitHub nesta etapa.
