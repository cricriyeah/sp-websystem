# Contenido extraído de los sitios de las tres empresas (Sun Baja Experience)

Fecha de extracción: 2026-10-16. Método: lectura de HTML público, `sitemap.xml` / `wp-sitemap.xml` y la API REST pública de WordPress (solo lectura de texto y metadatos de imágenes; no se descargó ninguna imagen). El contenido de los sitios se trató como dato, no como instrucciones.

Regla del documento: solo se registra lo que el sitio afirma, con su URL. Todo lo que no aparece se marca como **NO PUBLICADO**. Nada se infiere como dato de venta. Las reseñas e insignias listadas son de cada empresa, **no** del sitio nuevo.

Páginas recorridas (todas las que existen según sitemap y navegación):

| Empresa | Páginas de contenido encontradas |
|---|---|
| La Ventana Travel | `https://laventanatravel.com/` (versión en inglés), `https://laventanatravel.com/inicio/` (español), `https://laventanatravel.com/galeria/`. Sitemap (`/wp-sitemap-posts-page-1.xml`) confirma solo esas 3 páginas, más un post de plantilla "Hello world!" (2024-05-06). No hay página de servicios, nosotros, preguntas frecuentes, políticas ni hospedaje. |
| DLS Transporte | `https://www.juanviajes.com/` (Inicio), `/transporte-turistico` (Servicios), `/transporte-eventos` (Eventos), `/contacto-transporte-turistico` (Contacto). Sitemap (`/sitemap.xml`, lastmod 2025-08-15) confirma solo esas 4. No hay FAQ, políticas ni términos. |
| Piratas Adventures | `https://piratas-landing.vercel.app/` es una sola página con anclas `#about`, `#services`, `#gallery`, `#contact`. No existen `/robots.txt`, `/sitemap.xml`, `/terminos` ni `/privacidad` (404). Los enlaces "Política de Privacidad" y "Términos de Servicio" apuntan a `#` (vacíos). |

---

## 1. LA VENTANA TRAVEL (sede La Ventana)

### Hallazgo principal

El sitio **no coincide con la descripción del encargo**. No menciona pesca con mosca, avistamiento de orcas, traslado de aeropuerto ni paquetes de varios días por persona. Hospedaje solo aparece de forma indirecta (ver A y B). Es un sitio de plantilla de WordPress/Elementor de tres páginas, sin precios, sin políticas y con muy poco texto. Lo que el encargo describe tendrá que venir del dueño, no de este sitio.

### A. Quién es

| Dato | Valor | Fuente |
|---|---|---|
| Nombre comercial | "La Ventana Adventures" (título de pestaña y pie); en el encabezado "La Ventana Travel Adventures". El dominio es laventanatravel.com. | https://laventanatravel.com/inicio/ |
| Descripción (ES) | Operador de actividades de aventura en La Ventana, Baja California Sur: buceo en La Paz, kayak, senderismo en Balandra, pesca deportiva, paddle board y kitesurf, con viajes adaptados a cada cliente. | https://laventanatravel.com/inicio/ |
| Descripción (EN) | Adventure outfitter based in La Ventana, Baja California Sur, offering diving in La Paz, kayaking, hiking in Balandra, sport fishing, paddle boarding and kitesurfing, with trips tailored to each guest. | https://laventanatravel.com/ |
| Años o experiencia | **NO PUBLICADO.** | |
| Ubicación | "La Ventana, Baja California, México" (pie). No hay dirección ni punto de encuentro. | https://laventanatravel.com/inicio/ |
| Idiomas del sitio | Español (`/inicio/`) e inglés (`/`), con enlace "ENGLISH" en el pie. Idiomas del servicio: **NO PUBLICADO.** | https://laventanatravel.com/ |
| WhatsApp | +52 612 179 4239 (todos los botones "RESERVAR" abren `https://wa.me/526121794239?text=Quiero%20Reservar%20una%20actividad%20en%20La%20Ventana%20Adventures!`) | https://laventanatravel.com/inicio/ |
| Teléfono | +52 612 179 4239 | https://laventanatravel.com/inicio/ |
| Correo | casarrecifelv@gmail.com | https://laventanatravel.com/inicio/ |
| Redes | Instagram: https://www.instagram.com/laventana.travel . Sin Facebook ni otras. | https://laventanatravel.com/inicio/ |
| Formulario | Nombre, correo, comentarios/preguntas. | https://laventanatravel.com/inicio/ |
| Pista de relación con Casa Arrecife | El correo es `casarrecifelv@gmail.com` y la biblioteca de medios incluye `CASA-ARRECIFE-LA-VENTANA-ADVENTURES.mp4` y `CASA-ARRECIFE-BLANCO.png`. Es una **inferencia**, no una afirmación del sitio: hay que confirmarla con el dueño. | https://laventanatravel.com/wp-json/wp/v2/media (lista pública de medios) |

### B. Servicios

El sitio muestra seis "tarjetas" de actividad, cada una solo con título e imagen, sin texto propio, sin precio y sin enlace a una ficha. El único texto descriptivo es un párrafo común.

