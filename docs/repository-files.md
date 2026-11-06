# O que entra no Git

O repositório guarda código, scripts de coleta/normalização, comandos de abertura, dependências declaradas, testes, documentação, configurações, políticas e decisões revisadas. Arquivos `.spec` de empacotamento poderão ser versionados quando forem criados.

Ficam fora dos commits:

- `data/local/`: capturas, logs, nomes visíveis de jogadores, histórico, dependências locais e backups dos arsenais da conta;
- SQLite e gerações em `data/pipeline/`, `data/runtime/`, `data/item-sets/runs/` e `data/build-classification/runs/`;
- coletas, respostas HTML/JSON, downloads e inspeções de aplicativos em `research/`, preservando scripts e relatórios escritos;
- entradas, resultados derivados, registros gerados e ponteiros para gerações ausentes no clone;
- fixtures de imagens capturadas de partidas em `tests/fixtures/tab-icons-yasuo/`, `visual-selection/` e `yasuo-reroll/`;
- ambientes virtuais, caches, executáveis/pacotes de release, credenciais e chaves privadas.

Os arquivos de dados e o futuro instalador/executável devem ser publicados como **assets de GitHub Releases**, separados do histórico do código. Esta configuração não publica arquivos, não altera a origem remota e não apaga nenhum dado local.

## Clonar e executar

Um clone contém os fontes, não os dados coletados. Para executar o overlay, será necessário instalar o pacote de dados da release correspondente no layout `data/runtime/`. O futuro launcher cuidará desse processo. Até lá, o preparo local está em [Base de distribuição](runtime-data-pack.md).

Os testes que usam dados reais ou capturas precisam dos respectivos dados locais. Testes sintéticos não dependem dessas capturas. Não trate um clone sem esses arquivos como se contivesse a base completa de pesquisa.

As regras atuais não removem arquivos que já estejam rastreados. Na auditoria inicial de 06/11/2026, `git ls-files` estava vazio, portanto não havia bases, imagens ou segredos para remover do índice/histórico. A origem já configurada foi preservada.

`.gitignore` evita inclusão acidental; não substitui revisar o conteúdo do commit, nem impede inclusão forçada com `git add -f`. Arquivos de exemplo de ambiente podem entrar, mas devem conter apenas valores fictícios.
