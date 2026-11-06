# Dados locais e arquivos versionados

O Git contém as configurações e decisões editadas no projeto: `config/`, políticas/cenários de recomendação, revisões de classificação, julgamentos revisados, versões preservadas do código do classificador e `item-sets/export-exclusions.json`.

Bases SQLite, respostas das fontes, arquivos de entrada, resultados calculados, registros de caminhos, gerações de arsenais, pacotes de distribuição e dados pessoais ficam fora do Git. O `.gitignore` usa uma lista explícita de exceções para evitar que uma pasta de dados nova entre acidentalmente no primeiro commit.

Ignorar não apaga arquivos. Os dados completos continuam disponíveis nesta máquina. O Git sozinho não é o backup dessas coletas; os artefatos selecionados para distribuição devem ser anexados às releases, e a pesquisa completa precisa de backup separado.

O pacote distribuível está descrito em [Base de distribuição](../docs/runtime-data-pack.md). Ele tem catálogos, SQLite e todos os arsenais necessários à execução, sem incluir a pesquisa e os dados de sessão.
