# Validação da primeira versão

## Execução local

Python 3.12.14, PySide6 6.10.0, Linux x64, plataforma Qt offscreen.

- **59 testes passaram**, incluindo ações reais em controles Qt e inicialização
  da aplicação em outro diretório de trabalho.
- A simulação partiu de **50 moedas e dois terrenos**, sem injetar dinheiro,
  percorreu **92 horas virtuais**, plantou e colheu todas as cinco culturas,
  adquiriu as cinco construções e todas as doze espécies/raças.
- Foram comprados **12 terrenos e 20 animais**, incluindo nove galinhas. O teste
  verificou que o limite de cinco sprites não reduz a renda nem omite espécies.
- Testes individuais verificaram os pagamentos das oito espécies produtivas e
  a ausência de pagamento das quatro raças de cachorro.
- Períodos offline testados: 0, 60, 1.799, 1.800, 3.600, 14.400, 28.800 e
  86.400 segundos. Testados também ciclos parciais, reabertura repetida,
  colheita duplicada, saldo insuficiente e relógio retrocedendo.
- Persistência: restauração exata, transação revertida em falha de gravação,
  arquivo parcialmente gravado, recuperação de backup, dois arquivos inválidos,
  esquema inválido e proteção do save real durante QA.
- **12 capturas** cobrem os seis ambientes durante dia e noite. O validador
  verificou limites geométricos de textos e botões, sem controles cortados.
- Capturas adicionais executadas em DPI **100%, 125%, 150% e 200%**; sem
  cortes de controles detectados. Texto nativo, cena com escala inteira em
  pixels físicos e nearest-neighbor.

O relatório estruturado da captura está em
[`screenshots/validation.json`](screenshots/validation.json). A execução de
testes fica separada do relatório visual: uma captura não substitui os testes.

## Falha encontrada e corrigida

A primeira bateria encontrou cinco falhas no limiar visual de broto: o cálculo
`1 - restante / duração` arredondava 10% para um valor ligeiramente inferior.
A implementação agora compara diretamente o tempo decorrido com a duração,
preservando o limite exato sem afrouxar os testes. A bateria completa passou
depois da correção.

A inspeção das capturas também identificou quebra desnecessária do subtítulo
na barra superior. O indicador foi reduzido a período do dia e hora, mantendo
texto e controles legíveis.

## Windows e publicação

O workflow `.github/workflows/windows-release.yml` executa os testes, capturas,
PyInstaller e smoke test do **próprio executável Windows x64**. O smoke test
valida o cabeçalho PE x64, inicia o binário duas vezes fora do checkout, usa
save temporário e exige carregamento dos seis ambientes. A segunda abertura
confirma a persistência do perfil empacotado. O SHA-256 é calculado após isso.

Este relatório local não declara aprovado um workflow remoto ainda não observado.
Consulte Actions, os artefatos e a Release para o resultado efetivo no Windows.

## Limites conhecidos

- Saves não são criptografados; edição externa pode alterar progresso. A proteção
  cobre duplicação acidental, recuo do relógio e falhas de escrita.
- O jogo acompanha o horário civil local para iluminação, sem geolocalização.
- A versão não inclui som, conquistas, comercialização de animais ou assinatura
  digital do executável; esses itens não são necessários à economia da v0.1.
- Capturas offscreen verificam layout/renderização. O comportamento do desktop
  e o binário Windows recebem validação separada no executor Windows.
