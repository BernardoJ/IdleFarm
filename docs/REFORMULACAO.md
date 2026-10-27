# Plano técnico da reformulação 0.2.0

Base examinada: `6c4e893`, publicada como v0.1.0, mais a navegação por menu
implementada neste chat. O código usa Python 3.12, PySide6 6.10, QImage/QPainter,
fundos 256×144 e atlases 32×32 com quatro quadros. As cinco construções usavam
fachadas externas, o movimento era uma oscilação horizontal e a iluminação
dependia principalmente de uma sobreposição uniforme. A resolução e as
silhuetas pequenas limitavam a anatomia e a decoração interna.

1. Substituir as seis artes por composições originais: campo e cinco interiores,
   produzidos com geração de imagens e fontes PNG preservadas no repositório.
2. Exportar a 512×288, com pixels nítidos; novos atlases com células 96×96,
   seis poses por animal, quatro estágios por cultura e portes diferentes.
3. Separar primeiro plano, ordenar representantes pela posição dos pés e
   limitar passeios a zonas livres, com estados de animação determinísticos.
4. Separar luz ambiente, janelas, raios e fontes quentes locais; manter a
   visibilidade de animais à noite e efeitos independentes do relógio econômico.
5. Integrar molduras rurais, ícones e menu de áreas, com plantações iniciais e
   uma área por vez. Manter gerenciamento recolhível e janela redimensionável.
6. Verificar saves v1, economia, diversidade e limite de cinco, poses,
   sobreposição, iluminação, jogatina completa e desempenho sustentado.
7. Inspecionar capturas diurnas/noturnas; empacotar no Windows, iniciar o
   próprio executável duas vezes e publicar v0.2.0 com SHA-256 e evidências.

O catálogo econômico e o esquema dos saves não precisam mudar. Pillow fica
restrito à preparação de arte e QA; o executável continua offline, usando Qt.
O PescaIdle foi consultado como referência técnica de iluminação por materiais,
camadas, caches limitados e composição de primeiro plano; seus assets não foram
copiados.
