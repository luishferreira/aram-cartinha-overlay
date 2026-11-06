# Arsenais estáticos — 02/11/2026

**Atualização em 06/11:** os arsenais agora comparam ARAMKit, OP.GG, Mayhem.com e LemonNation dentro de cada caminho. São 485 conjuntos em 173 campeões. Veja [a implementação e validação atuais](item-set-comparisons.md). O restante deste documento descreve a entrega original e sua evolução até a versão 2.

Primeira implementação de builds no jogo. Sem IA, Overwolf, alteração de recomendações durante a partida, compras automáticas ou mudanças em runas/feitiços.

## Fluxo entregue

1. `data/item-sets/current.json` seleciona a geração local de **433 conjuntos em 173 campeões**. Cada caminho publicado do ARAMKit recebe um conjunto estável.
2. Ao abrir `Iniciar Debug.cmd`, o overlay real inicia um worker de arsenais, independente do OCR/interface. O modo `--demo` nunca inicia a integração com o cliente.
3. O worker aguarda `ChampSelect` e **fila 2400**. Identifica somente a célula do jogador local e espera uma seleção estável por cerca de um segundo.
4. Importa todos os caminhos do campeão atual, geralmente um a cinco. Uma troca de campeão substitui apenas os conjuntos gerenciados pelo nosso aplicativo. Os outros conjuntos da conta são preservados.
5. Durante `InProgress`, carregamento ou outras filas, o worker não escreve. Os arsenais são estáticos para a partida; o jogador troca entre conjuntos já carregados pela loja.

A decisão inicial de preparar cobertura completa não significa importar os 433 conjuntos para a conta. O usuário esclareceu que quer a importação somente do campeão selecionado. Dessa forma, ficam apenas os caminhos do último campeão importado pelo aplicativo. Conjuntos legados em arquivos de outros apps não são alterados.

## Conteúdo e proveniência

O núcleo de cada caminho usa um perfil geral `filtered`, sem carta condicionante, escolhido por maior amostra. Dentro dele, usa uma rota de maior amostra cuja ordem contém exatamente os itens do núcleo daquele perfil. Não escolhe o maior WR. As alternativas adicionais podem vir dos outros perfis gerais do mesmo caminho, sem apresentá-las como uma única sequência de compra.

Na versão `static-item-sets-2`, os blocos são: início da rota principal; núcleo inteiro em uma linha, na ordem de compra; até cinco opções de botas observadas no caminho; até oito alternativas de núcleo dos outros perfis do mesmo caminho; até 12 opções posteriores observadas nas rotas desse caminho. Uma seção separada, `Outras opções de <campeão> · geral`, acrescenta até 12 itens lendários das estatísticas gerais `filtered/all` do campeão, sem afirmar que são específicos do caminho ativo. Itens repetidos nas seções principais não são repetidos nessa seção geral. Não misturamos itens de outros campeões ou condicionados a cartas.

Componentes iniciais repetidos viram contagem nativa. ID zero, publicado como opção sem botas, nunca é exportado como item. Botas e itens posteriores são alternativas, não uma sequência completa inventada de seis compras. A ordenação das opções usa a maior amostra publicada de cada item, sem somar aparições em rotas sobrepostas. Proveniência dos perfis e opções gerais é preservada.

A geração salva `item-sets.json`, um JSON por campeão/caminho, `provenance.json` e `preview.md`. O manifesto registra hashes e a base de origem. UIDs UUIDv5 são determinísticos por caminho, mantendo identidade em reimportações. A geração inicial foi `529a38ca1718560824dc6b88`; a versão ampliada é `18c122b5e8dbceba152107c6`, com a mesma base `dc9801256aed94c6069941d5` e os mesmos UIDs. A publicação anterior continua preservada.

Os nomes dos itens e ícones são exibidos pelo próprio cliente no idioma dele; nomes de caminhos/blocos nesta primeira versão são PT-BR. Os IDs específicos de Mayhem são preservados, sem converter para variantes normais por heurística. Na importação, todos os IDs precisam existir no catálogo da instalação. Isso valida identidade, não todas as condições de compra ou compatibilidade mecânica com cartas.

## Integração local

`tools/items/lcu.py` descobre a sessão do `LeagueClientUx.exe` pela metadata do processo/lockfile. Credenciais são mantidas somente em memória, fora de logs, argumentos e arquivos. HTTPS usa exclusivamente `127.0.0.1`, sem proxy ou redirecionamento; a exceção de certificado fica restrita ao transporte local.

