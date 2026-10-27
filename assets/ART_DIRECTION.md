# IdleFarm 0.2.0 · direção artística e produção

Arte original com inspiração na linguagem rural dos RPGs de fazenda clássicos:
perspectiva superior em 3/4, madeira mel, terra quente, verdes naturais,
volumes sombreados, materiais texturizados e objetos com escala reconhecível.
Nenhum cenário ou sprite foi extraído de Stardew Valley, Harvest Moon ou
PescaIdle. O último foi consultado somente como referência técnica.

## Recursos finais

- Seis fundos **512×288**: campo, galinheiro, celeiro, chiqueiro, estábulo e
  canil. As cinco construções são interiores com paredes, janelas e mobiliário.
- Seis camadas RGBA de primeiro plano, com a cobertura das cercas e vegetação.
- `animals.png`: doze colunas de espécies × seis linhas de poses, células
  **96×96**. Os animais ocupam portes diferentes dentro das células. A vaca e
  o cavalo são maiores que cabras, ovelhas e aves.
- `crops.png`: cinco colunas × quatro estágios, também em células 96×96.
- `manifest.json`: resolução, ordem dos sprites, limites dos quadros, janelas,
  lanternas, zonas livres e inventário dos elementos de cada ambiente.

## Fontes e reexportação

As artes-fonte lossless estão em `assets/source/`, com seis composições e quatro
atlases. Foram produzidas com a ferramenta de geração de imagens a partir de
briefings próprios, depois preparadas com Pillow. Os arquivos originais gerados
foram preservados; não há fontes em camadas PSD/Aseprite disponíveis.

Os briefings pediram fundos sem animais nem culturas plantadas, pisos centrais
livres, coerência de perspectiva e decoração própria. Para os atlases, pediram
silhuetas inteiras sobre transparência, espécies constantes e poses distintas.
As divisões propostas pelo gerador nem sempre correspondiam às silhuetas:
a extração por componentes conexos preserva orelhas, pernas e caudas, remove
fragmentos vizinhos e conserva a escala entre quadros. Culturas são agrupadas
pela linha de solo, mantendo o crescimento real entre estágios.

Execute `python tools/generate_art.py` para reexportar as fontes. O processo é
determinístico e offline: limpa a cobertura alfa, extrai os sprites, normaliza
as escalas e linhas dos pés, reduz os novos fundos a 512×288 com nearest-neighbor
e exporta máscaras e metadados. Não amplia os assets antigos de 256×144.
As fontes ficam fora do executável; só os PNGs finais e metadados são empacotados.

## Movimento, profundidade e iluminação

Os representantes têm passeios curtos com aceleração suave, repouso ancorado,
alimentação, descanso e exibição da cauda do pavão. As poses usam quadros próprios,
sem deformação por interpolação. Os passeios ficam em zonas livres; o desenho
segue a ordem vertical dos pés e a cobertura do primeiro plano. Sombras de
contato acompanham os animais. O ciclo visual independe de saves e produção.

A iluminação usa 24 pares limitados de placas de fundo/primeiro plano: dia,
amanhecer, entardecer e noite para cada ambiente. A transição usa o relógio civil
local, com janelas escuras à noite, lanternas, áreas de luz quente, feixes,
poeira e paletas de animais influenciadas pela distância às fontes de luz.
Não há filtro que apague a visibilidade dos animais. Pequenos reflexos, lama,
borboletas, vaga-lumes e movimento das culturas completam a ambientação.

A cena atualiza a 10 Hz. O escalonamento permanece inteiro em pixels físicos,
inclusive com DPI fracionário, e os controles Qt usam a resolução nativa.
