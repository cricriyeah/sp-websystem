# Análisis de competidores — Sun Baja Experience

Fecha de la investigación: 2026-10-16. Las páginas de GetYourGuide mostraban "Published Time: 13 Oct 2026".

## 0. Método y límites (leer primero)

- **Viator y GetYourGuide bloquean la lectura directa** (HTTP 403 con WebFetch y con curl). Las páginas se leyeron con un lector de texto de terceros (r.jina.ai) que devuelve el texto de la página renderizada. Eso da el **orden del contenido y los textos**, pero **no confirma** comportamiento visual: si un botón es sticky, qué hay en un acordeón cerrado, o el diseño en móvil. Esos puntos se marcan "no verificado".
- Dos páginas de producto de Viator solo abrieron con la variante `/en-GB/` de la URL (la versión `/tours/...` devolvió captcha). Los precios salen en US$ de todos modos.
- El navegador de Chrome (extensión) no estaba conectado, así que no hubo capturas de pantalla ni prueba de móvil.
- Las páginas de resorts/hoteles de La Ventana / East Cape que vendan tours con precio casi no existen. Lo más cercano fue **Costa Palmas** (resort del East Cape) y dos **operadores directos**: **Cabo Adventures** (hace safari desde La Ventana) y **Baja Wild Encounters** (La Ventana). Se usan los tres como competidores 3 y 4, más Costa Palmas como contraste de "resort".
- "No hay X" significa que no aparece en el texto leído, no que sea imposible que exista en un elemento que no se renderizó.
- No se encontró ni abrió una página de destino propia de GetYourGuide para La Ventana (`/la-ventana-l193099/` devolvió vacío). Sí existe un producto bajo ese ID de ubicación.

---

## 1. Viator

### 1.1 Página de destino: La Paz
URL: https://www.viator.com/La-Paz/d22173-ttd (título: "THE BEST 20 Tours & Experiences in La Paz, Baja California Sur (October 2026)"; "100+ results")

**Orden de secciones (arriba a abajo):**
1. Barra superior: "a Tripadvisor company", Discover, Log in.
2. Migas de pan: Home > Things to do in Mexico > Baja California Sur > La Paz > La Paz Tours.
3. H1 "All La Paz Tours & Excursions in 2026".
4. Selector de fecha y personas: "Select Dates" / "2 Adults".
5. Chips de filtro por categoría: Private Drivers, Kayaking Tours, Cruises & Sailing, Snorkeling, Day Trips, Whale Watching, Nature and Wildlife Tours, Sightseeing Tours, Jet Boat Rentals, Water Tours.
6. "100+ results" y "Sort by: Featured".
7. Tarjetas de producto (20 por página, paginación 1 2 3...8). Cada tarjeta: foto (carrusel de 7), etiqueta opcional ("Best Seller", "Likely to Sell Out", "Special Offer"), descripción larga, duración, "Free Cancellation", rating con número de reseñas, "from $".
   Ejemplo de tarjeta: "Ocean Safari: Sea Lions, Mobula Rays, Dolphins, Orcas & Whales 5 hours Free Cancellation 4.9 (122) from $167".
8. Bloque "What are people saying about La Paz": 12 reseñas recientes (usuario abreviado + mes/año + texto), cada una con botón "Check Availability".
9. Enlaces SEO: More Tours in La Paz, Attractions in La Paz, Things to do near La Paz, Popular on Viator (categorías).
10. Pie de página.

**Confianza:** rating con número en cada tarjeta; etiquetas de escasez/popularidad; reseñas con nombre de usuario y fecha. No hay licencias ni seguros en la lista.
**Precio:** "from $X" (sin explicar de qué depende) en la tarjeta.
**Cancelación:** solo "Free Cancellation" como etiqueta en la tarjeta.
**CTA:** el único visible en el texto es "Check Availability" en el bloque de reseñas; en las tarjetas el clic lleva al producto.
**Elegir:** fecha, personas, categoría (chips), orden. **No hay filtro por proveedor ni por zona dentro de La Paz** (La Ventana y Espíritu Santo aparecen mezclados bajo "La Paz").
**Varios proveedores:** cientos de operadores en una lista única, ordenados por "Featured". Un producto de La Ventana (Ocean Safari) aparece listado bajo La Paz.
**Idioma:** inglés en la versión leída. El producto indica "Offered in: English and 2 more". No verificado si hay UI en español completa.
**Bien:** filtros por actividad claros; "Free Cancellation" visible desde la lista; reseñas de destino con texto real; migas de pan.
**Mal:** descripciones larguísimas en tarjeta (el Ocean Safari repite media página de contexto estacional); sin transparencia de quién opera hasta entrar al producto; la lista mezcla paseos de turista general con safaris serios; aparecen disclosures de ranking comercial (ver producto).