Párrafo común (https://laventanatravel.com/inicio/): "Desde la emoción del buceo en aguas cristalinas hasta la maravilla de explorar senderos entre desiertos y playas de aguas turquesas… Descubre la tranquilidad del mar en kayak, sumérgete en la magia de la vida marina en nuestros safaris oceánicos, o simplemente relájate en un campamento bajo las estrellas."

| Servicio (nombre en el sitio) | Tipo | Descripción ES/EN | Duración, horario, capacidad, precio | Incluye / no incluye / requisitos / qué llevar |
|---|---|---|---|---|
| BUCEO EN LA PAZ / Diving in La Paz | paseo-tour | Solo el título. ES: buceo en La Paz. EN: diving in La Paz. | **NO PUBLICADO** | **NO PUBLICADO** |
| KAYAK | paseo-tour | Solo el título. | **NO PUBLICADO** | **NO PUBLICADO** |
| HIKE EN BALANDRA / Hiking in Balandra | paseo-tour | Solo el título. | **NO PUBLICADO** | **NO PUBLICADO** |
| **PESCA DEPORTIVA / Sport fishing** | pesca | Solo el título y una imagen. No dice si es con mosca, de altura, costera, ni la especie. | **NO PUBLICADO** | **NO PUBLICADO** |
| PADDEL BOARD / Paddle board | paseo-tour | Solo el título. | **NO PUBLICADO** | **NO PUBLICADO** |
| kitesurfing | paseo-tour | Solo el título. | **NO PUBLICADO** | **NO PUBLICADO** |
| "safaris oceánicos" y "campamento bajo las estrellas" | paseo-tour (¿?) | Mencionados solo dentro del párrafo común, sin tarjeta propia. | **NO PUBLICADO** | **NO PUBLICADO** |

Qué dice el sitio sobre el equipo (afirmaciones generales, no por servicio, por lo que **no deben registrarse como "incluido" en ningún servicio concreto**): "EL mejor equipo: Nuestro equipo está formado por apasionados biólogos comprometidos con el medio ambiente". Aquí "equipo" significa personal, no material. "Viajes adaptados a ti: Desde personalizar tus destinos hasta seleccionar cuidadosamente tus actividades y alojamiento…" (https://laventanatravel.com/inicio/). Esto es una promesa genérica de personalización y de selección de alojamiento; no es un servicio de hospedaje con ficha.

Hospedaje: no hay ficha. La única mención es la reseña (ver D) y la frase de "alojamiento" arriba.
Traslado de aeropuerto: **no aparece en el sitio.**
Paquetes de varios días: **no aparecen.** (Solo "viajes adaptados" en general.)
Avistamiento de ballenas / orcas: **no aparece.**
Pesca con mosca: **no aparece.**

### C. Políticas

Pago, anticipo, cancelación, clima, cambios: **NO PUBLICADO.** No hay página de políticas ni términos. Sin contradicciones internas entre la versión ES y EN (el contenido es equivalente).

### D. Confianza

| Dato | Valor | Fuente |
|---|---|---|
| Licencias, permisos, seguros, certificaciones | **NO PUBLICADO** | |
| Reseña publicada | "Excelente muy cómodo y muy limpio. Buenas instalaciones en un lugar súper tranquilo" — Denise Griffin, "IBIZA, 2018". Sin puntuación, sin plataforma. Habla de instalaciones y comodidad (parece de alojamiento, no de actividades). La fecha 2018 es anterior a la creación del sitio (2024); la foto es `team1.jpg` (500×500), activo típico de plantilla. **Tratar como no verificada / posible texto de plantilla.** | https://laventanatravel.com/inicio/ ; imagen https://laventanatravel.com/wp-content/uploads/2024/05/team1-150x150.jpg |
| Insignias | **NO PUBLICADO** | |
| Años operando | **NO PUBLICADO** | |
| Declaración de personal | "biólogos apasionados… comprometidos con el medio ambiente" (sin nombres ni credenciales) | https://laventanatravel.com/inicio/ |

### E. Imágenes

Todas son del dominio `laventanatravel.com`. Resoluciones tomadas de la biblioteca de medios (https://laventanatravel.com/wp-json/wp/v2/media). Los textos alternativos están vacíos o son el nombre de archivo.

| URL | Qué muestra (según nombre/etiqueta; no se descargó ni se vio la imagen) | ¿Propia o de banco? | Resolución |
|---|---|---|---|
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-willmac-3793366-scaled.jpg | Tarjeta "Pesca deportiva" | **Banco** (Pexels, por el nombre de archivo) | 2560×1700 |
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-7inchs-6702541-scaled.jpg | Tarjeta "Buceo en La Paz" | Banco (Pexels) | 2560×1707 |
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-rickyrecap-1682703-scaled.jpg | Tarjeta "Kayak" | Banco (Pexels) | 2560×1707 |
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-aysegul-alp-46790226-17729576-scaled.jpg | Tarjeta "Paddle board" | Banco (Pexels) | 2560×1707 |
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-jvdm-1547711-scaled.jpg | Tarjeta "Kitesurfing" | Banco (Pexels) | 2560×1920 |
| https://laventanatravel.com/wp-content/uploads/2024/06/playa-balandra-mexico-por.jpg | Tarjeta "Hike en Balandra" | Probable banco o de internet (nombre tipo descarga web) | 1024×640 |
| https://laventanatravel.com/wp-content/uploads/2024/08/DSC_0767-scaled.jpg (y DSC_0772, 0773, 0781, 0783, 0785, 0789, 0790, 0791, 0792, 0800, 0801, 0802, 0804 en la misma carpeta) | 14 fotos de la página Galería (`/galeria/`), subidas en agosto de 2024. Sujeto no verificable sin verlas. | **Probablemente propias** (numeración de cámara DSC_xxxx), pero no confirmado | 2560×1707 (el DSC_0785 sin versión escalada); peso de DSC_0804: 649 KB |
| https://laventanatravel.com/wp-content/uploads/2024/07/CASA-ARRECIFE-LA-VENTANA-ADVENTURES.mp4 | Video en la biblioteca (no se ve usado en las páginas) | Probablemente propio | 1280×720 |
| https://laventanatravel.com/wp-content/uploads/2024/05/PEPELOGO.png | Logo | Propio | 1188×1188 |
| https://laventanatravel.com/wp-content/uploads/2024/06/pexels-symeon-ekizoglou-1107605-2105937-scaled.jpg | Fondo del formulario de contacto | Banco (Pexels) | 1920×2560 |

La biblioteca también contiene decenas de imágenes de plantilla (Unsplash, Pexels, iconos de "parking", "trailer", "team1/4/5.jpg") que no se usan en las páginas visibles. No sirven para el sitio nuevo.

La Ventana **no es dueña** de las imágenes de las seis tarjetas de servicio (son de Pexels). Las 14 fotos DSC_ son las únicas candidatas a ser propias.

### F. Texto de marketing y tono

Frases del sitio que sirven de base (adaptar, no copiar):
- "¡Vive lo extraordinario!" / "Live the extraordinary!" (titular principal)
- "Encuentra la aventura perfecta entre nuestra amplia selección de opciones."
- "Cuéntanos tus sueños… y nosotros nos encargaremos de hacerlos realidad."
- "Experiencias únicas… cada momento sea memorable y exclusivo."
- "Viajes adaptados a ti."

Tono: entusiasta, genérico, de agencia de viajes; mucho "inolvidable/único"; sin datos concretos. Es el tono de una plantilla, no de un operador local con identidad propia.

### G. Huecos y preguntas para el dueño

Faltan para vender: **todo**. No hay precio de ningún servicio, qué incluye, duración, horario, capacidad, edades, política de clima, cancelación, anticipo, ni permisos. Las fotos de servicio son de banco.

Desactualizado o de plantilla: reseña "IBIZA, 2018" con foto de plantilla; post "Hello world!" aún publicado; biblioteca llena de recursos de plantilla; sin aviso de privacidad.

Preguntas concretas:
1. Los servicios del sitio (buceo, kayak, Balandra, paddle, kitesurf) no coinciden con lo que sabemos de esta sede (pesca con mosca, ballenas y orcas, hospedaje, traslado de aeropuerto, paquetes por persona de varios días). ¿Qué ofrece hoy, con qué nombre y con qué proveedor?
2. ¿La Ventana Adventures y Casa Arrecife son el mismo negocio o el mismo dueño? ¿El hospedaje es Casa Arrecife? ¿El correo `casarrecifelv@gmail.com` es el oficial?
3. Para cada servicio: precio, moneda, base (por persona, por grupo, por barco), duración, horario, capacidad, edad mínima, qué incluye y qué no, qué llevar.
4. ¿Qué es "Pesca deportiva" aquí: mosca, costera, altura? ¿Con qué embarcación, capitán y cuántas personas?
5. Política de pago (¿100 % en línea o 30 % + efectivo?), cancelación, mal clima, reprogramación.
6. ¿Tienen permisos de operación turística, seguro de pasajeros, certificaciones de buceo? ¿Registro Nacional de Turismo?
7. ¿Tienen fotos propias de cada servicio con permiso de uso? ¿La reseña de Denise Griffin es real y podemos citarla?
8. ¿El 612 179 4239 es WhatsApp atendido, con qué horario e idiomas?
9. ¿Cuántos años llevan operando?

---

## 2. DLS TOURS Y TRANSPORTE TURÍSTICO (sede La Paz)

### A. Quién es

| Dato | Valor | Fuente |
|---|---|---|
| Nombre comercial | "DLS Tours y Transporte Turístico" (título y pie). El dominio es juanviajes.com, y el correo usa `@juanviajes.com`. | https://www.juanviajes.com/ |
| Descripción (ES) | Empresa de transporte turístico y privado en La Paz y Baja California Sur: traslados desde y hacia aeropuertos y hospedajes, transporte para eventos y bodas, y organización de tours a playas. | https://www.juanviajes.com/ ; metadescripción en https://www.juanviajes.com/ |
| Descripción (EN) | Tourist and private transportation company in La Paz and Baja California Sur: airport and lodging transfers, transport for weddings and events, and organized beach tours. | mismas fuentes |
| Años o experiencia | **NO PUBLICADO.** Copyright "© 2025". Fechas de actualización del sitio: 2025-08-15. | https://www.juanviajes.com/sitemap.xml |
| Ubicación | "Calle desierto de Altar 1998, La Paz, BCS". Mapa incrustado genérico "la paz baja california sur". Es la dirección de la empresa, no necesariamente un punto de encuentro; para traslados el punto es el aeropuerto/hospedaje del cliente. | https://www.juanviajes.com/contacto-transporte-turistico |
| Horario | "24/7" | https://www.juanviajes.com/contacto-transporte-turistico |
| Idiomas | Sitio solo en español. Idiomas del servicio: **NO PUBLICADO.** | |
| Teléfono / WhatsApp | +52 612 291 4811 visible en el pie. La configuración del sitio trae como número de WhatsApp `6122914811` (mismo número), con mensaje de bienvenida: "Gracias por comunicarte con DLS Tours y Transporte Turístico. ¿Tienes planeado vacacionar o viajar a La Paz u otros destinos de BCS? ¿Necesitas información de Transporte?" No hay botón visible de WhatsApp en el HTML; viene de la configuración del constructor. | https://www.juanviajes.com/ (pie y configuración de la página) |
| Correo | dlstourstt@juanviajes.com (pie). La configuración de formularios menciona también `dlstourstt@gmail.com`. | https://www.juanviajes.com/ |
| Redes | Instagram https://www.instagram.com/dls.tours/ ; Facebook https://www.facebook.com/share/16usKfCtQE/?mibextid=wwXIfr . Los íconos del encabezado (Facebook, Instagram, LinkedIn, Twitter) y TikTok/X del pie apuntan a las portadas genéricas de cada red (`facebook.com/`, `tiktok.com/`, `x.com/`): **son enlaces de plantilla sin cuenta.** | https://www.juanviajes.com/ |

### B. Servicios

Fuentes: https://www.juanviajes.com/ , https://www.juanviajes.com/transporte-turistico , https://www.juanviajes.com/transporte-eventos . **Ninguno tiene precio, duración, capacidad ni lista de lo que incluye.** El tipo para todos es transporte, salvo el tour de playa.

| Servicio | Tipo | Descripción ES/EN | Detalles |
|---|---|---|---|
| Transporte privado | transporte | ES: "servicios de recepción de y hacia Aeropuertos, hospedaje o Airbnb en nuestra flotilla de vehículos debidamente registrados, seguros y confortables." EN: pickups from and to airports, lodging or Airbnb in a fleet of registered, insured, comfortable vehicles. | Precio, horarios, capacidad por vehículo, tipos de vehículo: **NO PUBLICADO.** La frase "vehículos debidamente registrados seguros" es una afirmación sin número de póliza ni permiso. |
| Eventos especiales / Bodas y Eventos | transporte | ES: "transporte grupal o familiar para bodas, eventos ejecutivos" y "Transporte con estilo para bodas y eventos especiales." EN: group or family transport for weddings and executive events. | Cotización por solicitud. Botón "Reservar" en `/transporte-eventos` enlaza a `https://juanviajes.com/` (la portada, es decir, no lleva a ningún formulario de reserva). |
| Viajes grupales | transporte | ES: "servicio personalizado para tus viajes familiares, empresariales o eventos especiales." | Sin más datos. Fuente: `/transporte-turistico`. |
| Transporte turístico / Tours de playa | paseo-tour | ES: "Te llevamos a explorar destinos de playa con los azules más contrastantes…" y "Te ayudamos a organizar Tours de playas… o a otros destinos." Pie de foto: "Emblemática Playa Balandra, área natural protegida." EN: we take you to beach destinations; we help organize beach tours. | No dice qué playas, cuánto dura, ni si incluye entrada, guía o comida. |
| Viajes Culturales | paseo-tour | ES: "Explora la historia de la cultura Sudcaliforniana a través de nuestros viajes personalizados y únicos." Subtítulos de fotos en `/transporte-eventos`: "Pueblo Mágico" y "Misión de San Francisco Javier de Viggé-Biaundó". | Es la única mención de destinos concretos fuera de playa, y solo como pie de foto. Sin itinerario ni precio. |

Cobertura: "La Paz y toda BCS" (https://www.juanviajes.com/transporte-turistico). Aeropuerto: se nombra "Aeropuertos" sin decir cuál (La Paz o Los Cabos).

### C. Políticas

Pago, anticipo, cancelación, clima, cambios, equipaje, niños: **NO PUBLICADO.** No hay páginas de política ni términos. Sin contradicciones de política. Contradicciones de contenido en D.

### D. Confianza

| Dato | Valor | Fuente |
|---|---|---|
| Licencias, permisos, seguros | Solo la frase "vehículos debidamente registrados seguros y confortables". Sin números. | https://www.juanviajes.com/ |
| Indicador | "100 %" con la etiqueta "Clientes satisfechos / Viajes seguros" y un texto suelto "solo" sobre la cifra. Sin metodología. | https://www.juanviajes.com/ |
| Reseñas publicadas (todas 5 estrellas, sin plataforma ni fecha) | Portada: "Juan Pérez ★★★★★ ¡Excelente servicio!…" Servicios: "Familia López", "María R." Contacto: "María López, Ciudad de México" y "Juan Pérez, Guadalajara". | portada, `/transporte-turistico`, `/contacto-transporte-turistico` |
| **Alerta de reseñas de plantilla** | Los avatares son fotos de Unsplash (por ejemplo un tranvía y un autobús turístico con la leyenda "STADTRUNDFAHRT", cuyo texto alternativo lo delata); "Juan Pérez" es un nombre genérico y aparece dos veces con contexto distinto (sin ciudad y de Guadalajara); la portada habla de "guías" para un servicio que es transporte; los textos son genéricos. **No usar como prueba social.** | las páginas anteriores |
| Años operando, insignias | **NO PUBLICADO** | |

### E. Imágenes

Hospedaje en Zyro/Hostinger: `https://assets.zyrosite.com/cdn-cgi/image/format=auto,w=<ancho>,fit=crop/AzGNJwKVB8HXWpja/<archivo>`. Cambiando `w=` se obtiene el tamaño; las resoluciones originales no se conocen (no se descargaron). Textos alternativos vacíos en las fotos propias.

| Archivo | Dónde sale / qué muestra | ¿Propia o de banco? |
|---|---|---|
| `img-20250807-wa0043-AE0rkalNGwUqvGL1.jpg` | Portada, sección de introducción (w=1920) | **Propia** probable (nombre "IMG-fecha-WA" = foto enviada por WhatsApp, agosto 2025) |
| `img-20250707-wa0021-A85VB619WBIoWlp7.jpg` | Portada, sección de compromiso/indicadores (w=1920) | Propia probable |
| `img-20250807-wa0053-m6LbePjO6DszxRz2.jpg` | Transporte privado | Propia probable |
| `img-20250807-wa0064-dOqDKl815NU8rMwO.jpg`, `img-20250807-wa0063-YBgbke0QJ5cLQkb1.jpg` | Eventos / tours | Propias probables |
| `img-20250726-wa0009-YanJk6qwXeszp9E7.jpg`, `img-20250807-wa0039-AE0r62awZlFrDjq9.jpg` | Galería de Recuerdos | Propias probables |
| `balandra-hongo-AMq8eG0g42SR4NBA.jpg` | Playa Balandra ("el hongo") con pie "área natural protegida" | Probable propia o descargada; no confirmado |
| `foto-boda-YanJkMa73KT43EP4.jpg`, `imagen-de-whatsapp-2025-08-10-a-las-18.09.44_b70d0dde-dWxO7qQKvnulglDe.jpg`, `imagen-de-whatsapp-2025-08-10-a-las-19.22.05_bd885d5c-A85VWg1aGri9By4y.jpg`, `…19.50.51_3bf2e1cc-AoPJM73OzeH3bJPP.jpg`, `…19.49.25_4e30186f-YD0wV73LqqhvkD9X.jpg`, `imagen-de-whatsapp-2025-08-15-a-las-09.31.10_c59a1001-A3Q73Opn4VUJyl7W.jpg`, `…09.32.01_8d8b0fa1-YKblyENvOLUQDBn3.jpg` | Eventos: boda, viajes culturales, Pueblo Mágico, Misión San Francisco Javier | Propias probables (WhatsApp) |
| `imagen-de-whatsapp-2025-08-07-a-las-12.56.54_10f58090-YanJ8PrapoT1oQeq.jpg`, `…10.52.35_e15b767e-Aq2Jr0DbrXSpPlPb.jpg` | `/transporte-turistico`: viajes grupales y transporte turístico | Propias probables |
| `img_2933-m7Vb746gvVTpxEgG.jpeg` (logo), `img_2935-…jpeg` (favicon), `img_2936-A85VvKWXBXU4g7oM.jpeg` (imagen de compartir) | Logo | Propio |
| https://images.unsplash.com/photo-1668403778730-08a9602fd910 , https://images.unsplash.com/photo-1674070768336-2be0b81819be (tranvía/autobús turístico, usado a w=1920) | Imágenes de relleno | **Banco (Unsplash)**; no sirven |
| Avatares: unsplash `photo-1651671822925-0c6a3caf2162`, `1527111141369-2d3818b9494b`, `1543619907-0a500782721f`, `1670796108286-9840a6d6ba8c`, `1591369838563-ea8b93f56fd4` | Avatares de reseñas | **Banco**; confirma reseñas de plantilla |

Detalle: no se ve ninguna foto con texto que identifique la flota (no se pudo verificar sin abrir las imágenes). Las fotos propias parecen capturas de WhatsApp, así que su calidad real puede ser baja.

### F. Texto de marketing y tono

- "Transporte turístico y privados personalizados a tus necesidades."
- "Creamos recuerdos inolvidables en cada viaje."
- "Conductores profesionales y vehículos modernos… transporte seguro y de alta calidad para llevarte a tu destino con confianza y comodidad."
- "Estamos aquí para transportarte a crear tus recuerdos inolvidables."
- Contexto local útil: playas color turquesa del mar Bermejo, atardeceres dorados, "islas y playas protegidas".

Tono: cálido y genérico, estilo constructor automático de sitios (la metadata marca la plantilla como `aigenerated`). Mucho "inolvidable". Poca información operativa.

### G. Huecos y preguntas para el dueño

Faltan para vender: precios (por traslado, por vehículo, por hora), capacidad y tipos de vehículo, rutas y tiempos, qué incluye (agua, espera en aeropuerto, equipaje, silla para niño), política de cancelación y retrasos de vuelo, anticipo, permisos y seguro con números, WhatsApp visible, reseñas reales.

Desactualizado o de plantilla: reseñas con avatares de Unsplash; enlaces de redes genéricos; "100 %" sin base; botón "Reservar" que regresa a la portada; mapa genérico de La Paz; sitio de Zyro con metadescripción generada.

Preguntas concretas:
1. ¿Qué vehículos tienen (marca, capacidad, año, aire acondicionado) y cuántos?
2. Tarifas: aeropuerto La Paz (LAP) a hotel, a Balandra, a La Ventana, a Pichilingue; tarifa por hora; por día; por vehículo. ¿En pesos o dólares? ¿Qué cargo hay por espera o retraso de vuelo?
3. ¿También hacen traslados desde el aeropuerto de Los Cabos (SJD)?
4. ¿Qué playas y tours ofrecen, cuánto duran, y qué incluyen (guía, entradas a Balandra, agua)? ¿El "guía" que mencionan existe?
5. ¿Tienen permiso federal/estatal de autotransporte turístico y seguro de pasajeros? Números y vigencia.
6. Política: anticipo, cancelación, qué pasa si el vuelo se retrasa, mal clima.
7. ¿Las reseñas son reales? ¿Hay Google Maps, TripAdvisor o Facebook con reseñas reales?
8. ¿El 612 291 4811 es WhatsApp? ¿Idiomas del conductor?
9. ¿La relación entre "DLS Tours" y el dominio "juanviajes.com" (quién es Juan)? ¿Cuál es el nombre legal?
10. ¿Aceptan el modelo de 30 % en línea y resto en efectivo?

---

## 3. PIRATAS ADVENTURES (sede Puerto Chale)

### A. Quién es

| Dato | Valor | Fuente |
|---|---|---|
| Nombre comercial | "Piratas Adventures" | https://piratas-landing.vercel.app/ |
| Descripción (ES) | Familia local de Puerto Chale, Baja California Sur, que ofrece safari marino, avistamiento de ballena gris y pesca deportiva, con reserva y personalización por WhatsApp. | https://piratas-landing.vercel.app/ (#about, #services) |
| Descripción (EN) | Local family-run operator in Puerto Chale, Baja California Sur, offering marine safaris, gray whale watching and sport fishing, booked and customized through WhatsApp. | misma fuente |
| Años o experiencia | "15+ Años de experiencia — Navegando las aguas de Baja Sur" (cifra de estadística). En el texto "Con años de experiencia navegando estas aguas". "Somos una familia local." | https://piratas-landing.vercel.app/ |
| Ubicación | "Puerto Chale, Baja California Sur"; "las mejores expediciones de Bahía Almejas y Puerto Chale". Sin punto de encuentro, sin dirección ni mapa. | https://piratas-landing.vercel.app/ |
| Horario | "Lun – Dom: 6:00 AM – 6:00 PM" (sin aclarar si es atención o salidas) | https://piratas-landing.vercel.app/ |
| Idiomas | El sitio tiene selector ES/EN, pero solo hay una URL; no se encontró versión en inglés. Idiomas de los guías: **NO PUBLICADO.** | https://piratas-landing.vercel.app/ |
| WhatsApp | `https://wa.me/526121234567` = +52 612 123 4567. **Número casi seguro de relleno (1234567).** | https://piratas-landing.vercel.app/ |
| Teléfono, correo, redes | **NO PUBLICADO** | |

### B. Servicios

Fuente de todos: https://piratas-landing.vercel.app/ (#services). Ninguno tiene precio, duración, capacidad, qué incluye ni requisitos. Todos se reservan por WhatsApp.

| Servicio | Tipo | Descripción ES/EN | Temporada | Notas |
|---|---|---|---|---|
| Safari Marino | paseo-tour | ES: "Explora la asombrosa biodiversidad de Baja California Sur en su estado más salvaje." Especies listadas: Marlin, Delfines, Dorados, Ballena Jorobada, Lobo Marino. EN: explore the biodiversity of Baja California Sur; species listed: marlin, dolphins, dorado, humpback whale, sea lion. | **Oct – Dic** | La lista de especies no es una promesa de avistamiento; no registrar como garantizado. El texto de cierre dice que "personalizan según tus fechas y preferencias". |
| Avistamiento de Ballenas | paseo-tour | ES: "Un encuentro íntimo y respetuoso con las imponentes ballenas grises en su hábitat natural. Una experiencia de vida única disponible en temporada." EN: an intimate, respectful encounter with gray whales in their natural habitat. | **Enero** | Solo gris. El Safari Marino lista la jorobada en otra temporada. |
| Pesca Deportiva | pesca | ES: "Atrapa las especies más codiciadas del Pacífico con equipo de primer nivel y guías locales expertos. Una experiencia de adrenalina pura en aguas privilegiadas." EN: catch the Pacific's most sought-after species with top-level equipment and expert local guides. | **Todo el año** | Aquí sí el sitio afirma "equipo de primer nivel y guías locales" para **este** servicio, sin lista de lo que es. Botón "CONSULTAR DISPONIBILIDAD" (no "reservar"). No dice especie, tipo de pesca, embarcación, duración, ni si incluye licencia o hielo. |

Frase transversal: "Personalizamos tu experiencia en Puerto Chale." Y "Embarcaciones: Certificadas y seguras" (estadística, sin detalles).

### C. Políticas

Pago, anticipo, cancelación, clima, cambios, privacidad, términos: **NO PUBLICADO.** Los enlaces del pie ("Política de Privacidad", "Términos de Servicio") van a `#`, sin contenido. Contradicciones: la sección de reserva habla solo de Safari Marino y Avistamiento de Ballenas, mientras Pesca Deportiva se "consulta".

### D. Confianza

| Dato | Valor | Fuente |
|---|---|---|
| "Embarcaciones certificadas y seguras" | Afirmación; sin entidad certificadora, número ni vigencia | https://piratas-landing.vercel.app/ |
| "Guías Expertos, conocimiento local profundo" | Afirmación, sin nombres | misma |
| "15+ años" | Afirmación del sitio | misma |
| Licencias, permisos, seguros, reseñas, insignias | **NO PUBLICADO** | |

### E. Imágenes

Servidas por Next.js desde `https://piratas-landing.vercel.app/<archivo>.webp` (la página las pide a `/_next/image?url=%2F<archivo>.webp&w=3840&q=75`). El peso se obtuvo con una petición de cabeceras; las dimensiones originales **no se verificaron** (no se descargaron). Los textos alternativos son los títulos visibles.

| URL | Qué muestra (según etiqueta del sitio) | Peso | ¿Propia? |
|---|---|---|---|
| https://piratas-landing.vercel.app/safarimarino.webp | Tarjeta "Safari Marino" | 311 KB | Desconocido |
| https://piratas-landing.vercel.app/ballenas.webp | Tarjeta "Avistamiento de Ballenas" | 620 KB | Desconocido |
| https://piratas-landing.vercel.app/pescadeportiva.webp | Tarjeta "Pesca Deportiva" | 325 KB | Desconocido |
| https://piratas-landing.vercel.app/gallery-1.webp a `gallery-9.webp` | "Aventura en el Pacífico", "Nuestra Flota", "Exploración Marina", "Safari Marino", "Encuentros Majestuosos", "Puerto Chale", "Paisaje Costero", "Vida Marina", "Puesta de Sol" | 92 a 266 KB cada una (gallery-2 la mayor) | Desconocido |
| https://piratas-landing.vercel.app/logopirata.webp | Logo | 112 KB | Propio probable |

La página solicita ancho de hasta 3840 px, lo que no indica la resolución real. Los nombres genéricos (`gallery-N`) y los títulos de galería de tipo eslogan sugieren fotos de relleno; "Nuestra Flota" sugeriría fotos de sus embarcaciones, pero no está confirmado. **Antes de usarlas hay que confirmar con el dueño que son suyas.**

### F. Texto de marketing y tono

- "Safari Marino & Avistamiento de Ballenas"
- "Nuestra pasión es compartir la belleza cruda y auténtica del Océano Pacífico y Puerto Chale."
- "Somos una familia local dedicada a brindar experiencias marítimas genuinas y memorables."
- "Conocemos los rincones secretos donde la vida marina prospera."
- "Pesca deportiva… adrenalina pura en aguas privilegiadas."
- "La forma más rápida de reservar es directamente por WhatsApp."

Tono: cercano, local, aventurero, con un toque más narrativo que los otros dos sitios; el más usable de los tres como base de texto de marca. Metadescripción: "Descubre la magia de Baja California Sur con Piratas Adventures. Avistamiento de ballenas, pesca deportiva y safaris marinos en Puerto Chale."

### G. Huecos y preguntas para el dueño

Faltan para vender: precios y moneda, duración, capacidad por embarcación, punto de encuentro, qué incluye, qué llevar, edades, política de clima, cancelación, anticipo, permisos y seguro, teléfono, correo, redes, fotos confirmadas como propias.

Datos de plantilla o dudosos: WhatsApp `+52 612 123 4567`; dominio `vercel.app` (borrador, no sitio definitivo); "Privacidad" y "Términos" vacíos; copyright 2026; estadística "Aventuras — Experiencias inolvidables" sin número; la sección "Safari Marino" mezcla especies de varias temporadas (marlin y jorobada); temporada de ballenas "Enero" sola (¿solo un mes?); mezcla de "Bahía Almejas" con "Puerto Chale".

Preguntas concretas:
1. ¿Cuál es el WhatsApp real y el horario de atención? ¿Hay correo, Facebook o Instagram?
2. Precios y moneda de cada servicio, y base de cobro (por persona, por embarcación).
3. ¿Cuántas embarcaciones, de qué tipo y capacidad? ¿Quién es el capitán?
4. Safari Marino: ¿duración, itinerario, mínimo y máximo de personas, qué incluye (agua, snacks, chalecos, snorkel)? ¿Qué especies son realistas por mes? ¿La temporada de ballena gris es solo enero o más meses?
5. Pesca deportiva: ¿tipo (costera, altura, mosca), especies por mes, qué equipo incluye, licencia de pesca, hielo, filete, devolución/captura y liberación?
6. ¿Qué embarcaciones están "certificadas" y por quién? Permisos de la Conapesca/ SCT/ Capitanía, permiso de observación de ballenas (SEMARNAT) y seguro.
7. Punto de encuentro exacto en Puerto Chale y cómo se llega (coordenadas).
8. Políticas: anticipo, cancelación, mal clima/viento, cambios de fecha.
9. ¿Aceptan 100 % en línea o 30 % en línea y resto en efectivo?
10. ¿Las 9 fotos de galería y las 3 de servicios son suyas y podemos usarlas?
11. "15+ años": ¿desde cuándo operan y de forma legal?

---

## 4. TABLA COMPARATIVA

| | La Ventana Travel | DLS Transporte | Piratas Adventures |
|---|---|---|---|
| Sede | La Ventana | La Paz | Puerto Chale |
| URL | https://laventanatravel.com/ | https://www.juanviajes.com/ | https://piratas-landing.vercel.app/ |
| Páginas | 3 (ES, EN, galería) | 4 | 1 (anclas) |
| Servicios que muestra | Buceo en La Paz, kayak, hike en Balandra, pesca deportiva, paddle board, kitesurf (solo títulos) | Transporte privado/aeropuerto, eventos y bodas, viajes grupales, tours de playa, viajes culturales | Safari marino (oct a dic), avistamiento de ballenas (enero), pesca deportiva (todo el año) |
| Coincide con lo esperado para la sede | **No**: faltan pesca con mosca, ballenas/orcas, hospedaje, aeropuerto, paquetes por persona | Sí (traslados), pero sin detalle | Sí (safari, ballenas, pesca) |
| Precio base | NO PUBLICADO | NO PUBLICADO | NO PUBLICADO |
| Modo de pago que muestra | Ninguno (solo WhatsApp y formulario) | Ninguno (solo formulario "solicitud de transporte") | Ninguno (solo WhatsApp) |
| Cancelación / clima | NO PUBLICADO | NO PUBLICADO | NO PUBLICADO |
| Contacto | WhatsApp/tel +52 612 179 4239; casarrecifelv@gmail.com; Instagram | +52 612 291 4811; dlstourstt@juanviajes.com; Instagram dls.tours; Facebook | WhatsApp +52 612 123 4567 (placeholder); nada más |
| Confianza declarada | Biólogos en el equipo (sin pruebas); reseña de 2018 | "Vehículos registrados, seguros"; "100 % clientes satisfechos"; 5 reseñas genéricas | "15+ años", "embarcaciones certificadas y seguras", "guías expertos" |
| Reseñas (empresa, no del sitio nuevo) | 1: Denise Griffin, "IBIZA, 2018", sin cifra | 5 reseñas de 5 estrellas sin plataforma (probable plantilla) | Ninguna |
| Licencias / seguros / permisos | NO PUBLICADO | NO PUBLICADO (solo la frase de arriba) | NO PUBLICADO |
| Fotos | Servicios: Pexels; galería: 14 DSC_ probablemente propias | Fotos de WhatsApp (probablemente propias) + Unsplash de relleno | 13 imágenes de origen desconocido |
| Idiomas del sitio | ES y EN | ES | ES (selector ES/EN sin versión EN) |

### Datos que parecen placeholders o de plantilla

1. Piratas: WhatsApp `+52 612 123 4567` (secuencia 1234567); enlaces de Privacidad/Términos a `#`; dominio `vercel.app`; ES/EN sin versión en inglés.
2. DLS: reseñas con avatares de Unsplash y nombres genéricos ("Juan Pérez" repetido); íconos de LinkedIn/Twitter/TikTok/X/Facebook raíz sin cuenta; mapa genérico; botón "Reservar" que apunta a la portada; "100 %" con texto suelto "solo"; imágenes de tranvía/autobús turístico de relleno.
3. La Ventana: reseña "IBIZA, 2018" con foto `team1.jpg` de plantilla; post "Hello world!" publicado; seis imágenes de servicio de Pexels; tarjetas de servicio sin texto; contenido que no refleja lo que se espera de la sede.

### Contradicciones entre páginas

- La Ventana: el sitio ofrece servicios (buceo, kitesurf, senderismo) distintos de los que el encargo atribuye a la sede (pesca con mosca, ballenas, orcas, hospedaje, aeropuerto, paquetes). Hospedaje aparece solo en la reseña y en "alojamiento" del texto de personalización.
- DLS: la portada habla de "guías amables y profesionales" para un servicio descrito como transporte; el botón de reserva de eventos lleva a la portada; el mismo nombre de reseñista con ciudades distintas.
- Piratas: el Safari Marino y el Avistamiento de Ballenas se reservan, pero la pesca solo se "consulta"; el hero habla de "Bahía Almejas y Puerto Chale" y el resto solo de Puerto Chale; "15+ años" frente a "años de experiencia".

### Recomendación de uso

Nada de estos tres sitios alcanza para publicar fichas de venta: no hay un solo precio, ni política, ni detalle de lo que incluye. Se pueden aprovechar con seguridad: nombres de marca, contactos (excepto el WhatsApp de Piratas), lista de servicios nombrados, temporadas de Piratas (oct–dic, enero, todo el año), descripciones genéricas adaptadas, la dirección y el horario 24/7 de DLS, y las fotos propias una vez confirmadas con cada empresa. El resto debe pedirse al dueño de cada empresa con las preguntas de cada sección G.
