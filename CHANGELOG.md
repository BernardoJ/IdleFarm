# Changelog

## 0.3.1 — 27/10/2026

- Capturas Windows passam a usar o renderizador nativo e sua base de fontes,
  corrigindo a evidência visual com texto em quadrados produzida pelo modo offscreen.
- Validação de glifos e desenho de letras nas capturas e no próprio executável,
  além das verificações de dimensões, para bloquear uma distribuição ilegível.
- A v0.3.0 permanece como prévia; esta versão incorpora suas correções e melhorias.

## 0.3.0 — 27/10/2026 (prévia)

- Indicador de salvamento baseado em gerações confirmadas, com estados de
  gravação, pendência e erro; notificações expiradas não declaram sucesso falso.
- Ações concluídas ficam pendentes em memória após falha de gravação. Tentar
  salvar novamente não repete compras, plantios ou créditos de colheita.
- Validação temporal limitada ao domínio válido, sem conversão perigosa de
  inteiros gigantes; diagnóstico de saves inválidos preserva seus bytes.
- Recuperação explícita por backup ou nova fazenda, com confirmação e cópias
  preservadas; ausência de progresso anterior é diferenciada de corrupção.
- Seleção por clique segue a ordem inversa do desenho, incluindo desempates.
- Primeiro trigo de uma fazenda nova cresce em 60 segundos, uma única vez,
  mantendo custo e recompensa. Saves antigos continuam com tempos normais.
- Filtro de colheitas prontas, próximo terreno livre, colheita em lote e plantio
  em lote com revisão de quantidade, custo, saldo e confirmação de propostas.
- O terreno selecionado aparece destacado entre até cinco representantes,
  inclusive livre e fora do filtro, sem alterar sua identidade na interface.
- Suspensão, hibernação e reabertura usam o mesmo limite de quatro horas por
  intervalo sem contabilização para animais; plantações crescem pelo tempo real.
- Diagnóstico separado e limitado, novos testes determinísticos de integridade,
  tutorial, lotes, seleção, recuperação e política temporal.
- Identidade visual da v0.2.0, preços, recompensas e progressão normal preservados.

## 0.2.0 — 26/10/2026

- Substituição completa dos seis cenários por arte original a 512×288.
- Galinheiro, celeiro, chiqueiro, estábulo e canil vistos por dentro, com
  mobiliário e materiais próprios; campo com canteiros, vegetação e ferramentas.
- Novos sprites das doze espécies/raças: 72 quadros com portes distintos,
  caminhada, respiração, alimentação, descanso e comportamentos próprios.
- Vinte novos estágios visuais das cinco culturas.
- Sombras de contato, ordenação por profundidade, primeiro plano e passeios
  curtos em áreas livres.
- Luz local com amanhecer, dia, entardecer, noite, janelas e lanternas.
- Molduras rurais, botões, ícones e menu de áreas; abertura nas plantações,
  mantendo uma área por vez e gerenciamento recolhível.
- Fontes de arte preservadas e exportação reproduzível; pacote contém apenas
  recursos finais e continua funcionando offline, sem Python instalado.
- Testes de compatibilidade com save produzido pela v0.1.0, oclusão, iluminação,
  animação, seleção com escala e desempenho. Economia e esquema de save mantidos.
- Build Windows com versão do arquivo, quatro escalas de DPI, teste do próprio
  executável, relatório de desempenho e SHA-256.

## 0.1.0 — 26/10/2026

- Primeira versão: cinco culturas, cinco instalações, doze espécies/raças,
  produção por animal, progresso offline e salvamento atômico com recuperação.