### 1.2 Página de producto: Ocean Safari (La Ventana, vendido bajo La Paz)
URL: https://www.viator.com/en-GB/tours/La-Paz/Ocean-Safari-in-La-Ventana/d22173-296255P5

**Orden de secciones:**
1. Menú de anclas: Overview · What's Included · Meeting and Pickup · What To Expect · Additional Info · Cancellation Policy · Reviews (si es sticky: no verificado).
2. Migas de pan (hasta "Whale Watching").
3. H1 + "122 Reviews" + "Recommended by 97% of travellers" + "Badge of Excellence" + ubicación "La Paz, Mexico" + "Lowest Price Guarantee" + "High interest / Booked 3 times today".
4. Datos rápidos: "5 hours (approx.)", "Mobile ticket", "Offered in: English and 2 more".
5. "Explore our promoted experiences": 8 tarjetas de la competencia con rating y precio, con la nota "Viator earns higher commissions on experiences featured here".
6. Overview (texto largo con calendario estacional: marzo-junio mobulas/orcas, jul-dic agua cálida, invierno ballenas).
7. What's Included: "All Fees and Taxes, Use of Snorkelling equipment, Lunch, Private transportation". (No hay lista "No incluye" en el texto leído.)
8. Meeting and Pickup: dirección exacta (Muelle Fiscal, La Paz), punto final, hora de inicio 09:00.
9. What To Expect.
10. Additional Info: máx. 8 viajeros, no apto para espalda/embarazo, no accesible en silla de ruedas; "Supplied by Mexico Travel Adventure".
11. Cancellation Policy: "You can cancel up to 24 hours in advance of the experience for a full refund."
12. Preguntas / Help Centre; código de producto.
13. Fotos de viajeros; reseña destacada.
14. Reseñas: "4.9 based on 122 reviews", "Total reviews and rating from Viator & Tripadvisor", histograma 114/4/4/0/0, enlace "We perform checks on reviews", reseñas con fecha, enlace "See 116 more reviews on Tripadvisor".
15. Caja de compra (lateral): "Likely to Sell Out", "From US$166.64 per person", Date / Travelers / Start time, botón "Check Availability", "Free cancellation up to 24 hours before the experience starts (local time)", "Reserve Now and Pay Later", "On average, this is booked 41 days in advance".
16. "Compare Similar Experiences" (tabla: reseñas, duración, cancelación, precio).

**Confianza:** número de reseñas + fuente declarada (Viator y Tripadvisor) + histograma + "We perform checks on reviews" + insignia "Badge of Excellence" + "Recommended by 97%". Proveedor nombrado ("Supplied by …"). Fotos de viajeros. Sin licencias, seguros ni permisos en el texto de esta página (la ficha de la ballena tiburón de otra página sí habla de permisos CONANP en la descripción de un competidor).
**Precio:** "From US$166.64 per person" con fecha/viajeros/hora; el precio real depende de esos tres campos.
**Qué incluye:** lista corta. **Qué no incluye:** no aparece en el texto leído.
**Cancelación:** una línea, 24 h antes, reembolso completo, repetida en la caja de compra.
**Clima:** **no hay política de clima en el texto leído** (el "What To Expect" solo advierte que cada día es distinto y que las orcas no se ven a diario; el bloque "Show more" de cancelación no se expandió, así que puede haber más texto no verificado).
**CTA:** "Check Availability" (principal, único). Secundario: "Reserve Now and Pay Later" (texto de apoyo). Presión: "Likely to Sell Out", "Booked 3 times today", "booked 41 days in advance". Repetido en la caja de compra; sticky no verificado.
**Varios proveedores:** el proveedor aparece como nota de pie ("Supplied by"), no como marca protagonista; el modelo es "Viator vende, otro opera".
**Idioma:** UI en inglés (en-GB), tour ofrecido en inglés + 2 idiomas. Reseñas en varios idiomas (una en francés).
**Bien:** la misma página resuelve confianza, precio, cancelación y comparación; fuente de reseñas explícita; dirección exacta del punto de encuentro.
**Mal:** presión de escasez agresiva y "promoted experiences" que se paga; el operador es casi invisible; el precio "from" cambia al elegir fecha/personas; no hay política de mal clima.

