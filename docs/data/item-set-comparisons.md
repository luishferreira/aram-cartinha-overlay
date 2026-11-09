# Arsenais com comparação de fontes — 06/11/2026

Atualizado em 07/11/2026 com `static-item-sets-4`. A geração ativa é `406cddcb5c5fbe18eaf7c88b`, ligada ao classificador `112987fe81bd9f54056f7fb4` e à base `dc9801256aed94c6069941d5`.

## Conteúdo no jogo

São **485 conjuntos em 173 campeões**: os 433 caminhos originais e 52 caminhos principais adicionais sustentados pelas outras fontes. O dropdown continua separado por caminho. Compatibilidades secundárias acrescentam referências aos caminhos existentes; não criam um conjunto AD genérico para toda build que contenha AD.

Dentro de cada conjunto, os itens iniciais aparecem primeiro. Em seguida vêm os núcleos: primeiro ARAMKit, depois OP.GG, Mayhem.com e LemonNation, quando houver uma referência compatível. A segunda referência de uma fonte aparece depois da primeira das outras fontes. Exportamos até três sequências distintas por fonte estatística e até dois fluxos editoriais, antes de agrupar repetições. As alternativas adicionais e uma única linha de botas ficam abaixo.

- **ARAMKit:** perfis gerais `filtered` daquele caminho, ordenados por amostra; a ordem exibida vem de uma rota observada contendo exatamente o núcleo. Escolha/vitória pertencem ao perfil do núcleo, não necessariamente à rota específica. Os dados e denominadores de ambos ficam na proveniência.
- **OP.GG:** 173 páginas Mayhem, 2.595 núcleos disponíveis. Exibimos referências em sua posição publicada. Os percentuais continuam **gerais do campeão**; a classificação pelo conteúdo dos itens não recalcula as estatísticas para o caminho.
- **Mayhem.com:** 173 páginas, 865 núcleos. Mesma distinção entre classificação e métricas gerais. Não constitui uma amostra independente do MCP do próprio site.
- **LemonNation:** fluxos editoriais com nome da variante, sem inventar vitória/popularidade. A sequência é dividida em passos quando contém um grupo “escolha 1”; as alternativas ficam em um bloco próprio.

Os cabeçalhos estatísticos individuais mostram a fonte e os rótulos `escolha` e `vitória`. `geral` identifica os percentuais que não foram recortados por caminho. Núcleos idênticos de fontes estatísticas passam a uma única linha, com os nomes das fontes no título. Seus percentuais e escopos continuam individualmente em `origins`, sem média ou soma; não são concatenados no cabeçalho para evitar texto excessivo. Não exibimos contagem de jogos. O catálogo/idioma do cliente resolve nomes e ícones dos itens a partir dos IDs nativos.

Inícios com os mesmos IDs e quantidades são unificados entre fontes, independentemente da ordem dos componentes e ignorando poções (IDs 2003, 2004, 2031 e 2033). As poções são removidas da linha exibida e registradas em `display_omitted_potions`; os pacotes originais permanecem nos dados de origem. Outros consumíveis/componentes e suas quantidades não são ignorados. Linhas compostas apenas por poções não são exibidas.

Botas vêm de apenas uma fonte por caminho: ARAMKit quando disponível, depois OP.GG, Mayhem.com ou LemonNation. A lista escolhida conserva sua ordem e escopo, sem misturar rankings; as outras ficam em `undisplayed_alternatives` na proveniência. O título combinado dos inícios identifica fontes e respectivos escopos, e `origins` preserva cada evidência original.

A junção de núcleos exige IDs, quantidades e ordem idênticos. Inverter a ordem mantém outra linha. Fluxos editoriais e seus passos/alternativas não são unidos a núcleos estatísticos, preservando condições e grupos “escolha 1”. Na Ahri/AP, nove linhas viraram quatro núcleos, três inícios viraram dois (Capítulo Perdido e Bastão Desnecessariamente Grande), e quatro linhas de botas viraram uma. O total caiu de 20 para 12 blocos. Os 485 conjuntos/173 campeões e seus UIDs permanecem os mesmos.

