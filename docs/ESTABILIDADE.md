# IdleFarm 0.3.0 — estabilidade, recuperação e experiência

A versão mantém a arquitetura Python/PySide6 e a identidade visual 512×288 da
v0.2.0. A implementação foi dividida em correções críticas, melhorias de
experiência e integração/distribuição. Não há novas dependências pesadas.
O catálogo de preços, recompensas, rendimentos e desbloqueios permanece igual;
as mudanças de tempo limitam-se ao tutorial e à uniformização das ausências.

## Estado de salvamento

`game/persistence.py` acompanha a geração de alterações em memória e a geração
confirmada em disco. `game/engine.py` grava uma cópia isolada do estado; uma
conclusão só reconhece a geração daquela cópia. Se uma mudança surgir durante
a gravação, ela permanece pendente, mesmo quando a gravação anterior termina.
A interface observa quatro estados independentes das notificações temporárias:

| Estado | Significado |
|---|---|
| Tudo salvo | A geração atual foi confirmada em disco. |
| Salvando… | Uma tentativa de gravação está em andamento. |
| Alterações não salvas | Há uma geração posterior àquela persistida. |
| Erro ao salvar | A última tentativa falhou e a pendência precisa ser resolvida. |

Notificações podem expirar após 12 segundos, mas isso nunca converte pendência
ou erro em sucesso. O ciclo automático usual verifica o salvamento a cada
30 segundos; após uma falha, a interface tenta novamente após 10 segundos.
O botão **Tentar salvar** permite uma tentativa explícita. Chamadas sem mudança
não provocam gravações repetidas; gravações reentrantes ficam adiadas.

Uma ação economicamente válida é aplicada uma vez. Se somente sua persistência
falhar, a compra, o plantio ou a colheita ficam em memória, com indicação de
pendência. `PendingSaveError` conserva o resumo da operação para a interface.
A tentativa seguinte grava o estado pendente, sem repetir a regra de negócio,
cobrar novamente ou creditar outra colheita. Ações inválidas continuam sendo
revertidas antes de qualquer gravação.

O fechamento normal avança o tempo e tenta salvar. Uma falha mantém a janela
aberta e apresenta o problema. Encerramento forçado, queda de energia ou término
do processo antes de uma gravação bem-sucedida ainda podem perder alterações
que só existam em memória; o indicador não as apresenta como protegidas.

## Validação e recuperação dos arquivos

`game/state.py` aceita timestamps numéricos no intervalo
**`0 <= timestamp < 253402300800`**, do início de 1970 até antes do ano 10000,
incluindo frações representáveis no último segundo de 9999. O limite deriva do
domínio temporal aceito, não de uma data arbitrária de expiração. A faixa e o
tipo são verificados antes de qualquer conversão potencialmente perigosa.
Booleanos, negativos, valores não finitos, tipos incorretos e inteiros extremos
são rejeitados de forma controlada.

`SaveStore.load()` diagnostica os arquivos de progresso sem movê-los, renomeá-los
ou substituir seu conteúdo. Havendo progresso existente que não possa ser
aberto, a aplicação recebe `RecoveryRequired`, com motivos e eventual backup
validado. O diagnóstico não cria outra fazenda nem dispara um salvamento que
substitua o arquivo inválido. Corrupção descoberta antes de uma gravação também
impede a substituição silenciosa do alvo.

A tela `ui/recovery.py` distingue os seguintes casos:

| Situação | Comportamento |
|---|---|
| Nenhum save, backup ou arquivo de progresso preservado | A instalação nova inicia normalmente. |
| Save principal válido | O progresso é carregado. |
| Principal inválido e backup válido | A recuperação é oferecida; restaurar exige confirmação. |
| Nenhum save válido | A tela permite tentar novamente, consultar detalhes ou confirmar outra fazenda. |
| Cancelamento ou fechamento da recuperação | Nenhuma fazenda é criada; os arquivos de progresso permanecem intactos. |

