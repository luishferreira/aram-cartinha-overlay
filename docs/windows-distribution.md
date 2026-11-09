# Executável e instalador Windows

A versão publicada `0.1.0-alpha.11` empacota launcher e overlay com Python 3.12, Tkinter, Pillow e NumPy. O pacote de dados verificado e os retratos para a seleção visual e a consulta inicial também estão incluídos. A interface usa uma faixa compacta de status e busca incremental. O usuário final não precisa instalar Python, executar pip ou baixar/configurar a base separadamente. A [documentação do launcher](launcher.md) descreve a seleção e o gerenciamento de atualizações.

## Entregas

- **Setup x64:** instala por usuário em `%LOCALAPPDATA%\Programs\AramCartinhaOverlay`, cria atalhos e registra a desinstalação. Não solicita elevação administrativa.
- **ZIP portátil x64:** extrair a pasta inteira e abrir `AramCartinhaOverlay.exe`; `_internal/` e `data/` devem permanecer juntos do EXE.

Ambos usam `%LOCALAPPDATA%\AramCartinhaOverlay` para históricos, logs, capturas e backups dos arsenais. Atualizar ou desinstalar não remove essa pasta. Na execução pelo código-fonte, o layout anterior `data/local/` é preservado, sem migrar automaticamente dados do desenvolvedor para o pacote.

O instalador verifica os mutexes do overlay e da prévia para impedir alteração enquanto estão abertos. O atalho de abrir após instalar é opcional e não executa em instalação silenciosa. Não há inicialização automática com o Windows. O launcher consulta releases públicas, confere o hash do download e permite instalar por ação explícita fora da seleção/partida; uma nova versão pode ser instalada sobre a anterior com o app fechado.

## Compatibilidade e limites

Windows x64, versão 10 2004 ou superior. O reconhecimento continua calibrado para 1920×1080, borderless e PT-BR. O OCR depende dos idiomas/recursos do Windows; não são instalados automaticamente. O executável e o Setup ainda não têm assinatura de editor.

O pacote não contém a pesquisa, capturas de partidas, logs do desenvolvedor, credenciais ou backups da conta. O diagnóstico usa imagem de texto sintético, sem consultar ou alterar o LoL. A importação normal de arsenais mantém as proteções da versão anterior.

## Build local

Use um ambiente isolado no Windows x64 com Python 3.12:

```powershell
python -m venv data/local/windows-build-env
data/local/windows-build-env/Scripts/python.exe -m pip install -r requirements-build-windows.txt
data/local/windows-build-env/Scripts/python.exe -m tools.release.build_windows --iscc C:/caminho/do/InnoSetup/ISCC.exe
```

Foi usado PyInstaller 6.22.3 e Inno Setup 7.1.1 x64. O compilador Inno foi baixado da release oficial com verificação de hash e assinatura Authenticode válida de Pyrsys B.V. O script presume que o pacote de dados ativo já foi gerado/validado conforme [a documentação da base](runtime-data-pack.md).

Os fontes de empacotamento ficam em `packaging/windows/`. O resultado fica em `dist/<versão>/`, incluindo ZIP portátil, Setup, `SHA256SUMS.txt` e `build-manifest.json`. Os binários ficam fora do Git; são anexos de release. O manifesto registra commit e se havia alterações locais no build, sem alegar uma compilação binária determinística.

Os scripts PowerShell de OCR/captura são recursos explícitos do bundle. A execução de utilitários do Windows usa o caminho do sistema e limpa temporariamente a configuração de busca de DLLs do PyInstaller para o processo filho. Dependências Python são carregadas do próprio bundle.

## Diagnóstico e testes

```powershell
AramCartinhaOverlay.exe --self-test
AramCartinhaOverlay.exe --self-test --report C:/caminho/diagnostico.json
AramCartinhaOverlay.exe --demo
AramCartinhaOverlay.exe --stop
```

O diagnóstico testa Tk, dependências embarcadas, hashes do pacote, cartas, combos, nomes, os arsenais e o OCR do Windows. Não é uma partida simulada completa. `ARAM_CARTINHA_USER_DIR` permite isolar o perfil em testes ou compartilhar explicitamente um perfil durante a recuperação pelo código-fonte; exige caminho absoluto.

Verificações realizadas nesta máquina:

- alpha.9: 256 testes executados sem falhas, com dois testes de atalhos pulados por conflito com o aplicativo aberto;
- executável portátil testado com Python fora do `PATH` e sem variáveis `PYTHON*`, com dependências carregadas do bundle;
- diagnóstico do executável instalado, com 553 nomes normalizados, 485 caminhos e 173 campeões;
- prévia gráfica aberta e encerrada, com dados das fontes renderizados e sem erros;
- instalação, reinstalação e desinstalação em pasta de QA, com arquivo de histórico preservado fora da pasta do app.

Isso não substitui testar a versão instalada durante uma partida e em outro PC. O teste de PATH verifica independência do interpretador do sistema, mas a máquina de QA ainda tem os recursos de OCR já instalados.
