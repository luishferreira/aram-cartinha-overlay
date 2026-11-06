# Animação de escolha: análise offline de 31/10/2026

Foram fornecidos dois vídeos de Ziggs em 1920×1080, nominalmente 60 FPS. Os arquivos originais foram copiados para `data/local/video-analysis/selection-20261031/video1/source.mp4` e `video2/source.mp4`; `manifest.json` guarda caminhos originais, SHA-256, regiões e anotações. São dados locais, sem depender de cache. Há montagens de visão geral, comparação e detalhes quadro a quadro em cada diretório.

## Evidência observada

| Vídeo | Carta na posição esquerda | Animação aproximada no arquivo |
| --- | --- | --- |
| `2026-10-31 11-10-18.mp4` | Alma Hextec | 14,38–14,72 s |
| `2026-10-31 10-55-54 - Trim.mp4` | Recursão Infinita | 34,73–35,17 s |

Os intervalos são anotações visuais aproximadas, não timestamps de clique. O primeiro efeito é branco/prateado e o segundo é prismático/colorido. Em ambos, o conteúdo das três cartas desaparece e um efeito se destaca na posição escolhida antes do fechamento. O hover anterior ilumina principalmente a moldura sem apagar os títulos e descrições. Os vídeos também contêm mudanças por reroll: qualquer detector precisa distingui-las de aquisição.

Como diagnóstico, contou-se a fração de pixels com todos os canais RGB acima de 160 no interior de cada carta. Na primeira posição, o limiar de 10% foi excedido em 14 amostras de 60 FPS entre 14,4000–14,6167 s no vídeo 1, e em oito amostras entre 34,8333–34,9500 s no vídeo 2. A janela inclui um intervalo de exposição por amostra; a diferença entre timestamps extremos não é a duração total da animação. Esses limiares foram examinados nos exemplos positivos e não constituem classificador validado. Métricas completas dos trechos estão em `detail-metrics.json`.

## Consequência para o coletor

A captura atual inicia um PowerShell e executa OCR em cada ciclo. As transições anteriores registradas mostram intervalos na ordem de segundos; isso é incompatível com depender de um efeito de poucas centenas de milissegundos. Melhorar apenas o OCR não resolve esse gargalo.

Proposta a validar offline antes de integrar:

1. Captura persistente e independente do OCR, com alvo inicial de 30 FPS na região das cartas e timestamps de captura.
2. Buffer circular curto para revisar abertura, hover, reroll, recolhimento e escolha.
3. OCR separado, associado à geração da oferta. Mudança por reroll invalida os IDs anteriores daquela posição.
4. Detector temporal que combina efeito localizado, perda do conteúdo das cartas e fechamento. Luminosidade isolada não basta.
5. Registro de aquisição como inferência visual; confirmação independente do estado adquirido continua pendente.

Os dois positivos são da mesma posição e do mesmo campeão. Ainda faltam escolhas nas posições central/direita, outras raridades, fechamento sem escolher e maior variedade de fundos. Não há taxa de acerto estimada nem teste em tempo real deste detector. Nenhuma mudança no overlay foi feita como parte desta análise. Esta evidência técnica não representa autorização da Riot para o uso do produto ou de captura/OCR.