**Tentar novamente** repete a leitura. Mesmo se arquivos desaparecerem enquanto
a tela estiver aberta, essa opção não autoriza uma nova partida silenciosa.
**Restaurar backup** revalida a cópia antes de usá-la. **Iniciar nova fazenda**
também exige confirmação, cuja opção inicial é não prosseguir.

Após autorização, os arquivos anteriores são copiados integralmente para nomes
`.corrupt-*`, com descarga e `fsync`, antes da instalação atômica do estado
escolhido. O backup válido não é substituído pelos dados rejeitados durante a
restauração. Falhas de arquivamento ou escrita não apagam o original.

Gravações usuais continuam usando arquivo temporário, `fsync`, substituição
atômica e `.bak`. A trava por perfil permanece ativa durante a decisão de
recuperação. O esquema JSON **v1** continua aceito, inclusive a fixture produzida
pela v0.1.0. Não há criptografia nem proteção contra edição manual deliberada.

## Diagnóstico separado

`game/diagnostics.py` grava mensagens em `<nome-do-save>.diagnostic.log`,
separadas de qualquer nome de progresso, inclusive perfis que terminem em
`.log`. O arquivo usa rotação a 128 KiB e duas cópias antigas. Rejeições de
validação e falhas de gravação são registradas para investigação; os caminhos
disponíveis aparecem na opção **Consultar detalhes**.

O log é uma ajuda de diagnóstico, não um requisito para carregar ou recuperar a
fazenda. Se não puder ser criado, o fluxo seguro continua. Os detalhes técnicos
ficam nessa tela, sem tomar o lugar das instruções simples ao jogador.

## Seleção e representação dos terrenos

O desenho e a seleção por clique compartilham a mesma lista de canteiros,
ordenada de forma estável pela coordenada vertical. O hit-test percorre essa
lista ao contrário: um canteiro desenhado por último recebe prioridade na
interseção, inclusive quando dois objetos têm a mesma coordenada Y.
A conversão entre a posição do mouse e os pixels lógicos respeita a área real
da cena e a escala de exibição.

O terreno escolhido usa seu identificador real, sem confundir a linha de uma
lista filtrada com o número do terreno. A seleção é mantida entre no máximo
cinco representantes, com destaque também para um terreno livre. Os demais
espaços são preservados sempre que possível, e a diversidade continua sendo
priorizada quando não conflitar com a visibilidade da seleção. Animais não
mudam de ambiente, e esse limite visual não limita propriedade ou renda.

O filtro **Prontas** mostra as colheitas maduras e conserva o selecionado,
identificado quando estiver fora do filtro. **Próximo livre** percorre os
terrenos em ordem crescente, volta ao início e ignora ocupados. Na ausência de
um terreno elegível, a interface informa a situação.

## Tutorial de uma única colheita

A primeira plantação de **trigo** de uma fazenda nova recebe um ciclo de
**60 segundos**. Esse tempo permite experimentar plantio, crescimento, colheita
e reinvestimento em uma sessão inicial, sem acelerar permanentemente o jogo.
O custo e a recompensa continuam sendo os do catálogo: cinco e vinte moedas.

A informação opcional `tutorial` registra se o benefício está disponível, qual
terreno o utiliza e se foi concluído. O segundo trigo, inclusive quando plantado
antes da primeira colheita ou no mesmo lote, segue as 3.600 s normais. Reiniciar
não renova o tempo nem concede outro benefício. Outras culturas não recebem a
aceleração. A conclusão é persistida ao colher o trigo do tutorial.

Saves antigos sem essa informação são tratados como tutorial concluído e não
recebem a chave automaticamente: conservam seus tempos e seu estado. Metadados
presentes são validados; uma referência inválida de tutorial é tratada como
save inválido, sem conversão silenciosa para outra partida.

## Operações em lote

`Farm.harvest_ready()` reúne os terrenos maduros, aplica as recompensas
individuais e produz um resumo, em uma transação e uma tentativa de gravação.
Plantações em crescimento permanecem intactas. Repetir a colheita não duplica
os créditos porque os terrenos já foram esvaziados.