As opções de itens continuam separadas por fonte. A posição publicada ordena listas do OP.GG e Mayhem.com; no OP.GG, o bloco geral de itens limita a seleção a IDs com custo catalogado de pelo menos 2.000, para reduzir componentes. Essas linhas são **alternativas**, não uma sequência observada de seis compras. Métricas e opções originais permanecem nos arquivos, inclusive itens não exibidos.

## Limitações explícitas

Os snapshots têm versões diferentes: Mayhem.com publica 26.21; OP.GG publica 16.22; o LemonNation não informa patch. Isso fica na proveniência, sem afirmar equivalência ou atualização automática. O trabalho de patches continua adiado.

Um núcleo do LemonNation para Vayne contém Stormrazor, ID 3097, ausente do catálogo instalado. O núcleo inteiro foi omitido, sem trocar o item ou apresentar uma sequência parcial como original. A decisão está em `data/item-sets/export-exclusions.json` e a geração registra o caso em `omitted-source-cores.json`. A validação de importação continua estrita para outros IDs ausentes.

MayhemStats não fornece núcleos conjuntos observados nos agregados coletados e fica fora dessas sequências. Blitz e builds ARAM normal continuam excluídos.

## Reprodutibilidade e importação

`research/item-sources/opgg-items-2026-11-06/` contém as 173 páginas originais, manifesto com hashes e normalização própria. A coleta anterior dos pares ARAM/Mayhem permanece intacta. A normalização adicional é reproduzível sem rede:

```powershell
python research/normalize_opgg_item_archive.py research/item-sources/opgg-items-2026-11-06
python -m tools.items.classification_cli build
python -m tools.items.classification_cli replay
python -m tools.items.cli export
```

O gerador verifica os hashes do classificador e dos arquivos normalizados antes de compor os blocos. `provenance.json` relaciona cada bloco nativo à fonte, escopo, opções originais, classificação e artefatos. `preview.md` lista todo o conteúdo exportado com nomes de itens. A geração anterior continua arquivada.

Os UIDs dos 433 conjuntos existentes são preservados. A identidade de um caminho novo segue a mesma regra, inclusive se ele ganhar uma referência ARAMKit no futuro. Um conjunto explícito dos UIDs possíveis do projeto permite remover caminhos nossos que deixem de existir, sem usar prefixos de título para identificar propriedade.

O worker mantém a restrição à seleção de campeão da fila 2400 e importa apenas os caminhos do campeão atual. Detecta uma nova geração e recarrega os dados; não tenta atualizar a loja durante a partida. Backups, proteção contra concorrência, preservação dos outros conjuntos e conferência por leitura continuam ativos.

## Verificações desta entrega

Na atualização de 07/11, os testes verificam a ordem dos inícios, ausência de poções, unicidade dos núcleos e limite de uma linha de botas em todos os caminhos. Também conferem a regressão da Ahri, a preservação de cada sequência/escopo original e das escolhas editoriais. O pacote de distribuição foi regenerado com a mesma base de cartas e comparação offline de 12.334 respostas.

Verificações da entrega anterior:

- **43 testes**: classificador, composição, deduplicação de inícios/botas, preservação de alternativas e escopos, migração de UIDs, recarga do worker e proteções do importador.
- Replay offline das **3.531 classificações**, incluindo a avaliação salva.
- Todos os **163 IDs** usados nos 485 conjuntos existem no catálogo do cliente conectado.
- Atualização real de **Aphelios/Crítico**, o campeão que já estava importado: 20 blocos aceitos, conferidos por leitura, e segunda simulação sem diferença. Backup salvo antes da alteração. Não havia conjuntos alheios nessa coleção; a preservação deles foi verificada pelos testes.
- A disposição visual das novas linhas dentro da loja ainda deve ser avaliada em partida. A API confirmou o conteúdo persistido, não o espaço ocupado na tela do jogo.
