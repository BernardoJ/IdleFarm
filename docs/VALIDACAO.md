# Validação da reformulação 0.2.0

Este relatório registra a entrega gráfica 0.2.0. Para as correções de saves,
tutorial, lotes e política temporal da 0.3.0, consulte
[Estabilidade e recuperação](ESTABILIDADE.md) e os relatórios do workflow atual.

## Código e compatibilidade

A base v0.1.0 publicada foi examinada antes da reformulação. O catálogo de
preços, tempos, rendimentos e desbloqueios, assim como o código econômico e o
esquema v1 dos saves, foram preservados. A fixture `tests/fixtures/v0.1.0-save.json`
foi produzida executando o código da tag v0.1.0 em um diretório isolado, com
jogatina legítima. A versão nova restaura seu estado exatamente, incluindo
12 terrenos, 20 animais, culturas, edifícios e saldo; também verifica pagamentos
offline sem duplicação.

A suíte local passou com **76 testes**. As capturas passaram nas escalas
100%, 125%, 150% e 200%, sem controles cortados. A suíte cobre plantio e colheita das cinco culturas, todas as instalações e
espécies, navegação real pelo menu, uma página por vez, reinício nas plantações,
seleção de canteiros com a nova resolução, poses completas, portes, limites de
movimentação, ordem vertical, oclusão real de pixels, janelas, lanternas,
independência da renderização em relação ao estado econômico, recuperação de
saves e inicialização fora da pasta do projeto.

## Jogatina e imagens inspecionadas

A simulação parte de 50 moedas e dois terrenos. Em 92 horas virtuais, planta e
colhe todas as culturas, constrói as cinco instalações e compra as doze
espécies/raças. Termina com 12 terrenos e 20 animais, incluindo nove galinhas.
O galinheiro mostra galinha, pato e pavão entre no máximo cinco representantes.

Foram geradas e inspecionadas as cenas dos seis ambientes durante dia e noite,
as respectivas janelas completas e os novos atlases. Os cinco interiores têm
paredes, piso, janelas e decoração própria. A lama aparece no centro do
chiqueiro; camas e brinquedos diferenciam o canil; selas e baias identificam o
estábulo. A vaca e o cavalo têm portes maiores. Lanternas mantêm fontes quentes
locais à noite, enquanto os vidros escurecem.

A primeira inspeção encontrou pequenos fragmentos de silhuetas adjacentes e
extremidades de plantas atravessando divisões dos atlases gerados. A exportação
passou a isolar componentes conexos, agrupar plantas pela linha de solo e
normalizar as escalas sem cortar orelhas ou pernas. As capturas finais foram
regeneradas após a correção. Um teste com uma silhueta sólida comprova que o
primeiro plano realmente cobre os pixels do animal.

As [galerias e capturas](screenshots/) são imagens reais do renderizador e da
interface. `screenshots/animations.gif` demonstra os quadros de animação;
`screenshots/validation.json` registra os resultados geométricos e a simulação.
A validação considera botões comuns e o botão do menu, além de rótulos visíveis.

## Desempenho e empacotamento

`python tools/benchmark.py` aquece os caches e mede 1.200 renderizações,
amostrando um dia visual de 24 horas com todas as espécies. Isso é um teste
acelerado; não representa 24 horas de execução real. O relatório registra
média, percentil 95, memória residente antes/depois, caches fixos e confirmação
de que a economia não mudou. Na medição local final: média de 0,535 ms por
quadro e crescimento residente de 798.720 bytes, sem aumento dos caches.
O resultado está em `screenshots/performance-linux.json`.

As artes-fonte não entram no pacote. O executável usa apenas PNGs finais e
metadados locais. Pillow continua restrito à preparação de arte e QA.

O workflow Windows compila com PyInstaller, verifica PE x64 e inicia o próprio
`IdleFarm.exe` duas vezes em outra pasta, com save temporário. Confirma versão,
resolução 512×288, atlas com 72 quadros, cinco interiores, carregamento das seis
áreas e restauração do perfil. Somente depois calcula o SHA-256 e publica a
Release. Evidências remotas são os logs do workflow e os arquivos
`executable.json`, `performance.json` e `SHA256SUMS.txt` anexados à Release.

## Limites

As animações usam poses discretas e trajetos curtos, com cinco representantes;
não há navegação livre por todo o mapa. O teste de desempenho mede amostras
aceleradas, não uma sessão de 24 horas reais. A escala inteira pode criar
margens ao redor da cena em certos tamanhos/DPI. O executável continua sem
assinatura digital. Saves seguem sem criptografia. Não foram adicionados som,
conquistas ou alterações econômicas.
