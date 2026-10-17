# Licencias de las fuentes embebidas

| Archivo | Fuente | Licencia | ¿Puede salir a produccion? |
|---|---|---|---|
| `BebasNeue-Regular.woff2` | Bebas Neue 2.000 | SIL Open Font License 1.1 | Si (ya no se carga: retirar el archivo) |
| `BellaFashion-Regular.woff2` | Bella Fashion, de Billy Argel | «Free for personal use only» | **No.** Ya no se carga (la palabra caligrafica salio de los titulares): retirar el archivo |
| `ConsolaMono-Bold.woff2` | Consola Mono Bold, de Wojciech Kalinowski (dafont.com/es/consola-mono.font) | SIL Open Font License 1.1 (`OFL.txt` y `FONTLOG.txt` junto al archivo; sin nombre reservado declarado) | Si |

Sal y Sol vende tours: el sitio es uso comercial. Bebas Neue y Bella Fashion ya no
las importa `layout.tsx` (los titulares van en Consola Mono Bold y el cuerpo en la
fuente del sistema); sus archivos siguen aqui solo hasta que se borren.

Las dos vienen de archivos `.otf`/`.ttf` convertidos a woff2 con fontTools.
Los originales estan en `~/Downloads/bebas-neue.zip` (con su OFL.txt) y
`~/Downloads/bella-fashion-font.zip`, junto con sus EULA.

Bebas Neue va subconjuntada a latin + latin-1 + comillas y guiones tipograficos
(`pyftsubset ... --flavor=woff2`): 10.9 KB en vez de 74 KB. Si algun dia un
titular necesita un caracter fuera de eso, hay que rehacer el subconjunto o
saldra en la fuente de cuerpo a mitad de palabra.

Consola Mono Bold va subconjuntada con `python -m fontTools.subset` a latin, latin-1,
latin extendido A, puntuacion tipografica, euro, flechas y `×`: 23.7 KB en vez de 346 KB.
Solo se incorpora el peso 700 (Book no). Ancho medio de caracter: 0.586 em.