O importador lê a coleção, separa UIDs conhecidos do projeto, preserva os demais e prepara a atualização. Relê a coleção para detectar edições concorrentes e confere conta/seleção imediatamente antes do PUT. Há uma pequena janela inevitável entre conferência e escrita: a LCU não foi tratada como uma operação transacional com outros aplicativos.

Um backup da coleção anterior é escrito **antes** de cada alteração, em `data/local/item-sets/backups/<hash-da-conta>/`. A resposta é conferida por nova leitura: UIDs, títulos, associações e blocos esperados, além dos conjuntos alheios. A reimportação idêntica não escreve nem duplica. Se o cliente rejeitar limites ou formato, o erro fica registrado; o aplicativo não remove conjuntos pessoais para abrir espaço.

`restore` recupera somente os conjuntos gerenciados anteriores ao backup e preserva conjuntos pessoais/de outros apps presentes no momento da restauração. Exige a mesma conta e um backup do diretório local do projeto.

## Comandos

```powershell
# Regenerar os conjuntos sem tocar no cliente:
python -m tools.items.cli export

# Estado da conexão e do worker, sem expor credenciais:
python -m tools.items.cli status

# Inspecionar proposta, sem gravação:
python -m tools.items.cli sync --champion 11

# Importação manual antes da partida:
python -m tools.items.cli sync --champion 11 --apply

# Worker separado, caso não esteja usando o overlay:
python -m tools.items.cli watch

# Restaurar os conjuntos do projeto a partir de um backup:
python -m tools.items.cli restore C:/Projects/lol-overlay/data/local/item-sets/backups/<conta>/<arquivo>.json
```

`Gerar Arsenais.cmd` e `Status dos Arsenais.cmd` oferecem os dois primeiros comandos por duplo clique. A importação automática acompanha o ciclo de vida do overlay real: Ctrl+F9/Parar Debug encerra também o worker. Não iniciar dois workers intencionalmente.

Estados ficam em `data/local/item-sets/status.json` e nos eventos `item_sets_status` da sessão do overlay. `last-import.json` aponta para o último backup após uma importação verificada. Esses arquivos são locais e ignorados pelo Git.

## Validação realizada

- Todos os 433 conjuntos gerados e validados, cobrindo os 173 campeões.
- Todos os **152 IDs** da versão ampliada existem no catálogo instalado, incluindo variantes específicas de Mayhem; a versão inicial usava 149.
- Importação real dos quatro conjuntos do Master Yi pelo cliente aberto, leitura de conferência, reimportação sem duplicação e restauração da coleção original verificadas.
- Testes de preservação de conjuntos pessoais, troca de campeão, backups/restauração sem apagar novos conjuntos alheios, conta incorreta, concorrência, IDs ausentes, seleção alterada, restrição à fila Mayhem e debounce do worker.
- O usuário confirmou a presença dos conjuntos na loja em partida com uma captura do arsenal de Nilah/Letalidade. A versão ampliada foi importada e conferida pelo worker durante uma seleção real de Gangplank (três caminhos). Uma troca de campeão na mesma seleção e a exibição das novas seções na loja ainda precisam de confirmação em jogo.

Não há atualização de patch nesta entrega. A base continua no snapshot já coletado; ler os IDs do cliente não atualiza as estatísticas nem resolve diferenças de versões entre fontes. Builds condicionadas às cartas, escolha de caminho no overlay, tradução dos blocos para inglês e sincronização do conjunto ativo da loja ficam para etapas futuras.

A sondagem posterior das [builds do Blitz](blitz-builds-research.md), em 06/11/2026, encontrou dados estruturados, mas as páginas Mayhem examinadas usam builds da fila 450. Após a comparação, o usuário decidiu excluir o Blitz das fontes de itens e builds, incluindo tiers de itens de Mayhem. A pesquisa fica arquivada; o Blitz permanece apenas como fonte de cartas. Os arsenais atuais continuam baseados no ARAMKit.

A [auditoria de outras fontes de itens em 06/11/2026](item-sources-audit-2026-11-06.md) ampliou o arammayhem.com para 3.126 opções em 173 campeões, comparou três pares de páginas do OP.GG, arquivou agregados recentes do MayhemStats e 66 builds editoriais do LemonNation. Esses dados permanecem na pesquisa separada; a geração e os arsenais existentes não foram alterados.

A [classificação automática de caminhos](build-classification.md) gera um artefato offline separado para organizar núcleos das outras fontes pelos caminhos do campeão. Preserva métricas, alternativas e casos ambíguos; ainda não participa da geração dos arsenais nem altera os conjuntos importados.
