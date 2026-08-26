# Licencias de las fuentes embebidas

| Archivo | Fuente | Licencia | ¿Puede salir a produccion? |
|---|---|---|---|
| `BebasNeue-Regular.woff2` | Bebas Neue 2.000 | SIL Open Font License 1.1 | Si |
| `BellaFashion-Regular.woff2` | Bella Fashion, de Billy Argel | «Free for personal use only» | **No sin comprar la licencia comercial** |

Sal y Sol vende tours: el sitio es uso comercial. Mientras no se compre la
licencia de Bella Fashion en billyargel.com, las palabras de acento
(`.font-acento`) tienen que caer a la fuente de cuerpo o cambiarse por otra.

Las dos vienen de archivos `.otf`/`.ttf` convertidos a woff2 con fontTools.
Los originales estan en `~/Downloads/bebas-neue.zip` (con su OFL.txt) y
`~/Downloads/bella-fashion-font.zip`, junto con sus EULA.

Bebas Neue va subconjuntada a latin + latin-1 + comillas y guiones tipograficos
(`pyftsubset ... --flavor=woff2`): 10.9 KB en vez de 74 KB. Si algun dia un
titular necesita un caracter fuera de eso, hay que rehacer el subconjunto o
saldra en la fuente de cuerpo a mitad de palabra.
