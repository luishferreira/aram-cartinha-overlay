# Como testar caminhos e cartas offline

A versão atual **0.3.0** acrescenta o [módulo de apoio à decisão](card-evidence-module.md): cada carta apresenta efeito e indicadores das fontes. Feedback é opcional; não é necessário fornecer uma escolha correta. As regras de revisão descritas abaixo documentam a etapa anterior e não são um requisito para usar a bancada.

Versão da política: **0.2.1**. Base de dados fixada: `dc9801256aed94c6069941d5`.

Esta bancada testa o contexto e organiza as evidências. Ainda não calcula um ranking final nem tiers próprios S/A/B por build. Compatibilidade real continua desconhecida sem perfis mecânicos revisados; o campo `?` é esperado nesses casos. Cenários sintéticos de compatibilidade exercitam X/F/COND/OK separadamente.

## Três camadas de teste

1. **Contrato mecânico:** os 11 cenários sintéticos verificam vetos, condições, desconhecidos e prioridade da compatibilidade sobre tiers externos.
2. **Cobertura real:** 173 campeões e 433 caminhos nativos são conferidos. Para cada caminho, a bancada consulta três cartas como sondas e verifica que os perfis não vazam entre campeão/caminho/carta. Isso não valida a elegibilidade dessas cartas como oferta nem a qualidade da recomendação.
3. **Replays:** ofertas simuladas com IDs reais e evidências dos snapshots. Trocar caminho, comprar item, escolher carta e avançar etapa preservam o estado. A revisão humana define preferências esperadas; elas não são geradas a partir do mesmo win rate usado como evidência.

Ashe e Senna são exemplos legíveis para revisar o fluxo, não um recorte de cobertura do produto. O catálogo e o teste de caminhos cobrem todos os campeões coletados.

## Executar

Na raiz do projeto:

```powershell
python -m unittest discover -s tests
python tools/recommendation/policy.py --scenarios data/recommendation/scenarios/compatibility-0.1.0.json
python tools/recommendation/offline.py paths --champion champion:game:22
python tools/recommendation/offline.py replay --scenarios data/recommendation/scenarios/build-paths-0.2.1.json
```

O replay imprime o caminho absoluto do relatório. A execução inicial teve **3 cenários e 15 passos**:

- Ashe AP → efeitos ao contato → AP, com a mesma oferta.
- Ashe com Malignance comprada e uma carta escolhida, mudando depois para efeitos ao contato.
- Senna utilidade → crítico, com compra e carta preservadas.

As compras nos replays representam acontecimentos simulados de partida. Não implementam um editor de itens planejados ou personalização do caminho.

A revisão 0.2.1 corrigiu os exemplos anteriores que misturavam raridades. Todas as ofertas da suíte de revisão agora usam cartas da mesma raridade conforme o catálogo OP.GG, com validação automática. Isso ainda não prova elegibilidade por etapa, campeão ou possibilidade de aparecerem juntas numa partida real. As versões anteriores permanecem como histórico do protótipo.

## O que revisar no relatório

O Markdown mostra campeão, etapa, caminho, cartas já adquiridas e itens comprados. Para cada opção oferecida, apresenta compatibilidade conhecida/desconhecida, quantidade de perfis no caminho e um perfil ilustrativo com seus três itens, win rate e amostra.

O perfil ilustrativo é o de **maior amostra publicada**, não o de maior win rate. Não é uma recomendação de melhor build. Perfis de itens diferentes não são comparações controladas da eficácia das cartas. Não somamos amostras dos perfis. O JSON conserva as referências por fonte, incluindo patch, data, métricas, flags e artefato; referências gerais por campeão permanecem explicitamente sem condicionamento ao caminho.

Quando não há perfil da carta no caminho, a bancada mostra referências gerais quando existem. Isso não autoriza um veto, não cria win rate específico e não torna a carta ruim. Por exemplo, ADAPt tem perfis publicados em Ashe AP e nenhum perfil em Ashe on-hit neste snapshot; a falta do segundo caso não prova incompatibilidade.

Perfis condicionados a uma carta não descrevem automaticamente a combinação com todas as cartas atuais ou com os itens já comprados. Esses limites aparecem no JSON como `selected_augments_jointly_conditioned: false` e `current_items_conditioned: false`.

## Registrar uma decisão esperada

Ao lado de `report.md` ficam:

| Arquivo | Uso |
|---|---|
| `report.json` | Evidências completas e decisões de compatibilidade |
| `coverage-audit.json` | Auditoria de todos os caminhos selecionáveis |
| `manifest.json` | Hashes das saídas geradas |
| `judgments.json` | Preferências e justificativas humanas, editáveis |

Preencher em `judgments.json` a carta preferida (`preferred_candidate`), justificativa (`reason`), evidências faltantes (`missing_evidence`) e revisão (`review_status`). O estado inicial é pendente. Essas preferências são julgamentos a validar, não prova universal de resultado. Elas ficam separadas dos arquivos gerados e não são apagadas ao repetir a mesma execução.

Antes de olhar somente o maior WR, revisar:

1. A compatibilidade com o caminho e os itens reais faz sentido?
2. A carta tem utilidade própria ou depende de algo que ainda não existe?
3. Uma mudança de caminho seria viável considerando o estado preservado?
4. A evidência é específica o bastante para separar as opções ou deveria produzir empate/incerteza?

Essa revisão formará os casos esperados para desenvolver a primeira política de priorização. Hoje ainda não há medição de acerto de ranking: os campos `final_recommendation` e `strength_tier` ficam nulos, em vez de inventar uma resposta correta a partir dos próprios dados.

## Reprodutibilidade e escopo

O registro de caminhos preserva fonte, chave nativa, campeão, release e snapshot. Há de 1 a 5 caminhos gerais por campeão neste snapshot. Os 123 pares campeão/arquétipo encontrados apenas em perfis condicionais não são expostos automaticamente como caminhos gerais.

A política 0.2.1, o código, os testes, os cenários e o registro são preservados em `data/recommendation/releases/0.2.1/`, com manifesto em `releases/0.2.1.json`. As versões 0.1.0 e 0.2.0 permanecem disponíveis. Cada relatório registra os hashes da política, código, cenários e registro, além da versão de dados. Mesmas entradas produzem o mesmo identificador de revisão.

A assinatura dos fatos considera o caminho e, quando presentes, a versão de dados, versão da política, snapshot de caminhos, nível e revisão do perfil de capacidades. Fatos revisados para um contexto antigo não viram um veto válido após trocar de caminho. Não inferimos novas capacidades apenas pelo nome do caminho.

Nenhum cliente de jogo é aberto ou alterado, nenhum conjunto é importado no Arsenal e não há overlay. Atualização por novo patch continua adiada.
