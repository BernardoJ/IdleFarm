# Arte original do IdleFarm

Cenas de 256×144 pixels, paleta de verdes sálvia, madeiras quentes, telhados
terrosos e contornos escuros. A referência técnica e de apresentação é o
PescaIdle, revisão `6b29b4a0da3ce403dad4ff46e7f656659d2266f1`. Nenhuma imagem
ou sprite daquele projeto foi copiada.

Todos os PNGs são produzidos por `python tools/generate_art.py`, com sementes
determinísticas. Árvores têm volumes de folhagem, ramos e reflexos; edifícios
têm ripas, telhas, vigas, janelas, alvenaria e sombras de contato. Os ambientes
têm decoração própria (ninhos, lama, feno, baias, casinhas e brinquedos).

`animals.png` contém 12 espécies/raças × 4 quadros de 32×32 pixels, com
silhuetas próprias, pelagem, asas, caudas e repouso. `crops.png` contém cinco
culturas × quatro estágios. O tempo visual não modifica o estado econômico.

O renderizador aplica luz por horário civil local, nuvens, folhas, pássaros,
vagalumes e fontes quentes à noite. A escala da cena é inteira em pixels
físicos e usa nearest-neighbor; texto e controles Qt usam a resolução nativa.
