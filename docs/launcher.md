# Launcher de pré-jogo — 08/11/2026

Implementado no mesmo processo do overlay; a versão publicada atual é `0.1.0-alpha.10`. Abrir pelo atalho do Iniciar mostra uma janela normal, com conexão com o LoL e importação de arsenais. Fechar pelo X minimiza; `Sair do app` ou Ctrl+F9 encerram tudo. Abrir novamente o atalho solicita que a instância existente reapareça, sem duplicar coletores/importadores.

A alpha.7 substitui os três blocos explicativos por uma linha de status: conexão, importação durante a seleção e aviso de overlay oculto somente quando aplicável. Remove rodapés de instrução, legendas de clique e o botão duplicado de minimizar. A busca filtra enquanto se digita, ignorando acentos e pontuação, e esconde os detalhes antigos quando não há resultados. O próprio campeão recebe o selo “Você”. Feitiços usam colunas de escolha/vitória; as fontes continuam separadas com seus patches. A versão instalada aparece na aba Atualizações, que mantém erros e ações de recuperação, sem explicações técnicas permanentes sobre downloads.

## Seleção e consulta

A alpha.10 corrige especificamente o ícone da barra de tarefas: `WM_SETICON` define os ícones pequeno e grande no HWND externo do Tk e reaplica após mapear a janela. Os testes e o diagnóstico leem `WM_GETICON`, sem se limitar à leitura do ICO. O arquivo `app.ico` também fica ao lado do EXE e é a origem explícita dos ícones dos atalhos. A identidade de processo é definida antes de criar a interface. Referências: [WM_SETICON](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-seticon), [WM_GETICON](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-geticon) e [AppUserModelID](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-setcurrentprocessexplicitappusermodelid).

A alpha.9 define a identidade de barra de tarefas `AramCartinha.Overlay` e aplica um ícone próprio às janelas, executável, instalador e atalho principal. `assets/app.ico` inclui tamanhos de 16 a 256 px; a arte original e sua geração ficam em `tools/release/app_icon.py`. Não depende do ícone padrão do Python.

A alpha.8 usa uma única barra vertical plana na consulta, sem setas ou grip. Os pares de feitiços são exibidos com ícones oficiais tanto nas recomendações quanto nos feitiços atuais; passar o mouse revela o nome em português. Os 34 ícones vêm do `summoner.json` pt_BR do Data Dragon 16.22.1 e ficam no mesmo ZIP verificado dos retratos, sem downloads durante o uso. A coleta é `python -m tools.release.launcher_assets spells --version 16.22.1`, seguida da regeneração do pacote de distribuição. Os testes verificam a rolagem até ambas as extremidades e a correspondência dos pares ao campeão consultado.

O leitor usa somente GET da API local: fase da partida, fila e sessão de seleção. Na fila 2400, lê `localPlayerCellId`, campeão e feitiços próprios, `myTeam`, `benchEnabled` e `benchChampions`. Não armazena o payload completo, chat, nomes de jogadores ou credenciais. Trocas e mudanças no banco são acompanhadas por consultas em segundo plano a cada segundo. Fila diferente não recebe estatísticas de Mayhem como se fossem daquele modo. Ao sair da seleção, as escolhas antigas são limpas.

A lista permite ordenar por tier (incluindo subtier), win rate ou nome e escolher a fonte principal entre ARAMKit e Mayhem.com. Clicar ou buscar um campeão consulta seus dados, sem mudar o campeão no LoL. Fora da seleção, os 173 campeões continuam disponíveis para consulta offline.

Na alpha.6, cada linha dessa lista também exibe o retrato de 32 px ao lado do nome, reutilizando as imagens já incluídas no pacote. Ordenação, seleção e métricas mantêm os mesmos IDs; não há nova coleta de dados ou imagens.

Na alpha.5, essa tabela fica exclusiva da consulta fora da seleção. Durante a seleção há uma faixa superior de retratos para o banco e outra com os cinco slots do time, mantendo a ordem enviada pelo cliente (inclusive slots vazios). Cada retrato mostra nome, tier e win rate da fonte selecionada. O campeão próprio tem contorno verde; o campeão consultado ganha contorno azul. Bancos extensos têm rolagem horizontal. Clicar no banco ou num aliado só atualiza o painel de consulta e seus feitiços; nenhuma troca é enviada ao LoL. Não há lista de builds nessa superfície de seleção.

Os 173 retratos do Data Dragon oficial da Riot, versão de imagens 16.22.1, estão incluídos no pacote e não são baixados durante o uso. As estatísticas continuam com seus próprios patches/datas. Fonte: `https://ddragon.leagueoflegends.com/cdn/16.22.1/data/en_US/champion.json`. A coleta guarda URLs e SHA-256 de cada PNG em `research/launcher-assets/16.22.1/manifest.json`. `champion-portraits.zip` tem esse manifesto e arquivos por ID nativo, conferidos na compilação offline. O diagnóstico do executável também decodifica e renderiza um retrato real.

