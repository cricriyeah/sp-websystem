# Diagnóstico CRO y plan de contenido: hub y páginas de sede

> 2026-10-16. Hecho con las skills `marketing-skills:cro` y `site-architecture`, el contexto de `.agents/product-marketing.md` y el análisis de competidores de `docs/marketing/analisis-competidores.md`. **Estado: propuesta, pendiente de la luz verde del dueño. No se ha tocado código ni el plan de frontend.**
>
> **Límite honesto:** el sitio no está lanzado, así que no hay tasas de conversión, mapas de calor ni preguntas reales de clientes. Todo lo de abajo son **hipótesis basadas en buenas prácticas y en competidores**, para validar con las primeras ventas. Competidores: Viator y GetYourGuide no se pudieron ver en móvil ni con sus botones fijos (se leyó el texto). Se revisó el código de las páginas, no su aspecto renderizado.

## 1. Lo que hay hoy

**Hub** (`app/[lang]/page.tsx`): encabezado, héroe con el titular «Tu próxima experiencia empieza en Baja» y un mapa interactivo → «Elige tu sede» (tarjetas con foto, nombre y enlace) → «Por qué…» (3 pilares) → marcas que colaboran → pie.

**Sede** (`app/[lang]/sede/[slug]/page.tsx`): héroe con video y selector de servicios destacados → «Acerca de» (historia de la colaboración) → empresas colaboradoras → paquetes → servicios sueltos → temporadas → galería → opiniones → preguntas frecuentes → pie.

## 2. Dónde falla (ordenado por impacto, con el marco de `cro`)

### Hub

| # | Hallazgo | Dimensión CRO | Severidad |
|---|---|---|---|
| H1 | El titular («Tu próxima experiencia empieza en Baja») y la misión («una alianza de agencias locales…») no dicen **qué se puede hacer** (pescar, ver ballenas, hospedarse) ni **por qué confiar**. | Propuesta de valor | Alta |
| H2 | El nombre de la marca es «Sal y Sol Baja Experiences», que además es el nombre de una de las empresas (Sal y Sol Sportfishing). El turista no distingue marca y operador. *(El cambio a Sun Baja Experience en F7 lo corrige; el texto debe ir con la marca nueva.)* | Claridad | Alta |
| H3 | Meta del hub = mandar a la sede correcta, pero hay **dos selectores** (mapa y tarjetas) en las dos primeras pantallas; las tarjetas solo muestran foto y nombre, **no dicen qué se hace ahí ni desde cuánto**. El turista busca «pesca» o «ballenas», no «sede». | CTA / fricción | Alta |
| H4 | La principal objeción («¿pago a un desconocido?») no se responde en ningún lado del hub. Los pilares («Alianzas locales de confianza») afirman sin demostrar. | Confianza / objeciones | Alta |
| H5 | No dice cómo se reserva ni cómo se paga (pago directo a cada empresa, 100 % o 30 % + efectivo, reembolso por clima). Es lo que ningún competidor explica bien. | Objeciones | Media |
| H6 | Las empresas aparecen al final; es información de confianza, pero llega tarde y se repite en cada sede. | Jerarquía | Media |

### Sede

| # | Hallazgo | Dimensión CRO | Severidad |
|---|---|---|---|
| S1 | **Cuatro de las nueve secciones (temporadas, galería, opiniones, preguntas) dicen «Estamos preparando esta sección» en La Ventana y Puerto Chale.** Parece un sitio a medias justo donde se pide confianza. | Confianza | Crítica |
| S2 | Las opiniones son de **ejemplo**. Publicadas, serían reseñas falsas; el resto de las secciones de confianza (licencia, seguro) no existen. | Confianza / honestidad | Crítica |
| S3 | «Acerca de» y las empresas ocupan el primer tramo **antes** de lo que se puede reservar; el producto aparece hasta la 4.ª sección. | Jerarquía / CTA | Alta |
| S4 | La grilla de paquetes va primero y, si no hay, muestra un bloque vacío («sin paquetes») en vez de ocultarse. En La Paz, el producto principal es un servicio suelto. | Fricción | Media |
| S5 | No hay un bloque que junte pago, cancelación, cambio de fecha, clima y **qué incluye cada servicio** cerca de los precios. Hoy lo cubre solo la FAQ, abajo y solo en La Paz. | Objeciones | Alta |
| S6 | Las empresas se listan con la descripción vacía (`descripcion: ''`): no se sabe quién opera, ni con qué experiencia. | Confianza | Media |
| S7 | Lo único confiable que hay, **las fotos propias**, está casi al final. | Prueba social | Media |
| S8 | La FAQ de La Paz y sus datos estructurados (JSON-LD) responden a una sola empresa y pueden contradecir a las demás. | Consistencia | Media |

## 3. Qué hacen los competidores (resumen)

