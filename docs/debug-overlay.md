# Primeiro overlay de debug

## Abrir e fechar

- Executar `Iniciar Debug.cmd` na raiz do projeto.
- O painel aparece por alguns segundos ao abrir; depois acompanha a janela do LoL quando ela está em primeiro plano. Durante Alt-Tab fica oculto.
- `Ctrl+F8`: ocultar/reativar o painel.
- `Ctrl+F9` ou `Parar Debug.cmd`: encerrar.
- Na prévia, o botão `Fechar prévia ×` também encerra. Os atalhos são entregues por uma janela Windows própria de mensagens; em caso de conflito com outra instância, o registro é tentado novamente a cada dois segundos.
- `Preview Debug.cmd`: demonstração de 30 segundos, claramente marcada **SIMULAÇÃO**, sem consultar a partida.

Requer Windows, Python com Tkinter, Pillow, NumPy e OCR local do Windows. As dependências visuais ficam em `data/local/overlay-deps`; para prepará-las: `python -m pip install -r requirements-debug.txt --target data/local/overlay-deps`. Validado nesta máquina com Python 3.12/Tk 8.6 e OCR PT-BR. O leitor de ofertas está calibrado apenas para 1920×1080; alterações de escala/layout ainda precisam de teste. Não há Overwolf, serviço de IA nem consulta aos outros overlays.

O programa pode ser iniciado pelo terminal para ver erros diretamente:

```powershell
python tools/live/debug_overlay.py
```

O overlay é uma janela independente, sem ativação e com passagem de cliques. Não lê memória do jogo, não injeta módulos e não controla mouse/teclado. A captura de botões está desativada nesta versão, enquanto a permissão da Riot para observação de inputs permanece pendente. Apenas a posição do cursor é consultada para associar um tooltip já visível ao ícone da sua própria linha no TAB. Os atalhos registrados são próprios do debug.

## O que aparece

O modo real também inicia a [importação de arsenais estáticos](data/static-item-sets.md) na seleção de campeão do Mayhem. Abra o overlay **antes** de entrar na seleção. A prévia não inicia essa integração. A importação não ocorre durante a partida.

1. Nome do campeão obtido pela API local.
2. Histórico de escolhas detectadas abaixo do campeão, com `~` para inferências da animação e `✓` para identificação por ícone ou nome na própria linha do TAB. O arquivo de estado distingue `visual_icon` de `visual_name`; nome lido continua sendo a evidência mais forte.
3. Atalhos de ocultação e saída. A oferta aparece somente nos painéis acima das cartas.

Há três cabeçalhos independentes de 310×78 acima das cartas nativas, centrados em x=592/960/1328 e y=108–186 no cliente 1920×1080. Eles mostram tiers por fonte (AK ARAMKit, BL Blitz, OP OP.GG e AM arammayhem por campeão/raridade) e pick OP.GG, sem criar tier agregado. A legenda fica no histórico lateral. Os nomes permanecem nas cartas nativas. Os dados são consultados por um worker separado; a identificação parcial de uma posição já permite mostrar seu cabeçalho. O rastreador continua exigindo duas leituras completas para registrar a oferta estável.

Os combos ficam em janelas de 310×100 em y=808–908, abaixo dos botões nativos de reroll, fora dos títulos/ícones nativos e das regiões usadas para detectar seleção. `Comparar fontes`, abaixo do histórico, abre uma tabela de 1046×260 em x=437 e y=816, com tiers, WR por fonte, popularidade ARAMKit, pick OP.GG e WR de conjunto observado completo. Enquanto a comparação está aberta, os resumos de combos ficam ocultos para não se sobreporem à tabela. Sem quantidade de jogos, índice OP.GG, popularidade CN ou tiers globais. `Fechar ×` ou o mesmo botão recolhe a comparação. O painel se fecha quando a oferta termina. Apenas o botão e a comparação recebem cliques normais nas próprias janelas; usam `WS_EX_NOACTIVATE` para preservar o foco do jogo. Os indicadores, combos e histórico continuam passando cliques. Não há hooks, captura de novos inputs globais ou novos atalhos.

Na execução real, `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` exclui as janelas do overlay da captura, evitando que textos da comparação/combos sejam confundidos com tooltips do jogo. A aceitação por janela é registrada em `overlay_capture_exclusion`; validada nesta máquina com afinidade 17 e captura de tela. Isso também pode ocultar o overlay em gravações/capturas externas. No modo de prévia essa exclusão fica desligada, para permitir imagens de revisão.

As etiquetas passam cliques, acompanham a posição da janela e obedecem a Ctrl+F8/Ctrl+F9. São retiradas ao perder a oferta ou ao detectar mudança no ícone/título da posição; resultados OCR antigos são comparados à imagem atual antes de reaparecerem, para evitar nomes de um reroll anterior. Ficam fora da faixa de OCR dos títulos nativos.