`ReplantDialog` apenas monta uma proposta: cultura desbloqueada, quantidade,
terrenos livres, custo total, saldo e saldo posterior. Quando o dinheiro não
cobre todos os terrenos, a quantidade inicial é a que pode ser paga; isso é
mostrado antes da confirmação. O jogador pode alterar a quantidade, escolher
outra cultura ou cancelar sem cobrança. Sem saldo para uma semente ou sem
terrenos livres, a confirmação fica indisponível.

A confirmação reconsulta a proposta. Se os terrenos ou o saldo mudarem, os
valores são atualizados para revisão e uma nova confirmação é necessária;
a interface não reduz a compra silenciosamente. O diálogo não modifica o jogo
nem grava o save, mesmo quando aceito.

`Farm.plant_batch()` valida todos os identificadores, a ausência de duplicatas,
a cultura, a disponibilidade e o saldo antes de cobrar. O plantio usa uma única
transação e uma tentativa de gravação. Um erro de negócio não deixa um lote
parcial nem saldo negativo. Uma falha de disco deixa o lote completo pendente
em memória e é resolvida pelo mesmo salvamento sem nova cobrança.

## Suspensão, hibernação e relógios

O relógio de parede fornece o tempo de produção. O último instante contabilizado
funciona como marca de alta-maré: voltar o relógio não retrocede o crescimento
nem permite receber novamente ciclos já pagos. Uma leitura de horário inválida
mantém a última marca válida, sem contaminar o save.

**Todo intervalo ainda não contabilizado concede no máximo quatro horas de
produção animal**, tanto na reabertura quanto no primeiro tick após suspensão,
hibernação, bloqueio prolongado do processo ou salto para a frente do relógio.
Ticks curtos sucessivos preservam a renda normal por sessões de qualquer
duração. As frações dos ciclos dos animais são preservadas, e o intervalo
excedente não é creditado em ticks seguintes. Culturas continuam usando todo o
tempo real para crescer e aguardam a colheita manual.

Não são usadas notificações nativas de energia do sistema operacional para
identificar uma suspensão: a regra considera o intervalo entre atualizações,
o que produz o mesmo resultado nas plataformas suportadas. O relógio
monotônico serve às notificações e ao agendamento de tentativas de salvamento,
nunca ao cálculo das moedas. A retomada detectada por um intervalo relevante
leva a uma tentativa de persistência, respeitando a política de repetição em
caso de falha de disco.

## Testes e verificação

A suíte final local passou com **258 testes**, sem falhas, erros ou testes ignorados.
O resumo está em `screenshots/experience/tests-linux.json`; as seis capturas
dos novos fluxos também foram verificadas em DPI 100%, 125%, 150% e 200%.

A linha de base executada na `main` anterior passou com **76 testes**. A Fase 1
passou com **142 testes** antes de iniciar as melhorias de experiência. Os
resultados finais da suíte e do executável devem ser consultados no relatório
da versão e na execução do GitHub Actions; este documento não declara uma
compilação Windows aprovada sem essas evidências.

A validação visual encontrou dois cortes de texto: detalhes de recuperação em
DPI 200% e resumo do plantio em lote em DPI 125% com fonte nativa do Windows.
Os dois foram corrigidos pelo dimensionamento compartilhado de diálogos, com
regressões específicas; o validador permaneceu com os mesmos critérios.

Os testes novos separam os comportamentos em:

| Arquivo de teste | Verificação principal |
|---|---|
| `test_save_status.py` | Falha após compra/produção, expiração da notificação, retry, gerações atrasadas e ausência de cobranças repetidas. |
| `test_recovery_storage.py` | Limites temporais, inteiros extremos, leitura sem substituição, backups e preservação de bytes. |
| `test_plot_depth.py` | Interseções, empates, regiões normais e escala dos cliques. |
| `test_tutorial.py` | Primeiro ciclo, segundo trigo normal, reinício, save antigo e falha de gravação. |
| `test_batch.py` | Elegibilidade, saldo, recompensas, atomicidade, persistência e falhas em lotes. |
| `test_plot_tools.py` | Propostas de plantio, confirmação, cancelamento e revisão de valores alterados. |
| `test_plot_management_ui.py` | Filtro, IDs reais, próximo livre, lotes e atualização dos controles. |
| `test_selected_plot_visibility.py` | Seleção fora da representação inicial, destaque, espaços estáveis e limite de cinco. |
| `test_recovery_ui.py` | Fluxos de abertura, retry, confirmação, cancelamento e ausência de sobrescrita silenciosa. |
| `test_time_policy.py` | Equivalência entre retomada/reabertura em 30 min, 2 h, 4 h e 8 h, ciclos parciais e alterações do relógio. |
| `test_diagnostics.py` | Logs separados, impossibilidade de escrita e encerramento de handlers. |
| `test_integrity_end_to_end.py` | Compra/produção e restauração/offline com falhas de gravação e reabertura. |

Execute a partir da raiz do repositório, usando perfis temporários:

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest -q --junitxml=qa-output/tests.xml
python tools/validate.py --output qa-output/visual
python tools/validate_experience.py --output qa-output/experience
python tools/benchmark.py --output qa-output/performance.json
```

Sem tela em Linux, use `QT_QPA_PLATFORM=offscreen`. Os testes controlam o tempo e
não precisam de sleeps longos nem de alterações no relógio do computador.
Para uma inicialização isolada, use:

```powershell
python main.py --save qa-output/profile/save.json --smoke qa-output/source.json
```

O smoke test requer `--save`. Um perfil inválido é reportado sem uma caixa modal
nem criação de progresso substituto. No Windows, `build_windows.bat` executa as
validações, cria o binário limpo e testa o próprio `dist/IdleFarm.exe` antes de
calcular o SHA-256. Dentro do próprio executável, cenários privados verificam
tutorial, lotes, compra pendente com tentativa de gravação sem nova cobrança,
preservação/restauração, equivalência temporal e compatibilidade antiga. A
verificação exige também a identificação do commit incorporado ao build.
Esses cenários não alteram perfis de jogadores nem expõem atalhos de progressão.
O workflow executa os testes, as capturas nas quatro escalas de DPI, o benchmark
e a verificação do binário antes de publicar uma tag. O executável é novo e
incorpora os recursos locais; não requer Python instalado.

## Procedimento manual complementar

Os passos abaixo são verificações manuais reproduzíveis, não afirmações de uma
sessão física de suspensão já executada nesta documentação:

1. Use um perfil temporário e confirme o primeiro trigo pronto após 60 segundos;
   depois colha e verifique que o próximo trigo indica uma hora.
2. Com vários terrenos, alterne o filtro e o próximo livre, escolha um terreno
   fora dos representantes iniciais e confira o destaque correspondente.
3. Abra um plantio em lote, confira quantidade, custo e saldo, cancele e confirme
   que nada mudou; em seguida confirme um lote e confira seu resumo.
4. Em uma cópia do perfil, provoque uma falha de gravação. Compre ou colha apenas
   uma vez, aguarde a notificação expirar e confirme que o indicador conserva a
   pendência. Restabeleça a escrita e use **Tentar salvar**, sem repetir a ação.
5. Em uma cópia descartável, torne o principal ilegível e abra a recuperação.
   Cancele e compare os bytes; reabra, restaure um backup válido e confira as
   cópias anteriores preservadas. Nunca use o save real para esse ensaio.
6. Em um perfil de teste com animal produtivo, compare uma suspensão longa e uma
   reabertura com a mesma ausência; confira o limite de quatro horas e ausência
   de crédito repetido no tick seguinte. A automação cobre esse cálculo com
   relógios virtuais; o ensaio físico depende do computador e do sistema.

As limitações conhecidas são as poses discretas e os passeios curtos herdados da
arte atual, margens da escala inteira em alguns tamanhos/DPI, identificação da
ausência por intervalo sem atualização e diagnóstico em melhor esforço. O
estado pendente ainda depende de uma gravação efetiva para sobreviver ao fim
do processo. Nenhuma dessas condições é apresentada como salvamento concluído.