### 1.3 Segunda página de producto (comparación): Whale Shark, La Paz
URL: https://www.viator.com/en-GB/tours/La-Paz/La-Paz-Whale-Shark-Experience/d22173-203550P1 — mismo esqueleto. Diferencias: bloque "Why travellers loved this" (5.0, 454 reseñas, 5 reseñas arriba) **antes** del Overview, "Recommended by 100% of travellers", "Popular pick / Booked 10+ times last week!". "Supplied by Tuna Tuna Tours". Misma política de cancelación de 24 h.

---

## 2. GetYourGuide

### 2.1 Página de destino: La Paz, Mexico
URL: https://www.getyourguide.com/la-paz-mexico-l2930/ (79 resultados)

**Orden de secciones:**
1. Cabecera: búsqueda, "EN/USD $" (selector de idioma y moneda), perfil, "Explore La Paz, Mexico", pestañas "Places to see / Things to do".
2. Barra de filtros: Filters, Dates, y chips de categoría: Sea lions, Shark & ray safaris, Sandboarding/Mangroves, Boat cruises, Snorkeling, Day trips, Shark diving, Shore excursions, Dolphins & whales, Quads & ATVs, Culture & history, Sailing, Seal watching, Canoes & kayaks, Diving. Botón "Open map".
3. "79 results" + H1 "La Paz, Mexico".
4. Texto de transparencia: "How GetYourGuide ranks activities... Activities are ranked by popularity, customer ratings, performance, availability, diversity, and revenue (including supplier commissions)."
5. Tarjetas. Formato real: título, duración, atributos ("Small group", "Private option available", "Pickup available", "Skip the line"), etiqueta ("Top pick", "New activity"), rating con número ("4.9 (241)"), "From $124". Ejemplo: "La Paz 6-Hr Private Sea of Cortez Fishing Outing 6 hours • Private group From $919 $827 per group up to 5".
6. "Show more" (carga más).
7. Pie con idioma/moneda, soporte, empresa, "Work With Us / As a Supply Partner", formas de pago.

**Confianza:** rating y número en tarjetas (muchas "New activity" **sin reseñas**, lo cual es la situación de Sun Baja hoy); etiqueta "Top pick"; atributos como "Small group". 
**Precio:** "From $X"; precio **por grupo** para privados ("per group up to 5"), con precio tachado.
**Cancelación/clima:** no en la tarjeta.
**CTA:** en la lista no hay botón; toda la tarjeta es el enlace.
**Elegir:** fecha, categoría, mapa, atributos de grupo (privado/pequeño). Sin filtro por proveedor.
**Varios proveedores:** un listado único con productos de decenas de operadores (en La Paz, un mismo producto "Sea Safari: Wildlife Encounters in La Ventana" convive con tours desde Cabo). Hay productos "desde Cabo" en el listado de La Paz.
**Idioma:** selector EN + moneda; la misma URL aparece con locales en otros idiomas en resultados de búsqueda (es, de, fr).
**Bien:** atributos escaneables en cada tarjeta ("Small group", "Private option", "Pickup"); precio por grupo claro; transparencia sobre el ranking; categorías de intención específicas (Dolphins & whales, Shark & ray safaris).
**Mal:** muchos "New activity" sin reseñas se ven igual de prominentes; no hay estado por zona dentro de La Paz; resultados que no son de La Paz (Cabo).

### 2.2 Página de producto: Ocean Safari (La Ventana)
URL: https://www.getyourguide.com/la-ventana-l193099/ocean-safari-sea-lions-dolphins-mobulas-orcas-and-whales-t1339342/

**Orden de secciones:**
1. Cabecera y H1.
2. "5 · 4 reviews" + "Activity provider: Mexico Travel Adventure" (proveedor nombrado arriba, junto al título).
3. Resumen de 2 líneas.
4. Dos garantías: "Free cancellation — Cancel up to 24 hours in advance for a full refund" y "Reserve now & pay later — Keep your travel plans flexible".
5. Datos: "Duration 5 hours", "Live tour guide English, French, Spanish", "Small group — Limited to 6 participants".
6. "What travelers loved" (2 reseñas destacadas, "Verified booking", nombre + país + fecha).
7. Highlights.
8. Full description (incluye "nothing can be guaranteed", "we do not engage in the harassment of wildlife").
9. Includes / lista de **no incluye** en la misma sección (Alcoholic drinks, Scuba diving, Tips, Extra hours).
10. Meeting point (con mapa).
11. Important information / Know before you go.
12. Caja de compra: "Likely to sell out", "From $162 per person", Adult x 1, Select date, idioma, "Check availability", garantías repetidas.
13. Customer reviews: "5.0/5 Based on 4 reviews", orden/filtro, reseñas "Verified booking" con país, traducción ("Show original (Español)"), "Was this helpful?".
14. Product ID y proveedor.