- **Todos** repiten un solo CTA principal, muestran duración, grupo e idioma arriba, y llevan «Incluye»; solo GetYourGuide y Baja Wild Encounters también «No incluye». La pesca privada se cobra **por barco**.
- **Viator y GetYourGuide** meten La Ventana bajo «La Paz» y ninguno deja elegir sede dentro de un destino. Muestran reseñas con número y fuente («Verified booking»), cancelación en una línea y proveedor visible solo en GetYourGuide.
- **Los sitios de operadores** (Cabo Adventures, Baja Wild Encounters) tienen buen calendario de temporada y clima, pero sin reseñas, política de cancelación ni precios claros.
- **Nadie** hace lo que este sitio puede: selector de sede real, un solo carrito con varias empresas cobrando directo, calendario de temporada cruzado, dos modos de pago explicados con un ejemplo, política de clima concreta, precio en pesos y dólares a la vez, bilingüe real y una sección de opiniones que solo se pinta cuando hay reseñas confirmadas por la empresa. Detalle en el documento de competidores.

## 4. Estructura propuesta

### Principios (de `cro`, `site-architecture` y los competidores)
1. **Un solo propósito por página.** Hub = elegir sede. Sede = reservar; las dudas se resuelven al lado del producto, no al final.
2. **Nada de «pronto».** Una sección solo existe si tiene contenido real; si no, no se pinta (se acaba `SedePendingSection`).
3. **Nada falso.** Sin reseñas de ejemplo ni escasez inventada. Si no hay reseñas confirmadas, la sección de opiniones no se pinta (decisión del dueño, 2026-10-16: no hay fila «Recién abrimos»).
4. **La objeción central sube.** Cómo se paga y qué pasa si llueve va junto a los precios, no en una FAQ.
5. **Lo que se incluye es por servicio**, nunca promesa general (regla del dueño).
6. **Bilingüe real:** mismo orden y mismo peso en es y en.

### Hub (meta: mandar a la sede correcta)

1. **Héroe:** titular que diga qué se hace en Baja y a quién se compra; una línea de confianza («Reserva en línea con las empresas locales de cada sede»); un CTA «Ver las sedes». Marca nueva. Decisión del dueño (2026-10-16): titular «Reserva en Baja California Sur con las empresas locales»; héroe con un video del dueño de contenido neutro (varias sedes o Baja en general, sin audio) con poster inmediato; hasta que llegue, bloque de texto sobre arena con el mismo layout.
2. **Elegir sede (primera acción):** tarjetas con foto, **qué se puede hacer** (chips por actividad, con los colores de actividad del sistema de diseño), **empresas** que operan y **precio «desde»**. El mapa interactivo pasa a ser opcional (escritorio) o se queda como ayuda secundaria.
3. **Cómo funciona Sun Baja Experience (decisión del dueño):** explica la dinámica real: somos una empresa que reúne los servicios de distintas empresas locales en un solo lugar; cada empresa opera su servicio y cobra directo. Incluye las condiciones reales (pago directo a la empresa; 100 % en línea o anticipo + efectivo según el servicio; reembolso completo por mal clima; cambio de fecha con 48 h; valen igual en las 4 empresas). Reemplaza a los pilares genéricos.
4. **Mejor época por actividad y sede:** calendario cruzado (ningún competidor lo hace); solo cuando haya datos.
5. **Paquetes y combos** (hospedaje + traslado + pesca o ballenas): solo si existen.
6. **Quién opera cada servicio, directorio de empresas (decisión del dueño):** todas las empresas, cada una con enlace a su página oficial y sus redes, y su teléfono o WhatsApp solo si está confirmado; sin datos de relleno.
7. **Preguntas frecuentes globales** y contacto humano por WhatsApp.

### Sede (meta: reservar; secundaria: resolver dudas)

1. **Héroe:** foto o video real, titular con el beneficio y selector de lo destacado (como hoy), CTA único. La cabecera lleva dos marcas: Sun Baja Experience (agencia de turismo local) y la empresa protagonista de la sede, con la frase «Una colaboración entre Sun Baja Experience, agencia de turismo local, y {empresa}» (decisión del dueño, 2026-10-16).
2. **Qué puedes reservar:** servicios y paquetes **en un solo bloque**, agrupados por actividad, cada tarjeta con empresa que lo opera, «por persona» o «por grupo», «desde» y **su propia lista de qué incluye**. Se oculta lo que esté vacío.
3. **Reserva con tranquilidad:** pago (los dos modos con un ejemplo en dólares), cancelación y clima, cambio de fecha, y la nota «lo que incluye varía por servicio».
4. **Quién opera:** cada empresa con descripción, foto real y qué hace; sin licencias ni seguro hasta que existan para mostrarlos.
5. **Galería** (fotos propias): sube porque es la prueba de confianza disponible.
6. **Temporadas y mejor época** de esa sede.
7. **Cómo llegar / punto de encuentro**, por servicio cuando aplique.
8. **Opiniones (decisión del dueño):** se usan las reseñas que cada empresa ya publica en su propio sitio, siempre **atribuidas a la empresa** («Opinión publicada por X», con su fuente) y nunca como verificadas por Sun Baja Experience. Compuerta: antes de publicarlas, cada empresa confirma que son reales; las que no confirme se omiten. Si ninguna se confirma, la sección no se pinta. Nunca las de ejemplo del sitio.
9. **Preguntas frecuentes de esa sede.**
10. **Cierre:** el mismo CTA y WhatsApp.

