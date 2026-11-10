# Falhas em outro PC — 10/11/2026

Análise do `events.jsonl` fornecido pelo usuário: sessão de 03:17:22 a 03:45:24 UTC. A base compacta, as janelas e os atalhos inicializaram. Houve 151 registros de captura (mediana de 18,6 FPS), quatro animações de escolha com identidade desconhecida e nenhuma publicação de carta reconhecida.

## OCR

O processo auxiliar encerrou 257 vezes com `RuntimeError: OCR worker exited`. A versão alpha.12 descartava o stderr, portanto o arquivo não prova a causa do encerramento. Não há evidência suficiente para atribuí-lo a um antivírus ou à ausência de idioma.

Reprodução local: com `PSExecutionPolicyPreference=Restricted` apenas no ambiente do teste, o comando antigo do script termina com código 1 por execução de scripts desabilitada. O comando ajustado, com `-NonInteractive -ExecutionPolicy Bypass`, reconhece `TESTE CARTINHA` usando o OCR pt-BR. A política é aplicada somente ao processo auxiliar; não se executa `Set-ExecutionPolicy` nem se altera a política persistente do Windows. Políticas organizacionais e bloqueios de segurança podem continuar impedindo o processo.

O lançamento do worker e a captura avulsa passam a usar o mesmo comando. O worker mantém stderr limitado em memória e inclui a saída e o código de término na exceção. Falhas retornadas pelo próprio Windows OCR agora também são registradas como erro; repetições idênticas são deduplicadas até recuperação ou troca de partida.

## Arsenais

O cliente foi encontrado e houve uma tentativa de importação recusada com HTTP 413. O log antigo não inclui o endpoint, o método ou o tamanho; não permite confirmar qual requisição foi recusada nem o limite efetivo.

As requisições com corpo passam a usar JSON compacto em UTF-8, preservando campos, ordem dos itens e conjuntos de outros apps. O objetivo é reduzir o tamanho transmitido, sem excluir arsenais existentes. Isso **não garante** que uma coleção grande caiba no limite. Nos conjuntos gerados locais, a maior coleção de um campeão cai de 17.983 para 15.098 bytes; a coleção real do amigo pode ter outros conjuntos e tamanho muito maior.

Novos erros LCU incluem método, endpoint com ID de conta mascarado, bytes enviados e quantidade de conjuntos. Nenhum corpo, título de arsenal ou credencial é adicionado ao diagnóstico. O watcher conserva o erro em `item-sets/status.json` e no evento `item_sets_status`; não anuncia importação concluída após falhar.

## Validação pendente

Testar a versão com esses ajustes no PC afetado. Se o 413 continuar, usar os metadados novos para escolher uma estratégia que preserve os arsenais de outros aplicativos. Não houve nova coleta de estatísticas nem mudança nos arquivos do LoL durante esta análise.