Os eventos `offer_tag_detected` e `offer_tag_visible` medem, por posição, o intervalo desde o primeiro frame do painel/mudança, desde o frame enviado ao OCR e desde a identificação até a atualização da etiqueta. São tempos do coletor/interface, não uma medição física da apresentação do monitor. Eventos de preview têm `demo=true` e não medem reconhecimento. A velocidade real em partida ainda será medida nos novos testes.

O painel compacto tem largura de 300 pixels e altura ajustada ao conteúdo, sem mensagens de espera, IDs, nível ou diagnósticos. `—` indica campo vazio; `?` indica uma leitura antiga. Uma escolha pendente acrescenta apenas `? validar no TAB + mouse`. Detalhes técnicos continuam nos arquivos locais. Um futuro modo de edição com o mouse foi solicitado como evolução; ele ainda não está implementado.

Há tiers e indicadores publicados pelas fontes, sem tier agregado, vencedor automático, ajuste por caminho de build ou integração com a loja. A janela usa Python/Tkinter para aproveitar o coletor já existente; essa escolha não fixa a tecnologia da interface final.

Os painéis também exibem recomendações contextuais em verde: pares/trios observados com suas cartas e notas de combos do arammayhem.com para o campeão. `Falta` identifica membros necessários para completar um conjunto estatístico; `Outras citadas` apenas reproduz membros editoriais, sem afirmar que são requisitos. Mais detalhes em [Dados das fontes nas cartas](data/live-source-panels.md). O preview usa Master Yi para demonstrar esses três tipos de evidência, com cartas nativas ilustrativas e marcação SIMULAÇÃO. As cartas ilustrativas nunca são criadas durante a execução real.

## Precisão das escolhas

As ofertas exigem duas leituras OCR consecutivas da mesma combinação. O OCR usa um recorte da faixa dos títulos ampliado em 2×, com coordenadas convertidas para a tela original. A leitura visual funciona mesmo enquanto a API local ainda estiver indisponível. O painel de debug fica à esquerda das regiões nativas de títulos para não se reconhecer acidentalmente como fonte de dados. A detecção de painel aberto/fechado usa amostras de cores da moldura e do corpo das três cartas, além do OCR.

A captura visual agora roda separada da API e do OCR, com alvo de 30 FPS (a taxa efetiva é registrada). Mantém um buffer circular de 60 recortes em memória. A velocidade efetiva depende da máquina; o alvo não é uma garantia. O classificador do painel reconhece também as bordas cinza das cartas prateadas.

O OCR usa um processo PowerShell persistente, com timeout e identidade por requisição. O processo é encerrado junto do overlay e reiniciado se falhar; a primeira leitura ainda paga a inicialização. Os frames de entrada usam BMP, e a compressão dos PNGs diagnósticos ocorre apenas quando a leitura muda, fora do bloqueio da interface/captura. A API do campeão é consultada no máximo uma vez por segundo. Isso evita inicializar PowerShell e compilar os tipos de captura a cada leitura.

As camadas ativas são:

- **Animação:** aumento localizado de brilho em duas amostras, seguido de ausência do painel. O efeito é associado à posição somente quando os ícones imediatamente anteriores ainda correspondem à oferta lida; uma mudança parcial de ícones invalida a associação anterior para evitar reutilizar uma posição após reroll. Continua sendo inferência experimental.
- Um candidato de animação é descartado se as faces das outras cartas continuam visíveis ou se expira. As referências são atualizadas após rerolls estáveis; um candidato de reroll não deve sobreviver até uma seleção posterior. Uma incerteza curta do classificador global não apaga as etiquetas das posições cujo título e ícone continuam iguais.
- **Ícones no TAB:** o OCR localiza sua linha pelo nome obtido da API. Os ícones dessa linha são comparados às referências guardadas de todas as ofertas observadas, incluindo rerolls. A comparação testa pequenas variações de escala e alinhamento, excluindo as molduras do TAB. Resultados para imagens iguais ficam em cache. Exige similaridade mínima, margem sobre o segundo candidato e três amostras consistentes. Ícones empatados permanecem desconhecidos. Referências de ofertas já salvas são restauradas após reiniciar, sem depender de ensinar os ícones por hover. O app não abre o TAB.
- **Tooltip como fallback:** abra o TAB e passe o mouse sobre o ícone na sua própria linha, mantendo o nome visível até a leitura (inicialmente cerca de 3–5 segundos). Duas capturas OCR com o mesmo nome e posição validam a identidade. A busca usa o catálogo PT-BR/EN completo, inclusive para ofertas não vistas. Exige que a posição do cursor corresponda à célula identificada como sua; tooltips de outros jogadores não são aceitos. O nome corrige hipóteses anteriores quando sua associação é única; o motivo e o valor anterior ficam salvos. Uma inferência posterior não substitui um nome já lido.

Fechamento isolado não registra uma carta. Ofertas observadas sem identificação final continuam pendentes e podem ser recuperadas depois. Uma oferta que nunca foi vista e não produziu animação detectada só poderá ser recuperada pelo TAB. O agrupamento de rodadas por nível/intervalo é heurístico; em caso de dúvida, as alternativas são preservadas.