**Confianza:** "Verified booking" en cada reseña, país del reviewer, proveedor nombrado en el encabezado. Con 4 reseñas se muestra igual, sin inflar.
**Precio:** "From $162 per person" + Adult x 1.
**Incluye / no incluye:** ambas, claras (en el producto de pesca: licencias, permisos de parque marino, limpieza de captura, bebidas; no incluye alcohol).
**Cancelación:** dos veces (arriba y en la caja de compra), "24 hours in advance for a full refund". En otro producto (Cabo Trek) la política dice "Policy type: Standard" y **menciona clima**: "You may reserve the right to cancel a customer's booking for a full refund in case of: Bad weather, Not enough travelers".
**CTA:** "Check availability" (único). Secundario: "Reserve now & pay later" como beneficio. Repetido arriba (garantías) y en caja de compra; sticky no verificado.
**Idioma:** guía en English, French, Spanish; reseñas traducibles.
**Bien:** proveedor arriba; reseñas verificadas; incluye/no incluye separados; "Reserve now & pay later" como argumento; honesto con pocas reseñas.
**Mal:** la política de clima sólo aparece en algunos productos; no ofrece pago parcial (30% + resto efectivo) ni nada parecido; "Answers are generated by AI" (módulo de preguntas con IA).

### 2.3 Página de producto de pesca: 6-Hr Private Sea of Cortez Fishing Outing
URL: https://www.getyourguide.com/la-paz-mexico-l2930/la-paz-private-sea-of-cortez-fishing-charter-t1491017/ — "New activity", "Activity provider: La Paz Tiki Tours", sin reseñas. Incluye: licencias de pesca, permisos de parque marino, carnada, limpieza y fileteo; **no incluye** alcohol. Precio "$919 $827 per group up to 5" (precio por barco). Listado de "Know before you go": opera todo el año, especies varían por temporada. Sin política de clima en el texto leído. Útil como ejemplo de pesca presentada por **grupo/barco**, no por persona.

---

## 3. Costa Palmas (resort del East Cape, "hotel con concierge")

### 3.1 Destino: East Cape
URL: https://costapalmas.com/discover/east-cape/

**Orden:** (1) menú (Resorts & Real Estate, Location & Experiences, About) + CTA "Inquire"; (2) intro "THE EAST CAPE" ("It's the road less traveled in Cabo."); (3) "SEA OF CORTEZ" (cita de Cousteau: "The World's Aquarium"); (4) "EXPERIENCES" (vela, pesca, paddle, kite, buceo, ATV) con "Learn More"; (5) "GETTING HERE" (45 min del aeropuerto de Los Cabos); (6) "101 THINGS TO DO ON THE EAST CAPE" (tarjetas 01-09, lista hasta 92) con "View More"; (7) "Homes for Sale" (US$5,750,000); (8) formulario "DISCOVER YOUR DREAM AT COSTA PALMAS" ("Register for pricing and details"); (9) banner "Come Home to the Sea of Dreams" con "Inquire Now"; (10) pie.
**Pesca y ballenas:** tarjetas de una línea (item 03 "Deep-Sea Fishing" marlín, dorado, atún; item 04 "Whale Watching" ballenas gris y jorobada) **sin operador, precio ni botón de reserva**.
**Confianza:** marcas (Four Seasons, Aman, chef con estrella Michelin); **sin reseñas ni cifras**.
**Precio:** ninguno; "Register for pricing and details".
**CTA:** "Inquire" / "Inquire Now" / "Discover More", repetido arriba y al final. No hay motor de reservas. Solo inglés.
**Bien:** "Getting here" con tiempos reales desde el aeropuerto; narrativa de lugar fuerte ("road less traveled"). **Mal:** no se puede reservar ni ver precio; el servicio de pesca/ballenas es relleno de venta inmobiliaria.

### 3.2 "Producto": excursión por concierge
URL: https://costapalmas.com/blog/5-excursions-to-try-in-los-cabos-that-are-led-by-locals/ (blog de 2023). Cinco excursiones numeradas (Whale Shark Encounter, Todos Santos, Sport Fishing, Sunset Cruise, Guided Snorkel). Sin precios, sin botón por excursión, sin duración en algunas. Se nombra al "Costa Palmas Adventura team" y a un guía local (Sebastian Melani, descrito como "world record-holding spearfisherman"). Seasonal/clima: "Seasonal (December to March) and weather-dependent" en la ballena tiburón. Cierra con un formulario de compra de propiedad.
**Lección:** el resort **no** vende el tour; el concierge lo coordina por mensaje. Hay confianza por **nombre propio del guía**, pero sin reservar.

