# Keitinha Score — modelo 1.0.0

Implementado em 09/11/2026. Indicador de consenso de 0 a 100, calculado localmente ao consultar uma carta. Não é porcentagem de vitória, tier publicado, probabilidade de acerto ou avaliação de sinergia/build.

## Uma contribuição por fonte

| Fonte | Entrada | Peso com cobertura completa |
| --- | --- | ---: |
| ARAMKit | Tier do campeão | 25% |
| Blitz | Tier do campeão | 25% |
| arammayhem.com | Tier do campeão por raridade | 25% |
| OP.GG | Percentil de popularidade calculado para o campeão | 25% |

O tier OP.GG continua visível, mas não participa da nota. WR, amostras, popularidade CN, tier global e notas de combos não entram no cálculo. Os tiers de Mayhem têm cobertura parcial e escopo por raridade; esta versão usa as letras publicadas, sem alegar que as fontes compartilham critérios de classificação.

Tiers: S=90, A=70, B=50, C=30 e D=10; `+` acrescenta 5 e `−` retira 5. Letras desconhecidas não são convertidas em nota. A escala é uma convenção explícita do modelo, sem pressupor distâncias empíricas entre tiers.

## Popularidade

Usa todas as entradas publicadas não vazias do campeão, como o ranking OP.GG já exibido. Não usa somente as três opções oferecidas e não interpreta o campo bruto como pick rate percentual.

Para `N > 1`, converte a posição média do grupo de empate em:

```text
pontos = 100 × (N − posição_média) / (N − 1)
posição_média = rank_competitivo + (quantidade_empatada − 1) / 2
```

Sem empates, primeiro=100 e último=0. Empates recebem a mesma pontuação; quando todas as entradas empatam, ou há uma única entrada, a pontuação é 50. Uma população incompleta/inconsistente não é reescalada como se fosse completa.

## Média e cobertura

```text
Keitinha Score = soma dos pontos disponíveis / quantidade de fontes disponíveis
```

Sem fonte vira ausência, não zero; os pesos das demais fontes passam a `1/N`. Um zero observado de popularidade continua contando. Sem entradas válidas, mostra `—`. A cobertura é apresentada em `Comparar fontes` como `3/4 fontes`, por exemplo; não representa confiança estatística. Não há conversão para um tier próprio nem escolha automática de uma carta.

Exemplo dos snapshots: Tristana / O Boom e o Grave tem ARAMKit A=70, Blitz S=90, popularidade OP.GG #32/195=84,0206 e ausência de tier Mayhem do campeão. A média é 81,3402, exibida como **81,3**, com cobertura **3/4**. Trocar as cartas já adquiridas não altera esse consenso inicial.

## Runtime, cache e auditoria

O código fica em `tools/recommendation/keitinha_score.py`. O worker das fontes prepara o percentil por campeão uma vez e calcula a média ao carregar a carta, mantendo o cache existente. A interface recebe o resultado pronto; o OCR não espera pelo cálculo. O SQLite e o pacote de dados permanecem inalterados.

Cada `source-card-<campeão>-<carta>.json` registra `keitinha_score`: versão do modelo, nota sem arredondamento visual, fontes presentes, pontos, pesos e normalização da popularidade. A fórmula é versionada no código; não há configuração remota ou atualização automática de estatísticas. Mudar o modelo exige atualizar o app, mas não regenerar a base. Um novo snapshot muda as entradas utilizadas quando carregado pelo app.

O compacto preserva os quatro tiers originais e o Pick OP, acrescentando o score na mesma linha do pick. A comparação inclui a nota e a cobertura. Combos e notas contextuais continuam independentes, sem bônus inventados.

## Validação

- Igualdade de pesos, exclusão do tier OP.GG e de fallbacks globais, ausência versus zero, subtiers e entradas inválidas.
- Percentis da população inteira, empates, população constante, entrada única e rejeição de recortes incompletos.
- Isolamento entre campeões, resultados iguais com/sem cartas adquiridas e equivalência entre pesquisa e pacote compacto.
- Atualização do rótulo com a mesma oferta e limites de espaço dos painéis nativos em 1080p.
- Auditoria dos 173 campeões: 35.797 entradas OP.GG normalizadas, sem populações inconsistentes. Em um microbenchmark local de 20.000 cálculos da média, cerca de 2,1 microssegundos por cálculo; isso não mede a latência total de captura/OCR/consulta.