O painel do campeão mostra as duas fontes separadas, seus patches, as três combinações de feitiços mais usadas no ARAMKit (popularidade e vitória) e os caminhos de build que o importador tem disponíveis. As datas e proveniências completas continuam no pacote salvo. São dados dos snapshots salvos; não existe atualização automática das estatísticas de patch.

A confirmação verde de arsenais exige campeão, geração de dados e PID do importador atual correspondentes. Um sucesso de uma execução/campeão anterior não confirma a seleção atual. O importador mantém suas proteções e backups, e continua restrito à seleção. Iniciar partida minimiza a janela; o overlay continua operando. Retornar do jogo reabre a janela sem iniciar novos workers.

## Dados distribuídos

O pacote atual `overlay-data-pack-3`, geração `2bcf3a910e6bdfeae25dc012`, acrescenta `champion-portraits.zip` ao `launcher.json` e aos cinco arquivos originais. O SQLite de cartas permanece byte a byte igual. O compilador verifica hashes dos 173 arquivos originais do ARAMKit antes de exportar feitiços e preserva as métricas, escopos, patches e proveniências dos campeões, sem gerar um tier combinado. A comparação offline confere o JSON inteiro e os retratos com a pesquisa, além das 12.334 respostas de cartas.

## Atualizações

O app consulta releases públicas de `luishferreira/aram-cartinha-overlay` ao abrir e pelo botão na aba Atualizações. Inclui prereleases e compara versões numéricas, sem depender do marcador Latest do GitHub. Drafts, versões antigas e releases sem Setup/checksums não são oferecidas.

O usuário baixa explicitamente o Setup e decide quando instalar. URLs são limitadas ao repositório configurado e aos hosts HTTPS de entrega do GitHub; os redirecionamentos também são verificados. Há limites de tamanho e conferência do SHA-256 de `SHA256SUMS.txt` antes de concluir o download e novamente antes de instalar. O hash verifica integridade conforme a publicação; não é uma assinatura de editor.

A instalação é bloqueada durante seleção, fila e partida. A fase é consultada novamente, e a presença do processo do jogo também é verificada. Com o LoL fechado, exige que o cliente e o jogo estejam ausentes. Um auxiliar aguarda o app encerrar, abre o instalador normal e reabre o aplicativo ao terminar. A pasta de históricos/backups é preservada pelo instalador existente. Não há instalação silenciosa automática, telemetria ou alterações nas configurações de segurança do Windows.

## Verificações

- Suíte completa na alpha.5: 253 testes, sem falhas; dois de atalhos pulados por conflito com atalhos em uso. Objetos Tcl dos testes são finalizados no thread que os criou antes dos testes com workers.
- Contratos de seleção, limpeza de estado antigo, fonte/ordenação, confirmação de importação, consulta sem trocar campeão e espaço da interface na dimensão mínima.
- Alpha.7: 23 testes focados de launcher/seleção/atualizador e apresentação compacta passaram; busca incremental, ausência de resultados e limpeza dos detalhes conferidas em Tk, com janela mínima de 1000 × 680.
- Alpha.7 instalada localmente com o LoL fechado; diagnóstico do executável aprovado (173 retratos/campeões, 485 caminhos, cartas, combos e OCR). Consulta e seleção simulada conferidas visualmente após a limpeza.
- Alpha.8: 20 testes de launcher/seleção/atualizador passaram. A instalação local e o diagnóstico confirmaram 34 ícones, cobertura/renderização de todos os feitiços usados na base e OCR funcional. O novo pacote reproduziu as mesmas 12.334 consultas de cartas sem alterar o SQLite original.
- Atualizador: versões alpha/beta/rc, drafts, origem dos downloads, corrupção de arquivo e bloqueio durante fila/seleção/partida. Consulta e download real da alpha.3, conferindo o hash publicado, sem executar esse instalador antigo.
- Diagnóstico do executável portátil: 173 campeões do launcher, feitiços, 485 caminhos, cartas/combos e OCR do Windows.
- Janela instalada conferida visualmente com cliente conectado. Usuário confirmou funcionamento durante seleção de Mayhem. Logs registraram importação de três caminhos de Gangplank e a janela minimizou quando começou a partida. O banco não foi registrado em um snapshot retrospectivo nessa sessão. O ajuste final de retorno pós-partida também foi validado por teste gráfico, incluindo queda de conexão transitória, PreEndOfGame e EndOfGame.

Histórico pessoal, contagem de partidas, win rate do usuário e inicialização automática com Windows ficam para outra etapa. Publicar uma release no GitHub continua sendo uma ação separada.