## 5. Qué cambia en el código (para fusionarlo con el plan de frontend)

| Cambio | Toca |
|---|---|
| Titular, misión y marca del hub con la marca nueva | F7 (marca), contenido de `dict.hub` |
| Tarjetas de sede con actividades, empresas y «desde» | `hub-grid-sedes.tsx`, API de sedes; encaja con `ChipActividad` de la Task 3.3 |
| «Cómo reservas y pagas» (hub) y «Reserva con tranquilidad» (sede) | Componente nuevo `ReservaTranquila` (sin `Card` ni `AvisoEstado`: ver Task 9.2 del plan) |
| Unir paquetes y servicios, ocultar vacíos | `app/[lang]/sede/[slug]/page.tsx`, `paquete-card`, `servicios-sueltos-section` |
| Quitar `SedePendingSection` y renderizar condicional | misma página; elimina 4 placeholders |
| Reordenar: producto antes de «Acerca de» | misma página; se alinea con la Task 5.4 (`SectionShell`) |
| Reseñas reales confirmadas (sin ellas, la sección no se pinta) | `reviews-section.tsx`, `reviews-carousel.tsx` |
| FAQ y JSON-LD por sede, no por empresa | `faq-section.tsx`, `structured-data.tsx` |
| Empresas con descripción y foto | `sedes-cuerpo.ts` (`descripcion`) |

**Dependencias de contenido (del dueño):** sitios de las demás empresas (descripciones, servicios, fotos, qué incluye), logo y fotos definitivos, y reseñas reales cuando existan.

## 6. Hipótesis a validar después del lanzamiento

1. Mostrar «desde $X» y actividades en la tarjeta de sede aumenta el clic hacia la sede.
2. El bloque «Reserva con tranquilidad» junto al producto reduce abandonos del checkout por duda de pago.
3. Las opiniones atribuidas y confirmadas por cada empresa aumentan el clic hacia «Ver y reservar» frente a una sede sin ellas.
4. Quitar el mapa como selector principal no baja el clic en móvil.
Medir con eventos del sitio (clic en tarjeta de sede, inicio de checkout, abandono por paso) y con las preguntas reales de WhatsApp de las primeras semanas.

## 7. Decisiones del dueño (2026-10-16) y hallazgos de los sitios de las empresas

- **La Ventana Travel:** el catálogo cargado (pesca con mosca, ballenas y orcas, hospedaje, traslado, paquetes) es lo que el cliente quiere mostrar de momento. Su sitio actual lista otras actividades (buceo, kayak, hike, paddle board, kitesurf) y es de plantilla; no se toma como fuente del catálogo.
- **Sal y Sol Sportfishing (La Paz):** su información e imágenes ya son correctas.
- **Hub:** lleva una sección que explica la dinámica real del sitio y otra con todas las empresas y sus enlaces (puntos 3 y 6 de arriba).
- **Reseñas:** se usan las que ya publican las empresas, atribuidas y con confirmación previa de la empresa. *Riesgo conocido:* en los sitios revisados hay reseñas que parecen de plantilla (la única de La Ventana está fechada en 2018 y usa una foto de recurso de plantilla; las 5 de DLS repiten un nombre genérico y usan avatares de banco). Esas no pasan la compuerta si la empresa no las confirma.
- **Contacto:** el sitio muestra solo datos confirmados. El WhatsApp de Piratas (+52 612 123 4567) parece de relleno, los enlaces de privacidad y términos de su landing van a `#`, y el botón «Reservar» de eventos de DLS vuelve a la portada: no se importan hasta que la empresa los confirme.
- **Enlace al sitio oficial (decisión del dueño, 2026-10-16):** se enlaza el de DLS Transporte, La Ventana Travel y Piratas Adventures; Sal y Sol no lleva enlace externo (su sitio es este). El dueño decide así sabiendo que el sitio de La Ventana lista otras actividades y que el de Piratas es un borrador en vercel.app, y se compromete a tenerlos al día antes de lanzar.
- **Fotos:** solo las que cada empresa confirme como propias; las del sitio de La Ventana (Pexels) y las de relleno (Unsplash) no se usan.
- Detalle por empresa y preguntas abiertas: `docs/marketing/contenido-empresas.md`.
