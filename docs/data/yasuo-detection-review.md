# Revisão do vídeo de Yasuo — 31/10/2026

Fonte: `C:/Users/Keita/Videos/obs/2026-10-31 12-09-30.mp4`, 1920×1080, 60 FPS, duração aproximada 229,4 s. Registros correlatos: `data/local/debug-overlay/runs/20261031T145433.060247Z`. Visão geral e trechos em `data/local/video-analysis/selection-120930`.

## Problemas encontrados

1. As leituras de títulos levavam aproximadamente 0,9–1 s desde a captura. Um nome parcialmente lido precisava esperar outra execução inteira do PowerShell; Voltando ao Básico demorou cerca de 2,5 s no registro após a mudança.
2. Um reroll tornava a classificação global do painel brevemente incerta/ausente e removia também etiquetas de cartas que não mudaram.
3. Um candidato de animação não era invalidado quando as outras cartas continuavam visíveis. O candidato do reroll central sobreviveu até a escolha real à esquerda. O bundle `visual-event-5/event.png` mostra o efeito em Sifão da Alma, mas a hipótese registrada era Voltando ao Básico. O tooltip posterior corrigiu essa hipótese.
4. Eventos de seleção usavam `at` para tempo monotônico e sobrescreviam a data UTC do logger. A informação foi preservada nos arquivos antigos; os eventos novos mantêm UTC e `monotonic_at` separados. O timestamp de exibição também passou a ser coletado após a atualização da janela, em vez de antes de aguardar seu bloqueio.

## Alterações e validação offline

- Processo de OCR persistente, com protocolo de identidade/timeout, entradas BMP, cache curto da API e diagnósticos PNG fora do bloqueio da captura/interface.
- Candidatos de animação rejeitados quando outras faces continuam presentes; expiração e atualização das referências após reroll estável.
- Etiquetas não alteradas preservadas durante uma incerteza global curta, exigindo que seus próprios ícones/títulos ainda correspondam.
- O replay do trecho 115–127 s passou a produzir somente uma escolha, à esquerda, aproximadamente em 124,53 s. A posição correta corresponde a Sifão da Alma.
- 180 frames reduzidos do trecho foram preservados como regressão em `tests/fixtures/yasuo-reroll`, cobrindo os dois rerolls e a escolha posterior. Exemplos anteriores prateado/prismático continuam nos testes.
- Benchmark do OCR persistente na captura real antiga: 641 ms na primeira chamada e 62/47/63 ms nas seguintes. No teste de salvar BMP + OCR + associação dos nomes dos frames deste vídeo: 609 ms na primeira chamada e 62/47/47 ms nas seguintes. Resultados em `persistent-ocr-benchmark.json` e `pipeline-benchmark.json` no diretório local do vídeo.

Esses números são medições offline, sem API/rederização do overlay nem carga da partida. Não estabelecem latência ou taxa de acerto ao vivo. Hipóteses antigas não foram apagadas silenciosamente dos históricos. A nova versão ainda precisa de novo teste em jogo.
