# Economia v0.1.0

Valores centralizados em `config/catalog.json`. Moedas e pagamentos usam inteiros.

## Culturas

| Cultura | Crescimento | Semente | Colheita | Receita acumulada para desbloquear |
|---|---:|---:|---:|---:|
| Trigo | 1h | 5 | 20 | 0 |
| Cenoura | 2h | 10 | 50 | 0 |
| Milho | 4h | 20 | 125 | 200 |
| Morango | 6h | 30 | 220 | 800 |
| Abóbora | 8h | 50 | 400 | 1600 |

Desbloqueios são automáticos por receita total, sem cobrança adicional.

## Construções

| Construção | Preço permanente |
|---|---:|
| Galinheiro | 220 |
| Celeiro | 1200 |
| Chiqueiro | 700 |
| Estábulo | 1800 |
| Canil | 450 |

## Animais

| Espécie/raça | Instalação | Custo da primeira unidade | Recompensa | Intervalo | Moedas/h por unidade | Retorno inicial |
|---|---|---:|---:|---:|---:|---:|
| Galinha | Galinheiro | 80 | 15 | 30 min | 30 | 2.67h |
| Pato | Galinheiro | 180 | 30 | 45 min | 40 | 4.50h |
| Pavão | Galinheiro | 600 | 110 | 120 min | 55 | 10.91h |
| Vaca | Celeiro | 650 | 100 | 120 min | 50 | 13.00h |
| Cabra | Celeiro | 420 | 52 | 60 min | 52 | 8.08h |
| Ovelha | Celeiro | 500 | 75 | 90 min | 50 | 10.00h |
| Porco | Chiqueiro | 450 | 75 | 90 min | 50 | 9.00h |
| Cavalo | Estábulo | 1100 | 170 | 120 min | 85 | 12.94h |
| Vira-lata | Canil | 100 | 0 | — | 0 | Decorativo |
| Beagle | Canil | 180 | 0 | — | 0 | Decorativo |
| Border collie | Canil | 300 | 0 | — | 0 | Decorativo |
| Golden retriever | Canil | 420 | 0 | — | 0 | Decorativo |

## Progressão e decisões

- Início: **50 moedas e dois terrenos**. A primeira expansão custa **120**; as seguintes sobem **35%** por terreno adquirido, com arredondamento para cima. Não existe limite de terrenos imposto pelo cenário.
- Cada nova unidade da mesma espécie custa `ceil(base × 1,12^quantidade)`. O rendimento individual permanece constante. O custo crescente reduz a vantagem de repetir apenas galinhas baratas e dá utilidade às espécies caras, sem inflação exponencial da renda.
- Uma fazenda com uma unidade de cada espécie produtiva rende em média **412 moedas/h**; o celeiro oferece **152/h**, galinheiro **125/h**, chiqueiro **50/h** e estábulo **85/h**. O pagamento continua discreto, nos intervalos da tabela.
- O custo da construção deve ser somado ao investimento inicial. Galinheiro + uma galinha custa 300 e retorna em 10h produtivas; essa taxa melhora com mais animais, pois a construção é permanente.
- O PescaIdle usa capturas de valores fracionários até milhares de moedas, melhorias a partir de 30 moedas e ciclos de segundos. Aqui foram mantidos os valores sugeridos de plantio por horas para a proposta de fazenda, com pagamentos previsíveis e limite offline de 4h. Não foi copiada a aleatoriedade da pesca.
- A primeira expansão pode ser alcançada em aproximadamente 3h de manejo inicial (colheitas de trigo e cenoura), sem exigir desbloqueios ou investimento impossível.
- A simulação legítima atingiu todas as culturas, cinco instalações, doze espécies/raças, 12 terrenos e 20 animais em **92 horas virtuais**. É um cenário de teste de cobertura, não uma estimativa de tempo mínimo de jogador.
- Para evitar bloqueio financeiro, sem plantações nem animais produtivos e com menos de 5 moedas, o auxílio de recomeço restaura o saldo para 5. Ele não pode ser repetido durante o crescimento ou quando há produção animal.
- O crescimento das culturas não tem teto offline; somente a renda dos animais é limitada a 4h por ausência. O excedente é descartado preservando a fase do ciclo parcial, sem pagamentos retroativos duplicados.
