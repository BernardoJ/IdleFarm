## IdleFarm 0.3.1 · cuidar da fazenda com mais segurança

A v0.3.1 corrige a validação das fontes no Windows: as capturas usam a
renderização nativa, e a presença e o desenho dos glifos são verificados nas
capturas e no executável. A v0.3.0 ficou como prévia após a inspeção identificar
texto em quadrados nas evidências do modo offscreen.

Esta versão corrige o indicador de salvamento, o tratamento de arquivos
inválidos e a seleção dos canteiros. Acrescenta ferramentas para fazendas
maiores e preserva a arte, os cenários e as animações da v0.2.0.

### Progresso protegido e recuperação compreensível

O indicador mostra **Tudo salvo**, **Salvando…**, **Alterações não salvas** ou
**Erro ao salvar** de acordo com a gravação real. Uma falha continua visível
até ser resolvida. **Tentar salvar** persiste a ação já aplicada na janela,
sem repetir uma compra ou cobrar novamente.

Saves inválidos, inclusive com timestamps extremos, são rejeitados de forma
controlada. A tela de recuperação permite tentar novamente, consultar detalhes,
restaurar um backup válido ou confirmar uma nova fazenda. Os arquivos anteriores
são preservados; nenhuma nova partida substitui silenciosamente seu progresso.

### Menos tarefas repetitivas

- **Prontas** filtra as colheitas disponíveis, mantendo o terreno selecionado
  identificado mesmo quando não atender ao filtro.
- **Próximo livre** encontra o próximo terreno disponível em ordem previsível.
- **Colher prontas** reúne as colheitas maduras em uma operação e informa o total.
- **Plantar terrenos livres** mostra cultura, quantidade, custo e saldo antes da
  confirmação. É possível plantar só a quantidade que o saldo permite. Propostas
  alteradas precisam ser revisadas novamente.
- O terreno selecionado aparece destacado no cenário. Cliques sobre canteiros
  sobrepostos priorizam aquele que está visualmente à frente.

### Um primeiro ciclo mais acessível

Em uma fazenda nova, somente o **primeiro trigo** cresce em **60 segundos**.
Seu custo e sua recompensa são normais. Após a colheita, o trigo volta ao tempo
usual de uma hora. O benefício é salvo e não recomeça quando você abre o jogo.
**Saves antigos mantêm suas plantações e seus tempos de crescimento.**

Suspensão, hibernação e reabertura agora seguem a mesma regra: até **quatro
horas** de produção animal por ausência. O crescimento das culturas considera
todo o tempo real. Sessões ativas com atualizações regulares continuam
acumulando produção normalmente.

### Jogar no Windows 64 bits

Baixe **IdleFarm.exe** abaixo e abra com dois cliques. Não requer instalação
de Python nem conexão à internet. O progresso continua em
`%APPDATA%\IdleFarm\save.json`. O executável não possui assinatura digital.

### Verificação da distribuição

A publicação desta Release depende da aprovação dos testes funcionais e de
interface, das capturas em DPI 100%, 125%, 150% e 200%, do benchmark, do build
Windows limpo e do teste do próprio executável com perfis isolados. O binário
verifica tutorial, lotes, retomada, recuperação e repetição segura de salvamento,
além de registrar seu commit de origem e verificar a legibilidade das fontes
na renderização nativa do Windows.
`SHA256SUMS.txt` contém o checksum; `executable.json` e `performance.json`
registram as verificações do binário e do renderizador. Os demais relatórios e
capturas ficam no artefato da execução do GitHub Actions.

[Regras de estabilidade e recuperação](https://github.com/BernardoJ/IdleFarm/blob/main/docs/ESTABILIDADE.md)
· [Changelog](https://github.com/BernardoJ/IdleFarm/blob/main/CHANGELOG.md)