---

## 4. Cabo Adventures (operador directo, safari desde La Ventana)

### 4.1 Producto: "Orca Encounter, Whales & Baja's Ocean Giants"
URL: https://www.cabo-adventures.com/en/tour/ocean-safari

**Orden:** (1) cabecera con menú (Tours, Dolphins, Whales & Wildlife, Private, New Year, Special Offers) y selector "ENG"; (2) migas Tours / Whales & Wildlife / …; (3) galería 1/8; (4) H1; (5) datos clave: 12 horas, "Min 8 years old", etiquetas Active / Sea Lovers / Adventurers / Families; (6) botón **BOOK NOW**; (7) bloque de contacto (teléfonos USA/Canadá y México, WhatsApp, email, horario "6:30 AM – 7:30 PM MST"); (8) intro; (9) "Seasonal Wildlife Calendar" (invierno/primavera/verano/otoño); (10) "Snorkeling & Ocean Adventures"; (11) "Why Choose Us?"; (12) "What to Expect": What's Included (6 viñetas) + Essential Information (edad, peso 265 lb, hotel pickup, política de clima); (13) narrativa de la expedición (7:00 a.m. desde Cabo, 2.5 h de camino, panga con grupos de 7); (14) highlights de snorkel; (15) "A Perfect Ending"; (16) "Responsible Tourism" (no garantizan avistamientos); (17) What to Bring; (18) FAQs (5).
**Confianza:** casi no hay prueba social **en el texto leído**: sin conteo de reseñas ni fuente, sin licencias/seguros mostrados; sí un contacto humano muy visible (teléfono, WhatsApp, horario). Menciona operadores "SEMARNAT-approved" en las FAQ.
**Precio:** **no se muestra** en la página leída (se calcula en el flujo de reserva, no verificado).
**Cancelación:** solo una línea de clima: "we reserve the right to cancel a tour without prior notice for safety reasons". Sin términos de reembolso en la página (hay un enlace "Reservation & Cancellation" en el pie).
**CTA:** "BOOK NOW" (arriba). Sin selector de fecha/personas visible. Sticky: no verificado.
**Idioma:** "ENG" únicamente en el texto leído.
**Bien:** el calendario estacional (qué verás en qué mes) y la sección "no garantizamos avistamientos" generan expectativas honestas; contacto humano completo; FAQ concreto ("swimming with orcas in La Ventana").
**Mal:** sin precio ni reseñas visibles; la política de clima es unilateral y vaga; inconsistencia interna (el transporte "incluido" vs. solo con hotel elegible y reserva con 24 h); ubicación ambigua (La Ventana descrita como parte de La Paz, salida desde Cabo).

### 4.2 Categoría: Whales & Wildlife
URL: https://www.cabo-adventures.com/en/tours/whales-wildlife — el texto leído solo trajo la barra de categorías (All Tours, Boat Tours, Camels, Dolphins, Beach & Adventure, City Tours, Whales & Wildlife, Scuba Diving, Private Tours), formulario de newsletter, contactos y enlaces a políticas ("Reservation & Cancellation", Affirm). **No se pudieron ver las tarjetas** (la página mostraba "Collection Not Found" en el render leído). Se documenta solo lo anterior. Destacable: enlace a "La Paz & Sea of Cortez" como categoría y logos de marcas hermanas (Vallarta Adventures, Cancun Adventures).

---

## 5. Baja Wild Encounters (operador directo pequeño, La Ventana)

### 5.1 Portada
URL: https://bajawildencounters.com
**Orden:** (1) menú Day Tours / Expeditions / More, carrito; (2) hero "BAJA WILD ENCOUNTERS — Journey with Purpose" + "Book noW" con 3 enlaces (Day Tours, Multi-Day Expeditions, Contact us); (3) insignia TripAdvisor "Travelers' Choice 2023 and 2024" + frase; (4) Expeditions (3 tarjetas con fecha: oct-dic marlín y sardina, feb-mar ballena gris, abr-jun mobulas) + "tap to SEE ALL"; (5) Day trips (La Ventana Snorkel Tour, Ocean Safari Pacific Offshore, Gray Whales in Mag Bay); (6) "Small Boats — Big adventures!"; (7) "Our beliefs": Ethical / Sustainable / "No bullshit" (promete expectativas honestas); (8) enlaces rápidos; (9) pie con teléfono/WhatsApp y email.
**Se organiza por temporada y actividad, no por destino.** Un solo credencial de terceros (TripAdvisor); sin permisos, sin cifras de reseñas. Solo inglés.

