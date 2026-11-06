# ARAMGG: API de desenvolvedor

Investigação em 30/10/2026, usando a conta e a chave existentes disponibilizadas pelo usuário. Nenhuma chave foi criada, rotacionada ou revogada. A credencial foi recebida em entrada oculta do terminal e usada somente em cabeçalho de autenticação para `data.dtodo.cn`; não foi gravada nos arquivos do projeto.

Fontes: [documentação da API](https://data.dtodo.cn/api/v1/en/docs/cf-data-api.md), [configuração pública](https://data.dtodo.cn/api/v1/en/config.json) e respostas reais preservadas em `research/aramgg-api/`. A documentação foi baixada como texto, sem executar código fornecido pelo site.

## O que muda em relação ao HTML anterior

Antes, tínhamos apenas as 20 cartas iniciais publicadas no HTML de cada campeão. A API disponibiliza o dicionário de cartas do campeão, incluindo ranking, popularidade e desempenho publicado, com metadados mais explícitos. O Master Yi, usado para verificar o formato expandido contra o bruto, retornou **132 cartas**, contra 20 na coleta HTML. O universo do projeto continua sendo todos os campeões.

A API também entrega até cinco **trios observados por campeão**, com vitórias, partidas e taxa de vitória. Isso acrescenta evidência de combinações de três cartas aos pares do ARAMKit e às explicações editoriais do arammayhem.com.

Nesta coleta, o catálogo tem **218 cartas**, **173 campeões** e **307 itens**. Das cartas, **214** têm estatística global e **4** aparecem sem estatísticas. Os campos de estágios existem no schema, mas nenhuma das 218 cartas deste release trouxe linhas por estágio. Não considerar uma funcionalidade documentada como uma cobertura já recebida.

A sincronização completa retornou **21.031 registros campeão/carta**, dos quais **19.641** têm desempenho publicado, e **527 trios em 127 campeões**. Os trios têm amostras de 151 a 1.130 partidas. Todos os 218 IDs de cartas compartilhados com o catálogo Blitz têm a mesma chave interna; não foram encontrados conflitos de identidade.

### O release atual também contém desempenho antigo

O envelope `gamePatch: 16.21` não se aplica automaticamente a todas as métricas internas:

| Evidência | Patch 16.21 | Patches anteriores |
| --- | ---: | ---: |
| Desempenho campeão/carta publicado | 19.303 | 338: 328 do 16.19 e 10 do 16.20 |
| Trios | 473 | 54: 53 do 16.19 e 1 do 16.20 |

Os outros 1.390 registros de carta não têm win rate publicada. O adaptador preserva os dados antigos com sua versão e os marca como históricos. A consulta contextual retorna `historical_evidence_not_current` para esses trios, sem promovê-los a recomendação atual. Essa é uma razão concreta para separar versão do release, patch do jogo e patch de cada métrica.

## Origem por métrica, não apenas por site

As respostas combinam evidências distintas:

| Conteúdo | Origem declarada | Contexto observado |
| --- | --- | --- |
| Ordem/tier e popularidade de cartas por campeão | Tencent | Região CN; data do snapshot base |
| Desempenho de carta por campeão | `aramgg-client-upload` | Região WORLD; patch/data próprios e contagem de jogos |
| Desempenho dos trios | `aramgg-client-upload` | Região WORLD; contagens e subconjunto selecionado |
| Builds de itens | iesdev, segundo a documentação | Exemplo recebido identifica fila 450; excluído de Mayhem |

No Yi, a ordem/popularidade identifica 28/10/2026, enquanto a taxa de vitória dos uploads identifica 29/10/2026. O adaptador mantém duas observações para cada carta, preservando essas origens, datas e regiões. Não colocar a win rate dos uploads sob o rótulo Tencent/CN.

O fornecedor declara mínimo de **255 jogos** para publicar desempenho de uma carta por campeão e **151 jogos** para trios, retornando no máximo cinco trios. Isso é uma política de publicação da fonte, não uma garantia nossa de representatividade ou independência entre partidas.

O dado não demonstra que o trio causa a taxa de vitória observada. Escolhas anteriores, momento da partida, duração e perfil de jogadores podem influenciar. Também não permite deduzir a taxa de vitória de uma quarta carta ou de todas as combinações ausentes.

## Exemplo concreto

No Master Yi, o trio **Ethereal Weapon + Mystic Punch + Pursuit of Haste** veio com **144 vitórias em 204 partidas**, taxa publicada de **70,59%**. Serve como evidência de um caminho de combinação que podemos investigar e exibir com sua amostra. Não deve virar uma previsão de 70,59% para a próxima partida.

As taxas individuais dessas três cartas são de outros subconjuntos. Comparar o trio diretamente à melhor carta isolada não calcula o ganho causal de sinergia.

## Builds: filtro necessário

O endpoint expandido do Yi retornou quatro variantes de build, todas com `queueId: 450`, e a documentação nomeia o caminho bruto como `HOWLING_ABYSS_ARAM`.

A [lista oficial da Riot](https://static.developer.riotgames.com/docs/lol/queues.json) distingue:

- **450:** ARAM normal.
- **2400:** ARAM: Mayhem.

Essas builds foram guardadas na pesquisa, mas **não foram importadas como recomendações de Mayhem**. O adaptador gera uma observação de qualidade sobre a exclusão. O catálogo de itens continua útil para identificação, descrições, custo e componentes; possuir um item no catálogo não é recomendá-lo.

## Idiomas e atualização

Há endpoints nativos em inglês, chinês simplificado/tradicional, japonês, coreano e vietnamita. PT-BR é um alias que retorna inglês; não é uma tradução nova. Mantemos PT-BR dos catálogos já integrados e registramos os nomes recebidos desta API como inglês.

O release desta coleta é **16.21.4**, com `gamePatch: 16.21`, `apiRelease: 4` e publicação em 29/10/2026. `dataVersion` pode mudar sem alterar o patch do jogo. O pipeline registra `source_release_changed` separadamente de `source_patch_changed`.

Consultar `config.json` não gasta créditos e permite decidir quando atualizar os arquivos. O coletor verifica novamente o release ao terminar, confirma hashes de arquivos já guardados ao retomar e não publica uma aquisição incompleta.

## Quota e coleta

O plano observado oferece **200 créditos/dia**, com **60 requisições/minuto**, reset às **00:00 UTC** (21h de Brasília na data desta pesquisa).

- Arquivo bruto por campeão: 1 crédito.
- Endpoint expandido por campeão: 2 créditos.
- Catálogo de cartas, catálogo de campeões ou itens: 1 crédito cada.
- Configuração e documentação: gratuitos.

A sincronização mínima de 173 campeões mais catálogos de campeões/cartas custa **175 créditos**. A coleta desta investigação inclui ainda itens, estatísticas globais e um exemplo expandido de Yi, totalizando **179 créditos**, deixando **21** quando concluída. O consumo real está registrado nos cabeçalhos de cada resposta do manifesto.

Para coletar ou retomar com a chave digitada sem eco:

```powershell
python research/collect_aramgg_api.py --key-prompt --sync-champions
```

A chave não deve ser colocada em argumentos, código ou arquivos. Não há agendamento ou cobrança paga configurados. A mesma pasta de release permite retomar sem pagar novamente pelas respostas íntegras já guardadas. Uma nova versão usa outro diretório.

Auditoria offline e publicação:

```powershell
python research/analyze_aramgg_api.py
python -m unittest discover -s tests -q
python tools/data/pipeline.py build
```

Quando a sincronização estiver completa, o adaptador ARAMGG usa a API no lugar do HTML limitado; não duplica ambos como dois votos. Dados de origem Tencent ou iesdev também não devem ser automaticamente tratados como independentes de outros agregadores que possam usar essas origens.

O arquivo `analysis.json` do release contém a contagem final por campeão, cobertura de desempenho/trios, checagem contra o exemplo expandido, conflitos de identidade e anomalias aritméticas. Acesso por chave documenta o canal de uso; uma licença geral de redistribuição não foi estabelecida por esta investigação.
