# Leitura automática de cartas — investigação de 30/10/2026

## Requisito de produto

O usuário exige reconhecimento automático. Digitar ou selecionar manualmente as três cartas não atende ao MVP. A detecção da oferta, suas mudanças por reroll e o acompanhamento da carta adquirida devem ser validados separadamente. Um atalho pode solicitar nova leitura, mas não substitui a detecção automática normal.

## Resultado: OP.GG standalone 3.2.0

Ser standalone e não instalar o cliente Overwolf separadamente é compatível com o uso de componentes integrados. A investigação não procurou nem identificou um cliente Overwolf separado; examinou o próprio pacote OP.GG e seus diagnósticos.

O REA reconstruiu o pacote instalado, selecionando `package.json` e `assets/main/main.js`. Uma inspeção focal dos bytes complementou o grafo. O caminho encontrado é:

1. O serviço GameEvents referencia `app.overwolf` e registra o gerenciador de pacotes.
2. Quando o pacote `gep` fica pronto, o serviço obtém sua API e solicita as features `jungle_camps` e `augments` para LoL.
3. O handler de `augments` nas keys `me` ou `augments` recebe os nomes oferecidos.
4. `createLoLMayhemGepEvent` normaliza os nomes e procura IDs no catálogo localizado do OP.GG. A requisição HTTP do catálogo resolve identidade; não fornece a oferta da partida.
5. A publicação exige três cartas reconhecidas com IDs positivos e usa o estado `lol:mayhem.gepEvent`.
6. O evento `picked_augment` publica `lol:mayhem.pickedAugment` e limpa a oferta ativa.

Os logs existentes corroboram uso histórico desse fluxo, além da presença estática no código. No arquivo `main.log` lido nesta investigação:

| Marcador | Ocorrências | Último registro observado |
| --- | ---: | --- |
| `[MAYHEM][GEP] confirmed mayhem augments` | 911 | 29/10/2026 22:39:34.655 |
| `[MAYHEM][GEP] picked augment` | 498 | 29/10/2026 22:39:36.417 |
| `package ready: gep` | 5 | 30/10/2026 14:56:08.803 |

Os horários são os textos do próprio log, sem inferência de fuso. Contagens incluem notificações repetidas; não representam ofertas únicas nem partidas. Esses são registros históricos produzidos pelo aplicativo, não uma captura ao vivo instrumentada por nós.

Isso sustenta que o caminho GEP foi usado nessa instalação standalone. Não estabelece o mecanismo interno de aquisição do GEP: OCR, memória, hooks ou outra técnica continuam desconhecidos. Não foi demonstrada uma API Riot acessível que forneça as ofertas. Também não foi encontrada uma implementação OCR no `assets/main/main.js`; essa busca negativa não cobre todo o produto.

## Comparação limitada: Blitz 3.0.17

O REA analisou `package.json`, `src/gameHandlers/lol/index.js`, `src/injection-manager.js` e `src/gameHandlers/lol/overlaySettings.js`.

O código de LoL seleciona uma DLL de overlay conforme versão do jogo e opt-in beta, declarando uma operação `dllToInject`. Há encaminhamento de dados de augments pelo IPC nativo. Isso demonstra uma arquitetura com componentes nativos e caminho de injeção no código; não demonstra execução atual, nem prova que as ofertas Mayhem sejam lidas por memória ou OCR. A direção de envio de avaliações para o overlay não deve ser confundida com aquisição das cartas oferecidas.

Não há base nesta investigação para afirmar que o Blitz lê a interface visual ou que sua rota de leitura já seja reproduzível por nós.

## Consequência para nosso MVP sem Overwolf

O caminho encontrado no OP.GG não atende à restrição de nenhuma dependência Overwolf. Não reutilizar seu GEP, suas DLLs nem exigir o OP.GG instalado para obter eventos.

A rota proposta para validar é captura local da janela do jogo, detecção automática da tela de escolha, recorte dos nomes, OCR local e correspondência no nosso catálogo PT-BR/inglês. Reconhecimento de ícones pode complementar o texto. Essa é uma proposta de implementação, não uma capacidade já demonstrada.

Antes de construir a apresentação completa, medir:

- identificação correta e ordem das três cartas, incluindo nomes parecidos e múltiplas linhas;
- estabilidade em frames consecutivos e rejeição de leitura incerta;
- atualização após rerolls e descarte da oferta antiga;
- identificação da carta realmente adquirida, separadamente da simples posição do clique;
- retorno de Alt-Tab, ocultação por outro overlay, resolução, escala do Windows e idioma;
- latência e consumo em partida, com detecção leve e OCR restrito à região necessária.

O app deve informar quando ainda não reconheceu a oferta, repetir a leitura automaticamente e evitar apresentar dados antigos como atuais. Correção manual pode existir como ferramenta de diagnóstico, mas não será considerada solução para o requisito de reconhecimento.

## Evidências preservadas e limitações

- `research/augment-recognition/installed-evidence-20261030.json`: hashes dos pacotes/membros, excertos com offsets de caracteres e resumo dos diagnósticos. Não contém logs completos nem credenciais.
- `research/inspect_augment_recognition.py`: coleta reproduzível, somente leitura dos aplicativos; recusa sobrescrever o snapshot existente.
- `research/augment-recognition/opgg-rea-summary.json`: recibo REA e limitações.
- `research/augment-recognition/opgg-rea-trace.json`: traço estático parcial, sem equivalência presumida a execução.
- `research/augment-recognition/blitz-rea-summary.json`: recibo REA da seleção Blitz.

REA OP.GG parent: `ev_37b953a76ec11485a4cb29fc2c00b66ee601f6530f9c61355daf7ff19b5af216`.

REA trace: `ev_b105aebf2e6daf7c97020994f4f4cacf01b714c25eb612d04a2332490b0da5b1`.

REA Blitz parent: `ev_5f782d58ff9e51bdc5689cab72dba2aa713fce0ca69ea698fbc4a039851a26b5`.

Os grafos têm cobertura parcial. No OP.GG, limites de relações semânticas e divergências entre metadados de integridade ASAR e alguns companions nativos foram reportados; os bytes foram registrados com `record-and-continue`, sem execução. A causa das divergências não foi estabelecida. Nenhum binário nativo foi executado, decompilado ou anexado ao processo do jogo nesta investigação. Não houve alteração dos aplicativos instalados.