### 5.2 Producto: La Ventana Whale Watching
URL: https://bajawildencounters.com/la-ventana-whale-watching

**Orden:** (1) hero "Baja California Whale Watching ADVENTURE"; (2) intro con temporada dic-mayo; (3) bloque del tour: botón **Book Now**, horario "From 7am to 1 - 2pm", punto de encuentro ("Boat Ramp behind Playa Central, La Ventana"), incluye (guía, bebidas, comida ligera, fotos y video), **no incluye** ("Transaction fees; tips/gratuity (optional)"), qué llevar, precio "$3,500 MXN pesos per person", "Click here to reserve", depósito mínimo 50%; (4) "Tour information" + otro Book Now; (5) charter privado con precio por tamaño de grupo ($18,000 / $24,000 / $30,000 MXN para 4 / 6 / 8) y botón "Book Private Boat Now"; (6) "What Animals can you see" (calendario por especie y mes) + Book Now; (7) "Why Baja Wild Encounters?" + Book Now; (8) condiciones: temperatura del agua y del aire por mes; **política de clima**: "If the wind reports show the wind to be too strong and not enjoyable we will have to reschedule the trip."; nota "November to April is the wind season, and September is storm season"; (9) "LA VENTANA Information": aeropuertos (La Paz ~45 min, San José del Cabo ~2.5 h); (10) galería de ~20 fotos; (11) enlaces y contacto.
**Confianza:** fotos reales de animales propios, honestidad sobre estacionalidad y viento. Sin reseñas ni permisos mostrados en esta página.
**Precio:** en **pesos mexicanos**, por persona y por barco; **depósito 50%**.
**Cancelación:** no hay política de reembolso propia; sí política de reprogramación por viento.
**CTA:** "Book Now" repetido 5 veces (sticky no verificado), más "Click here to reserve".
**Bien:** la mejor información de **clima y temporada** de todos los analizados; precio abierto, depósito claro, aeropuertos y logística; tono honesto. **Mal:** solo inglés; sin reseñas; sin cancelación; precio solo en MXN (el turista EE. UU./Canadá tiene que convertir); depende de un enlace externo para reservar (WeTravel).

---

## 6. Resumen comparativo rápido

| | Viator | GetYourGuide | Costa Palmas | Cabo Adventures | Baja Wild Encounters |
|---|---|---|---|---|---|
| Reseñas con número y fuente | Sí (Viator + Tripadvisor, histograma) | Sí ("Verified booking", país) | No | No visible | Solo insignia TripAdvisor |
| Precio visible | "From US$" | "From $" (por persona o grupo) | No | No | MXN, por persona y por barco |
| Incluye / no incluye | Solo incluye | Ambos | No | Solo incluye | Ambos |
| Cancelación en página | 24 h, reembolso total | 24 h, reembolso total | No | Solo "por seguridad" | Solo reprogramación por viento |
| Clima explícito | No | A veces | "weather-dependent" | Línea unilateral | Sí, detallado |
| Proveedor visible | Pie ("Supplied by") | Arriba junto al título | Concierge propio | Marca propia | Marca propia |
| Idioma de la UI | EN | EN + selector | EN | EN | EN |
| CTA | Check Availability | Check availability | Inquire | BOOK NOW | Book Now |

---

## A. Patrones comunes que todos usan

1. Un **CTA principal único** con verbo de acción y repetido (Check Availability / BOOK NOW / Book Now / Inquire). Ninguno usa más de 2 verbos distintos.
2. **Duración, tamaño de grupo, idiomas y edad mínima** en un bloque de datos rápidos arriba (los 5 lo hacen en alguna forma).
3. **Incluye** siempre; "No incluye" solo en GYG y Baja Wild Encounters.
4. **Calendario por temporada** (qué especie en qué mes): los 5 lo tienen.
5. **Punto de encuentro con dirección exacta** (Viator, GYG, Baja Wild Encounters).
6. **Garantías de flexibilidad** en la caja de compra (cancelación 24 h + "pay later").
7. **Honestidad sobre avistamientos no garantizados** ("nothing can be guaranteed").
8. **Reseñas con nombre abreviado, país o fecha** donde existen.
9. **Chips de categoría por actividad** (no por empresa) en las páginas de destino.
10. **Descripciones largas pero con listas** (highlights, includes, what to bring).
11. **Pesca privada se vende por barco/grupo**, no por persona (GYG: "per group up to 5"; BWE: por tamaño de grupo).
12. **Sin selector de sede/zona dentro del destino**: el viajero ve "La Paz" aunque el tour sea en La Ventana.

## B. Secciones candidatas

