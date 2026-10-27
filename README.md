# IdleFarm 0.3.0 · um canto para cultivar

Jogo incremental de fazenda para desktop, em **Python 3.12 + PySide6**.
Cinco culturas, cinco instalações, doze espécies/raças e seis ambientes originais
em pixel art **512×288**. Campo cultivável e cinco interiores detalhados,
72 quadros de animais, iluminação por janelas e lanternas, progresso offline
e salvamento compatível com as versões 0.1.0 e 0.2.0.
O jogo funciona sem internet.

## Ambientes

![Os seis ambientes durante o dia](docs/screenshots/gallery-day.png)
![Os seis ambientes à noite](docs/screenshots/gallery-night.png)

## Jogar no Windows

**[Baixar IdleFarm.exe · Windows 64 bits](https://github.com/BernardoJ/IdleFarm/releases/download/v0.3.0/IdleFarm.exe)** · [Release e checksums](https://github.com/BernardoJ/IdleFarm/releases/tag/v0.3.0)

O workflow [Windows x64](.github/workflows/windows-release.yml) gera
`IdleFarm.exe` e, para tags de versão, publica o arquivo e `SHA256SUMS.txt` na
aba [Releases](https://github.com/BernardoJ/IdleFarm/releases).
Uma release só é criada após testes, build e duas inicializações do próprio
executável no Windows. A existência deste código não comprova que o workflow
já executou: confira a execução em [Actions](https://github.com/BernardoJ/IdleFarm/actions).

Baixe o executável, salve em qualquer pasta e abra com dois cliques. Não precisa instalar Python. O save fica em
`%APPDATA%\IdleFarm\save.json`; mover o executável não move nem apaga o progresso.
O executável não tem assinatura de código nesta versão.

## Começar sua fazenda

- Você começa com **50 moedas e dois terrenos**. Selecione um terreno, escolha
  trigo ou cenoura e clique em **Plantar**. Em uma fazenda nova, o primeiro
  trigo cresce em **60 segundos**, com o custo e a recompensa normais. Colha-o
  e reinvista as moedas. Os próximos trigos levam uma hora; o benefício não
  se repete ao reabrir nem altera plantações de saves antigos.
- Milho, morango e abóbora desbloqueiam com receita acumulada, sem gastar moedas
  no desbloqueio. A colheita permanece manual, mesmo depois de vários dias fora.
- O jogo sempre abre nas **Plantações**. Use o menu **Áreas da fazenda** para
  visitar galinheiro, celeiro e as demais instalações. Somente a área selecionada
  e seu gerenciamento são exibidos por vez.
- Compre terrenos nas plantações e construa instalações em suas respectivas
  áreas. Cada terreno funciona de verdade; cada animal produtivo tem seu próprio
  ciclo de pagamento, mesmo enquanto você visita outra área.
- O preço de novas unidades da mesma espécie sobe 12%. Isso incentiva diversificar
  a fazenda, sem limitar o número de animais. As expansões sobem 35%.
- Cachorros são companheiros: **não produzem moedas**.
- Animais produzem enquanto você joga. Ao reabrir ou retomar após suspensão,
  a produção monetária de cada ausência conta até **quatro horas**. Ticks
  regulares continuam acumulando normalmente durante sessões longas.
  O crescimento de plantações conta todo o tempo real, sem esse limite.
- A cena mostra até **cinco representantes**, priorizando culturas e espécies
  diferentes e incluindo o terreno selecionado, mesmo que esteja livre.
  O destaque corresponde ao terreno escolhido; cliques em sobreposições
  selecionam o canteiro da frente. Esse limite não afeta produção ou propriedade.
- Arraste a cena ou a barra da janela para movê-la. **Sempre no topo** é opcional;
  **Ocultar gerenciamento** reduz a janela para acompanhar a fazenda enquanto trabalha.
- Sem dinheiro para trigo, sem plantações e sem animais produtivos, o botão
  **Sementes de recomeço** garante uma retomada sem bloquear a progressão.

[Tabela econômica completa e análise de retorno](docs/ECONOMIA.md).

## Administrar fazendas maiores

- Ative **Prontas** para localizar as colheitas disponíveis. O terreno selecionado
  continua na lista, com indicação quando estiver fora do filtro.
- Use **Próximo livre** para avançar em ordem pelos terrenos disponíveis. Ao
  chegar ao último, a busca volta ao início; terrenos ocupados são ignorados.
- Em **Ações em lote**, escolha **Colher prontas** para recolher todas as
  plantações maduras e ver o total de moedas recebido.
- Escolha **Plantar terrenos livres** para revisar cultura, quantidade, custo
  e saldo antes de **Confirmar plantio**. Se não houver dinheiro para todos,
  a proposta mostra a quantidade que você pode pagar. Cancelar não cobra nada.
  Se o saldo ou os terrenos mudarem, os valores precisam ser conferidos novamente.

## Salvar e recuperar seu progresso

O indicador diferencia **Tudo salvo**, **Salvando…**, **Alterações não salvas**
e **Erro ao salvar**. O sucesso aparece somente após uma gravação confirmada.
Se houver erro, use **Tentar salvar**: a operação já aplicada na janela não é
executada nem cobrada novamente. O jogo também tenta salvar automaticamente.
Mantenha a janela aberta até resolver uma falha de gravação.

Quando houver um problema com um save existente, a tela **Recuperar progresso**
oferece **Tentar novamente**, **Consultar detalhes**, **Restaurar backup** quando
houver uma cópia válida e **Iniciar nova fazenda**. Restaurar ou começar outra
partida exige confirmação; os arquivos anteriores são preservados. Cancelar
mantém os arquivos e encerra a abertura, sem criar outra fazenda silenciosamente.
Uma instalação sem qualquer progresso anterior inicia normalmente.

[Capturas reais do tutorial, filtro, confirmação de lote e recuperação](docs/screenshots/experience/).

## Executar pelo código

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Em Linux/macOS, use `python3 -m venv .venv` e `.venv/bin/python`.
Para um perfil de teste: `python main.py --save caminho/temporario/save.json`.
A variável `IDLEFARM_SAVE_PATH` também permite selecionar um perfil. Não altere
o relógio do computador para testar: os testes usam um relógio virtual isolado.

## Validar e recompilar

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python tools/validate.py --output qa-output/visual
python tools/validate_experience.py --output qa-output/experience
python tools/benchmark.py --output qa-output/performance.json
```

Em um servidor Linux sem tela, defina `QT_QPA_PLATFORM=offscreen`. A aplicação
também possui um smoke test que exige um perfil isolado:

```powershell
python main.py --save qa-output/profile/save.json --smoke qa-output/source.json
```

No Windows, execute `build_windows.bat`. O script instala dependências, roda
os testes, gera `dist/IdleFarm.exe`, inicia o executável em uma pasta temporária
duas vezes e grava seu SHA-256. O teste do próprio binário também verifica
tutorial, lotes, repetição segura de salvamento, recuperação, retomada e o
commit de origem, usando perfis temporários. Alternativamente:

```powershell
python -m PyInstaller --noconfirm --clean IdleFarm.spec
python tools/smoke_exe.py dist/IdleFarm.exe --output qa-output/packaged
```

O PyInstaller gera binários nativos: em Linux, a saída é Linux. O executável
Windows x64 deve ser gerado no Windows ou pelo workflow Windows incluído.
Para publicar uma versão, envie uma tag, por exemplo `v0.3.0`; a publicação é
automática somente se todos os passos do workflow passarem.

## Arquitetura e persistência

| Diretório | Responsabilidade |
|---|---|
| `game/` | Economia, tempo, tutorial, lotes, gerações de salvamento e recuperação |
| `config/catalog.json` | Todos os preços, tempos, recompensas e desbloqueios |
| `ui/` | Controles Qt, navegação, confirmação de lotes e recuperação de progresso |
| `visual/` | Cenas 512×288, comportamentos, profundidade e iluminação local |
| `assets/` | Arte final offline, fontes originais e metadados de animação |
| `tools/` | Simulação, capturas, geração de arte e smoke test de distribuição |
| `tests/` | Testes econômicos, integração, recuperação e interface |

O save é JSON versionado, validado antes de carregar. Gravações usam arquivo
temporário, `fsync` e substituição atômica, com cópia `.bak`. O diagnóstico de
arquivos inválidos não os move nem os substitui. Uma restauração ou nova fazenda
confirmada preserva cópias exatas `.corrupt-*` antes de instalar os dados escolhidos.
Um log separado `.diagnostic.log` ajuda na investigação e tem tamanho limitado.

Uma trava por perfil evita duas janelas contabilizando a mesma fazenda.
O controle por gerações distingue alterações em memória de dados persistidos;
o salvamento automático usual ocorre a cada 30 segundos e falhas são tentadas
novamente após 10 segundos. Operações em lote gravam uma vez por operação.
O esquema v1 continua compatível: saves sem os dados opcionais do tutorial
mantêm os tempos normais. Timestamps de alta-maré impedem voltar o relógio e
receber novamente ciclos já pagos. Não há DRM nem proteção criptográfica contra
edição manual do save.

Leia as [decisões de estabilidade, recuperação e tempo](docs/ESTABILIDADE.md)
para os detalhes técnicos, testes direcionados e procedimentos de verificação.

Veja as [animações](docs/screenshots/animations.gif), o [changelog](CHANGELOG.md)
e o [plano técnico da reformulação](docs/REFORMULACAO.md).

Leia [os testes e limites verificados](docs/VALIDACAO.md) e
[a direção artística](assets/ART_DIRECTION.md). A referência de apresentação
foi o [PescaIdle](https://github.com/BernardoJ/PescaIdle), consultado sem alterações.