O histórico pode estar parcial, principalmente quando o debug abre no meio da partida. Se já houver histórico salvo pelo próprio debug para esse processo, ele é restaurado. A identidade usa PID e instante de criação do processo do jogo; não reutiliza cartas porque o campeão é o mesmo. As ofertas, escolhas, correções e pendências são persistidas. Os ícones aprendidos são separados por processo.

Estas camadas identificam informações visíveis e não representam aprovação da Riot do produto. A validação de políticas continua separada da validação técnica. Nenhuma carta deve ser tratada como estado fornecido diretamente pelo jogo/API.

## Dados locais

As consultas às fontes agora preferem a [base compacta de distribuição](runtime-data-pack.md), quando há um pacote válido em `data/runtime/current.json`. Pesquisa e geradores continuam separados. Os dados de sessão listados abaixo são pessoais e não entram no pacote.

Em `data/local/debug-overlay/`, ignorado pelo Git:

- `state.json`: último histórico persistido;
- `matches/<identidade>.json`: histórico por processo de partida;
- `runs/<sessão>/events.jsonl`: mudanças, diagnósticos de aquisição e hipóteses de escolha; fragmentos OCR podem incluir nomes visíveis quando o painel de cartas está fechado;
- `runs/<sessão>/latest-frame.png`: última captura da sessão;
- `runs/<sessão>/first-offer.png` e `.json`: primeira oferta reconhecida na sessão;
- `runs/<sessão>/failed-offer-0` até `failed-offer-7`, em PNG/JSON: amostras rotativas de leituras incompletas com painel detectado aberto;
- `offers/<processo>/`: referências dos títulos e ícones de cada combinação, incluindo rerolls;
- `icons/<processo>/`: variantes dos ícones aprendidos;
- `runs/<sessão>/visual-event-0` até `visual-event-7`: bundles rotativos com captura do evento e amostras anteriores;
- `startup-error.log`: erros de abertura, quando houver.

Os eventos `source_cards_ready`/`source_card_visible` identificam a versão da base e o tempo de consulta dos dados. `runs/<sessão>/source-card-<campeão>-<carta>.json` conserva o último contexto exibido para o par, com métricas, artefatos, patches, datas e texto editorial completo.

As imagens podem conter chat e nomes visuais do jogo. O debug não arquiva um vídeo nem todos os frames continuamente. Os snapshots históricos da pesquisa anterior permanecem preservados em seus diretórios originais.

## Validação desta versão

- Testes focais de identidade, leitor de títulos e transições de escolha.
- Preview real da janela inspecionado por screenshot; os estilos `layered`, `transparent` e `no-activate` foram conferidos.
- O reconhecimento de campeão e títulos reaproveita o teste real anterior, em Lillia, descrito em `docs/data/player-state-validation.md`.
- Na partida de Shaco de 31/10, a segunda oferta e a escolha de Mestre das Tropas foram registradas. O usuário relatou falha na primeira oferta; a captura correspondente já havia sido sobrescrita, então a causa permanece não confirmada. O recorte ampliado passou no replay de duas capturas reais anteriores, inclusive com título em duas linhas. A primeira oferta de uma nova partida ainda requer novo teste.
- Os testes automatizados cobrem aquisição sem API, chegada posterior do campeão, migração do histórico e transições controladas, sem estabelecer confirmação pelo HUD.

## Validação das camadas visuais

O replay integral dos dois vídeos fornecidos, amostrado a 30 FPS, produziu um evento na posição esquerda em cada vídeo e nenhum evento extra nos trechos de hover/reroll. Resultado em `data/local/video-analysis/selection-20261031/detector-replay.json`. Cinquenta frames reais foram preservados em `tests/fixtures/visual-selection` e testam também a associação do efeito aos IDs da oferta, em cartas prateadas e prismáticas. Um ícone real de Engenho do Encolhimento foi associado da oferta à própria linha do TAB; um tooltip real de Pacto Nefasto foi reconhecido e recusado quando atribuído a outra linha.

Também há testes de correção, restauração, empate de ícones, posição central/direita com eventos sintéticos, fechamento isolado, flash global e aquisição sem API. Esses testes não estabelecem taxa de acerto em partidas. As posições central/direita ainda precisam de exemplos reais; o sistema precisa ser validado em execução com as novas capturas.

Na revisão dos ícones de Yasuo, as referências da oferta com recorte fixo não passavam nos limiares do TAB. A regressão `tests/fixtures/tab-icons-yasuo` usa apenas 21 referências de ofertas e um recorte da própria linha: a comparação ajustada reconhece Zelote e Sifão da Alma sem aprender pelo hover; Enfeitiçamento Coletivo permanece ambíguo contra outros ícones de espada. Não se reduziu a margem para forçar essa identificação. Os eventos `tab_read` agora registram duração do OCR, localização da própria linha e estabilidade do nome lido, para separar lentidão de falhas de associação.