### B.1 Página de sede (10 secciones, en orden sugerido)

| # | Sección | Quién la usa | Problema del turista que resuelve |
|---|---|---|---|
| 1 | Hero: nombre de la sede + una frase de qué se hace aquí + CTA único ("Ver fechas") | Viator, GYG, Cabo Adventures | "¿Estoy en el lugar correcto?" en 3 segundos |
| 2 | Selector rápido: actividad + fecha + personas (chips de actividad) | Viator, GYG | Llegar a lo que busca sin leer; reduce carga cognitiva |
| 3 | Tarjetas de servicios con dato escaneable: duración, "grupo pequeño / privado", precio "desde" y por qué ("por persona" / "por barco") | GYG, Baja Wild Encounters | Comparar sin entrar a cada ficha |
| 4 | Calendario por temporada (qué verás, qué mes) | Cabo Adventures, Baja Wild Encounters | "¿Voy en buen mes? ¿habrá ballenas/orcas?" |
| 5 | Bloque de confianza: quién opera (nombre real y foto del capitán/guía), permisos/seguro/licencia, política de seguridad | Costa Palmas (guía con nombre), GYG (proveedor arriba) | "¿Es seguro y legal? ¿quién me lleva?" |
| 6 | Reseñas con número y fuente (o, mientras no existan, una fila honesta: "Abrimos en 2026; así trabajamos" + fotos reales de salidas propias) | Viator, GYG | Miedo a un operador desconocido |
| 7 | Cómo funciona el pago y la cancelación (100% en línea o 30% + resto en efectivo; reembolso; qué pasa si hay mal clima) | GYG (cancelación dos veces), BWE (depósito 50%, clima) | Miedo a perder dinero; es la mayor duda de un turista internacional |
| 8 | Clima y mar: reglas de viento, temporada de tormentas, qué pasa si se cancela | Baja Wild Encounters (el mejor) | "¿Y si el día está feo?" |
| 9 | Cómo llegar / logística: aeropuerto más cercano y tiempos, dónde es el punto de encuentro, traslado y hospedaje | BWE (aeropuertos), Costa Palmas ("Getting here") | Llegar al lugar; cruza con hospedaje y traslado de la sede |
| 10 | Preguntas frecuentes + contacto humano (WhatsApp, horario, idioma) | Cabo Adventures | Duda final antes de pagar |

(Opcional 11: "Otras sedes cercanas" con 1 línea cada una, para cruzar a La Paz / La Ventana / Puerto Chale sin salir del hub.)

### B.2 Hub / portada (6 secciones)

| # | Sección | Quién la usa | Problema del turista que resuelve |
|---|---|---|---|
| 1 | Hero con pregunta "¿Qué quieres hacer?" + elección de sede o actividad en un clic | GYG, Viator (buscador) | Mandar a la sede correcta sin que el turista conozca la geografía de BCS |
| 2 | Mapa simple de Baja California Sur con las 3 sedes y distancias entre ellas (aeropuerto incluido) | Costa Palmas ("Getting here"), BWE (aeropuertos) | "¿Dónde queda esto y cuánto tarda llegar?" |
| 3 | Tarjetas por sede (qué hace cada una, mejor temporada, precio "desde") | GYG (tarjetas de destino) | Elegir sede por actividad y época |
| 4 | "Mejor mes para cada cosa" (calendario cruzado entre sedes: pesca, ballenas, orcas, mobulas) | Cabo Adventures, BWE (por sede) | Planear fechas de viaje |
| 5 | Garantías comunes: pago, cancelación, idioma, quiénes son las empresas | GYG (garantías arriba), Viator | Confianza en una marca que no conocen |
| 6 | Combinar sedes en un solo viaje (paquetes / ruta) | Ninguno (ver C) | Armar un viaje de varios días sin 3 formularios |

## C. Lo que NINGÚN competidor hace y podría diferenciar a Sun Baja Experience

