# LoL ARAM Mayhem — base local de dados

Projeto pessoal com base local de dados e primeiro overlay de debug para validar a captura de estado do jogo. Sem IA na primeira versão e sem Overwolf. O debug consulta o campeão pela API local, lê ofertas por captura/OCR e acompanha escolhas inferidas, antes de integrar o motor. League of Graphs e METAsrc ficam fora das cartas por enquanto; os arquivos de pesquisa permanecem preservados.

O fluxo reúne cinco fontes ativas (Blitz, OP.GG, ARAMKit, arammayhem.com e ARAMGG), preserva evidências e publica uma base SQLite local com suporte a PT-BR e inglês, diferenças por patch e fila de revisão.

Overlay: abrir `Iniciar Debug.cmd`; ocultar com `Ctrl+F8`; fechar com `Ctrl+F9` ou `Parar Debug.cmd`. Mostra campeão, histórico de escolhas com evidência e os [dados das cinco fontes sobre cada carta](docs/data/live-source-panels.md), usando a base local. Mantém tiers, desempenho e popularidade separados, sem vencedor automático. [Uso e limitações](docs/debug-overlay.md).

Arsenais: o overlay real também importa os caminhos estáticos do campeão selecionado no ARAM Mayhem, antes da partida, preservando conjuntos pessoais e de outros apps. Cobertura local: 485 caminhos em 173 campeões, com comparação de fontes dentro de cada caminho; importa somente os caminhos do campeão atual. A prévia não modifica o cliente. [Como funciona, comandos e backups](docs/data/static-item-sets.md).

Distribuição: a [base compacta do overlay](docs/runtime-data-pack.md) separa a pesquisa dos arquivos usados pelo aplicativo. O [executável e instalador Windows](docs/windows-distribution.md) incluem Python, dependências e os dados. A atualização automática por launcher continua como etapa futura.

Git: [arquivos versionados e dados locais](docs/repository-files.md). Um clone contém o código e as regras; os dados de execução serão distribuídos pelos assets das releases.

```powershell
python tools/data/pipeline.py build
python tools/data/pipeline.py status
python tools/data/pipeline.py verify
```

- [Fluxo, contrato, atualização e testes](docs/data/pipeline.md)
- [Decisões de arquitetura](docs/architecture-decisions.md)
- [Dados arammayhem.com](docs/data/arammayhem.md)
- [Análise do complemento MCP](docs/data/arammayhem-complement.md)
- [Coleta completa e persistência do MCP](docs/data/arammayhem-mcp-full.md)
- [API ARAMGG: cartas, trios, quota e origem das métricas](docs/data/aramgg-api.md)
- [Identidades, builds completas, combos e comparação entre fontes](docs/data/data-enrichment.md)
- [Política de recomendação e vetos de compatibilidade](docs/data/recommendation-policy.md)
- [Como executar e revisar os testes offline de caminhos e cartas](docs/data/offline-recommendation-bench.md)
- [Cartas com efeitos e indicadores para apoiar a decisão](docs/data/card-evidence-module.md)
- [Validação do campeão, ofertas e cartas adquiridas](docs/data/player-state-validation.md)
- [Pesquisa das fontes](research/README.md)

Não somar métricas de escopos distintos ou interpretar tiers de fontes diferentes como uma única escala. Licenças e limitações permanecem associadas às fontes.