1. **Selector de sede dentro del destino**: Viator y GYG meten La Ventana bajo "La Paz" y mezclan productos desde Cabo. Una sede con su zona real, aeropuerto y tiempos resuelve eso.
2. **Un solo carrito para varias empresas de la misma zona**, con cobro directo a cada empresa pero un resumen único (ya diseñado en el checkout unificado). En Viator/GYG el carrito es de la plataforma; en los operadores directos, de uno solo.
3. **Calendario de temporada cruzado entre sedes y especies** (ballenas, orcas, mobulas, pesca por especie, viento): cada operador muestra solo el suyo.
4. **Pago en dos modos explicados en la ficha** (100% en línea o 30% + resto en efectivo) con un ejemplo en dólares. Nadie lo muestra; GYG/Viator solo ofrecen "pay later".
5. **Política de clima con reglas concretas y la misma para todas las empresas del marketplace** (quién decide, plazo, qué se devuelve). Solo Baja Wild Encounters da algo, y es parcial.
6. **Proveedor nombrado arriba, con rostro, permisos y seguro** en cada ficha. En Viator el operador está al pie; en Costa Palmas solo hay un guía con nombre en un blog.
7. **Precios en USD y MXN visibles a la vez** con tipo de cambio (BWE solo MXN; Viator/GYG solo USD).
8. **Bilingüe real (es/en) con contacto humano en ambos idiomas y horario local**; los operadores directos son solo inglés, y los marketplaces tienen la UI en inglés en las páginas leídas.
9. **Combo hospedaje + traslado + pesca/ballenas en la misma sede** (La Ventana), con itinerario conjunto.
10. **Honestidad radical de "recién abrimos"**: en vez de ocultar la falta de reseñas, mostrar cómo se opera y garantías.

## D. Riesgos y malas prácticas a evitar

1. **Escasez fabricada** ("Booked 3 times today", "Likely to Sell Out"): con el volumen real de una sede nueva sería falso o fácil de contradecir. No copiarlo.
2. **Reseñas o insignias inventadas.** No hay reseñas reales aún: no mostrar "4.9" ni insignias de TripAdvisor que no se tengan. GYG muestra actividades "New activity" sin reseñas sin maquillar; seguir ese ejemplo.
3. **Ranking pagado sin avisar.** Viator ("Viator earns higher commissions on experiences featured here") y GYG lo declaran; si el hub ordena empresas, decir con qué criterio.
4. **Precio "desde" que cambia al elegir fecha/personas** sin explicar de qué depende (Viator). Decir "por persona" o "por barco hasta N".
5. **Política de clima unilateral y vaga** ("we reserve the right to cancel... for safety reasons", Cabo Adventures) sin reembolso explícito. Escribir qué pasa y cuánto se devuelve.
6. **Contradicciones internas** (transporte "incluido" vs. solo con condiciones, Cabo Adventures): revisar que "incluye", "no incluye" y las notas no se contradigan.
7. **Ubicación ambigua** (La Ventana descrita como La Paz): nombrar la sede real y el punto de encuentro exacto.
8. **Fichas largas con el mismo contexto repetido en tarjeta y página** (Viator). Mantener tarjetas escaneables.
9. **Formulario sin precio** (Costa Palmas: "Register for pricing and details"): el turista de EE. UU./Canadá que llega por Google quiere precio antes de dar datos.
10. **Solo inglés o solo pesos**: excluye a turistas nacionales o complica a los extranjeros.
11. **Depender de un enlace externo para reservar** (BWE usa WeTravel): rompe confianza y medición.
12. **Prometer avistamientos.** Ningún operador serio garantiza orcas/ballenas; la página debe decirlo igual (varios lo hacen).
13. **Presentar como propias reseñas de otras plataformas** o mezclar las de varias empresas bajo la marca paraguas sin decir de cuál empresa es cada una.

---

## Fuentes (URLs efectivamente abiertas)
- https://www.viator.com/La-Paz/d22173-ttd
- https://www.viator.com/en-GB/tours/La-Paz/Ocean-Safari-in-La-Ventana/d22173-296255P5
- https://www.viator.com/en-GB/tours/La-Paz/La-Paz-Whale-Shark-Experience/d22173-203550P1
- https://www.getyourguide.com/la-paz-mexico-l2930/
- https://www.getyourguide.com/la-ventana-l193099/ocean-safari-sea-lions-dolphins-mobulas-orcas-and-whales-t1339342/
- https://www.getyourguide.com/la-paz-mexico-l2930/la-paz-private-sea-of-cortez-fishing-charter-t1491017/
- https://www.getyourguide.com/la-paz-mexico-l2930/whale-shark-experience-t593461/
- https://costapalmas.com/discover/east-cape/
- https://costapalmas.com/blog/5-excursions-to-try-in-los-cabos-that-are-led-by-locals/
- https://www.cabo-adventures.com/en/tour/ocean-safari
- https://www.cabo-adventures.com/en/tours/whales-wildlife (contenido parcial)
- https://bajawildencounters.com
- https://bajawildencounters.com/la-ventana-whale-watching

No se pudo abrir: las URLs `/tours/...` de Viator sin `/en-GB/` (captcha), cualquier URL de Viator o GYG con WebFetch directo (403), y `https://www.getyourguide.com/la-ventana-l193099/` (vacía).
