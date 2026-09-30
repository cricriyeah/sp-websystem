# Diseño — Hub de agencia y páginas de sede

- **Fecha:** 2026-09-15
- **Rama/worktree:** `feat/transporte-multi-empresa`, worktree `transporte-multi-empresa`
  (mismo commit que apunta `sistema-actual` hoy — se trabaja en ese worktree, no
  en uno nuevo).
- **Estado:** PROPUESTO — pendiente de revisión del dueño y del spec-critic
- **Alcance:** solo frontend (Next.js), con una extracción pequeña de dos
  funciones puras (§7). Cero cambios de backend/modelos/API.

Documento de plan que sale de este diseño (a escribir después de aprobar este spec):

- `docs/superpowers/plans/2026-09-15-hub-multisede.md`

---

## 1. Contexto y objetivo

Hoy `/` es la página de una sola empresa (Sal y Sol Sportfishing, La Paz): hero,
about, temporada, incluye, licencia, galería, reseñas, FAQ, con un booking bar
pegado que reserva pesca directo. `/catalogo` es donde en realidad vive el
concepto de "varias sedes": un selector de sede (guardado en localStorage/cookie,
`src/lib/sede.ts`) más un grid de paquetes y servicios de la sede elegida.

El negocio ya no es una sola empresa — es una agencia (**Sal y Sol Baja
Experiences**) que agrupa sedes (`tenancy.Sede`), cada una operada por una o más
empresas (`tenancy.Empresa`) en alianza. El sitio nunca reflejó ese cambio: sigue
vendiéndose como si fuera un solo negocio, y el descubrimiento de sede vive
escondido detrás del link "Experiencias" del nav.

**Objetivo de este rediseño:** que la portada sea el punto de entrada de la
agencia (no de una empresa), que cada sede tenga su propia página completa con
storytelling + catálogo + reserva, y que reservar siga siendo lo más directo
posible para quien ya sabe qué quiere, sin esconder el detalle para quien
quiere verlo antes de decidir.

**Correcciones tras dos rondas de revisión adversarial** (se dejan aquí para que
quien implemente entienda por qué el diseño es como es, no solo qué hacer):

1. "Empresa fundadora/prioritaria de la sede" **no** es `Empresa.exclusiva`. Ese
   campo significa *operador único de la sede* (`help_text`: "Si esta Empresa
   opera en exclusiva su Sede"), lo edita el dueño desde el admin de Django hoy
   mismo, y se vuelve `False` el día que una segunda empresa entra a una sede —
   exactamente el escenario que esta página está diseñada para mostrar (§6.7).
   La empresa fundadora es **contenido editorial**, hardcodeado en el
   diccionario (§4), sin relación con `exclusiva`.
2. El booking bar de hoy (`BookingBar`/`ProveedorReserva`/`getCupoRango`/
   `TimeField`) **no es genérico** — está cableado a pesca en La Paz vía Sal y
   Sol (empresa del `.env`, horas fijas 5-7am, sin endpoint de horarios/
   capacidad por `Servicio`). No se generaliza en este spec (sería trabajo de
   API); se usa tal cual, solo donde ya es correcto (§7).
3. Todo el contenido "migrado tal cual de `/`, por sede" (hero, galería,
   reseñas, FAQ, dirección) **no puede migrarse tal cual** porque hoy solo
   existe una copia global de cada uno en el diccionario. El modelo de
   contenido (§4) tiene que incluirlos explícitamente por sede, o una sede pendiente
   renderiza el video de pesca, las reseñas de Sal y Sol y la dirección de la
   marina de La Paz como si fueran suyas.

## 2. Alcance

**Sí incluye:**
- Nueva portada `/[lang]` como hub de agencia (mapa ilustrado + secciones de marca).
- Nueva ruta `/[lang]/sede/[slug]` — plantilla de página de sede, reutilizable,
  con `notFound()` para cualquier slug que no tenga entrada en el diccionario
  (§4), sin importar lo que diga la API.
- Un paso nuevo al inicio de la experiencia de reserva en la página de sede
  (elegir qué reservar) — con inline real **solo** para el único flujo que ya
  lo soporta hoy (pesca/La Paz/Sal y Sol); todo lo demás navega directo a su
  checkout existente (§7).
- Extracción de la lógica de armado de URL de reserva que hoy vive inline
  dentro de `PaqueteCard` y `ServiciosSueltosSection` a un helper compartido
  (`src/lib/booking-href.ts`), sin cambiar el resultado ni el comportamiento
  visible de esos componentes — se reutiliza desde los chips nuevos (§7).
- Restructurar el contenido hoy global del diccionario (hero, about, temporada,
  incluye, licencia, galería, reseñas, FAQ, dirección/horario del negocio,
  metadata) para que viva **por sede** (§4), migrando el contenido actual de
  Sal y Sol/La Paz a la entrada `la-paz` tal cual, sin reescribirlo.
- Migración de la lógica de `/catalogo` (selector + grids de paquetes/servicios)
  hacia el hub (selector) y la página de sede (grids ya filtrados) — usando
  `PaqueteCard`/`ServiciosSueltosSection` sin tocar su UI ni su botón de reserva.
- `/catalogo` pasa a ser un stub de redirect (§9).
- Contenido nuevo (empresa fundadora, historia de la alianza, "otras empresas de
  la sede", experiencias destacadas, copy del hub) hardcodeado en los
  diccionarios del frontend — **no** hay campos nuevos en `Sede`/`Empresa`.
- Ajustes de nav (`SiteHeader`, todos sus puntos de montaje), sitemap y datos
  estructurados para que sigan siendo correctos con la URL nueva (§9).

**No incluye (fuera de alcance, explícitamente diferido):**
- Campos de contenido en el backend (`descripcion`, `imagen`, `coordenadas`,
  `sitio_web`, dirección/horario en `Sede`/`Empresa`) — cuando el catálogo de
  contenido crezca lo suficiente para que editar código por cada cambio de
  texto/foto sea un cuello de botella real, se revisita.
- Mapa geográfico real (Mapbox/Leaflet/coordenadas de verdad) — se usa un mapa
  ilustrado a la medida.
- Contenido narrativo, fotos, reseñas y FAQ reales de La Ventana y Puerto Chale — se
  pone placeholder honesto (secciones que dependen de eso simplemente no se
  renderizan, §6), no se inventa historia ni se copian las de La Paz.
- Rediseño visual o de comportamiento de `PaqueteCard`/`ServiciosSueltosSection`
  más allá de la extracción de §2 — su JSX, su UI y a dónde navegan al hacer
  click no cambian.
- **Disponibilidad/horarios/capacidad por servicio en el booking bar.** Hoy
  `getCupoRango` no recibe empresa (siempre pega a la empresa del `.env`),
  `TimeField` asume la ventana de pesca (5-7am), y no existe endpoint de
  horarios/capacidad por `Servicio`. Construir eso es trabajo de API — ver §7
  para cómo se evita necesitarlo.
- Atajo de selección rápida de sede en el hero del hub (dropdown/links directos)
  — se revisita cuando haya 4-5+ sedes; con 2 sedes, el scroll al mapa basta.

## 3. Rutas — antes y después

| Ruta | Hoy | Después |
|---|---|---|
| `/[lang]` | Landing de Sal y Sol (empresa) | Hub de agencia (Sal y Sol Baja Experiences) |
| `/[lang]/catalogo` | Selector de sede + grids | **Stub de redirect** (§9), ya no tiene contenido propio. |
| `/[lang]/sede/[slug]` | No existe | **Nueva.** Página completa de la sede (storytelling + catálogo + booking bar). `notFound()` si el slug no está en el diccionario (§2). |
| `/[lang]/traslados` | Página propia de cotización/reserva de transporte, hoy solo enlazada desde el banner de `/catalogo` | Sigue existiendo tal cual (misma lógica, mismo componente `TrasladoView`); el enlace de entrada se mueve a la página de sede (§6.4) y sus dos links de "volver" (`traslados/page.tsx` estado no-disponible, `traslado-view.tsx` línea ~500) dejan de apuntar a `/catalogo` (§9). |
| `/[lang]/reservar`, `/[lang]/reservar-paquete` | Checkout | **Sin cambios de lógica ni de contrato de query params.** Sí cambian, de forma mecánica: los props que reciben de `SiteHeader` (§9) y, en `paquete-checkout.tsx`, un link de "volver" que hoy apunta a `/catalogo` (§9). |

`SedeSelector` deja de navegar a `/catalogo?sede=`; navega directo a
`/[lang]/sede/[slug]`. `src/lib/sede.ts` se conserva (localStorage/cookie) para
que el nav recuerde la última sede vista en el **hub** y en páginas sin sede
propia (checkout, deslinde — ver §9), donde no hay slug en la URL; dentro de
una página de sede, el slug de la URL manda siempre — el selector recibe
`sedeSeleccionadaSlug` explícito desde el parámetro de ruta, no desde
localStorage.

## 4. Modelo de contenido (hardcodeado, sin backend nuevo)

Esta sección creció respecto a la primera versión del spec: no alcanza con
"historia de la alianza + otras empresas" — **todo** el contenido que hoy es
global (hero, about, temporada, incluye, licencia, galería, reseñas, FAQ,
negocio/dirección, metadata) tiene que volverse por-sede, porque cada sede
necesita el suyo propio y hoy solo existe una copia.

**Regla de reconciliación (dos fuentes de sedes):** el diccionario es la
**única fuente de verdad de qué páginas de sede existen**. `getSedes()` (la
API) solo se usa para saber si una sede sigue `activo=True` — el hub renderiza
la intersección (sede en el diccionario Y activa en la API); si `getSedes()`
falla o no responde, el hub **falla abierto** y muestra todas las sedes del
diccionario sin filtrar (nunca deja el hub sin ningún destino por un error de
red — hoy `/` no depende de ninguna API para poder navegar, y este rediseño no
le agrega esa fragilidad). `/[lang]/sede/[slug]` nunca consulta `getSedes()`
para decidir si existe: si el slug no está en el diccionario, `notFound()`, sin
importar lo que diga la API (evita que dar de alta una sede nueva en el admin
de Django, algo que el dueño ya puede hacer hoy, cree un pin/card que apunta a
una página sin contenido).

```json
"sedes": {
  "la-paz": {
    "empresaFundadoraSlug": "sal-y-sol",
    "empresaFundadoraNombre": "Sal y Sol Sportfishing",

    "negocio": {
      "nombre": "Sal y Sol Sportfishing",
      "calle": "Marina La Costa, Rangel y Navarro",
      "ciudad": "La Paz", "estado": "Baja California Sur", "pais": "MX",
      "horarioApertura": "05:00", "horarioCierre": "07:00"
    },
    "meta": { "title": "...", "description": "..." },

    "hero": { "video": "/videos/videohero.webm", "titulo": "...", "subtitulo": "...", "facts": ["..."] },
    "colaboracion": { "titulo": "...", "texto": "...", "imagen": "/..." },
    "temporada": { "...": "..." },
    "incluye": { "...": "..." },
    "licencia": { "...": "..." },
    "galeria": { "fotos": ["/..."] },
    "resenas": { "items": [{ "autor": "...", "texto": "...", "estrellas": 5 }] },
    "faq": { "items": [{ "pregunta": "...", "respuesta": "..." }] },

    "destacadas": [
      { "tipo": "servicio", "slug": "pesca-deportiva", "empresaSlug": "sal-y-sol", "inlineable": true },
      { "tipo": "paquete", "slug": "brunch-y-pesca", "inlineable": false }
    ],

    "otrasEmpresas": [
      { "slug": "hotel-malecon", "nombre": "Hotel Malecón",
        "descripcion": "Hospedaje frente al mar en el malecón de La Paz.",
        "enlaceExterno": "https://..." }
    ],

    "servicioTransporte": { "empresaSlug": "transporte-la-paz" }
  },
  "la-ventana": {
    "empresaFundadoraSlug": null,
    "empresaFundadoraNombre": null,
    "negocio": null,
    "meta": { "title": "...", "description": "..." },
    "hero": { "video": null, "imagen": "/...", "titulo": "...", "subtitulo": "...", "facts": [] },
    "colaboracion": { "titulo": "placeholder", "texto": "placeholder honesto" },
    "temporada": null, "incluye": null, "licencia": null,
    "galeria": null, "resenas": null, "faq": null,
    "destacadas": [],
    "otrasEmpresas": [],
    "servicioTransporte": null
  },
  "puerto-chale": {
    "empresaFundadoraSlug": null,
    "empresaFundadoraNombre": null,
    "negocio": null,
    "meta": { "title": "...", "description": "..." },
    "hero": { "video": null, "imagen": "/...", "titulo": "...", "subtitulo": "...", "facts": [] },
    "colaboracion": { "titulo": "placeholder", "texto": "placeholder honesto" },
    "temporada": null, "incluye": null, "licencia": null,
    "galeria": null, "resenas": null, "faq": null,
    "destacadas": [], "otrasEmpresas": [], "servicioTransporte": null
  }
}
```

Notas:

- **`empresaFundadoraSlug`/`Nombre`**: contenido editorial, sin relación con
  `Empresa.exclusiva` (§1.1). El slug es el mismo valor que trae
  `ServicioCatalogo.empresa_slug`/`PaqueteCatalogo.empresa_lider_slug`.
- **`negocio`/`meta`/`hero`/`colaboracion`/`temporada`/`incluye`/`licencia`/
  `galeria`/`resenas`/`faq`**: contenido migrado tal cual de las claves
  globales de hoy (`NEGOCIO` en `lib/site.ts`, `dict.hero`, `dict.about`, etc.)
  hacia la entrada `la-paz`; cualquiera de estas puede ser `null` por sede — el
  componente correspondiente (§6, §8, §9) simplemente no se renderiza cuando su
  clave es `null`, no inventa contenido de relleno.
- **`destacadas`**: lista ordenada a mano de qué chips ofrece el Paso 0 (§7).
  Las entradas de tipo `paquete` **no** llevan `empresaSlug` — cuál ruta de
  checkout usar (mono vs. cruza-empresa) depende de los componentes del
  paquete, no del líder, y eso solo lo sabe la respuesta de
  `getPaquetesSede`/`getServiciosSede` (§7). `inlineable: true` es solo una
  intención editorial; la página la valida contra una regla mecánica antes de
  confiar en ella (§7) — no es, por sí sola, lo que decide si el chip se abre
  inline.
- **`otrasEmpresas`**: solo empresas sin reserva integrada navegable desde esta
  página (ej. hotel socio sin checkout en el sistema). Si una empresa sí tiene
  reserva integrada (transporte), no lleva entrada aquí — vive en
  `servicioTransporte`/`destacadas`/el grid de Servicios (§6.4).
- **`servicioTransporte`**: puntero al producto de traslados de la sede (si
  existe) y a su URL de entrada real (`/traslados`, página con flujo propio).
- **`enlaceExterno`**: único dato sin equivalente en la API hoy.

## 5. Hub central (`/[lang]`)

Cuatro secciones:

1. **Hero de agencia.** Nombre "Sal y Sol Baja Experiences", una línea de misión,
   imagen de costa. Un solo CTA: "Elige tu destino" — `scrollIntoView` suave a la
   sección del mapa (ancla, sin router). Sin selector ni dropdown aquí. Sin
   booking bar de ningún tipo — elegir sede es el único paso de esta pantalla.
2. **Mapa ilustrado.** SVG/ilustración a la medida de Baja California Sur (no
   mapa real/API externa). Un pin por sede resultante de la intersección
   diccionario × `getSedes()` (regla de reconciliación, §4). Click en un pin
   abre un popover local (no navega): foto chica (de `hero.imagen`/`hero.video`
   si existe, si no un placeholder genérico), nombre de sede, "con
   `<empresaFundadoraNombre>`", botón "Ver destino" → `Link` a
   `/[lang]/sede/[slug]`. Pensado para crecer: agregar un pin nuevo no debe
   requerir tocar el layout (solo agregar la entrada al diccionario).
3. **Grid de sedes.** Debajo del mapa, las mismas sedes en tarjetas normales
   (foto, nombre, empresa fundadora, CTA) — respaldo accesible/SEO para quien no
   interactúa con el mapa (móvil, sin JS, lector de pantalla).
4. **Por qué Sal y Sol Baja Experiences.** 3 pilares cortos (alianzas locales de
   confianza, un solo lugar para reservar en toda Baja, atención personalizada)
   — el diferenciador real es el modelo de alianzas, no relleno genérico.

Nada de reseñas/temporada/licencia en el hub — es contenido específico de sede.
Sin `<StructuredData>` de negocio en esta v1 (§9) — no hay un solo negocio/
horario que declarar en una página que agrupa varias sedes con datos distintos.

## 6. Página de sede (`/[lang]/sede/[slug]`)

Plantilla única, reutilizada por cada sede, alimentada 100% por
`sedes.<slug>.*` (§4) más el catálogo (`getPaquetesSede`/`getServiciosSede`).
Orden:

1. **Hero.** Contenido de `sedes.<slug>.hero`. **Solo si esa sede es la que
   hoy tiene el flujo heredado de pesca funcionando (hoy: únicamente `la-paz`)**,
   el hero monta el `BookingBar` inline existente, sin cambios, con
   `id={ID_BARRA_PORTADA}` — el mismo mecanismo de hoy (`sticky-booking-bar.tsx`
   busca ese id; sin él, `StickyBookingBar` simplemente no encuentra nada y no
   se muestra, que es su comportamiento normal hoy en cualquier página sin
   hero). **Para cualquier otra sede, el hero NO monta `BookingBar`/
   `StickyBookingBar`** — sería el formulario de pesca de La Paz cobrando en la
   cuenta de Sal y Sol, sin relación con esa sede. En su lugar, todas las sedes
   (incluida `la-paz`) muestran el selector de experiencia del Paso 0 (§7) como
   parte del hero — es un componente nuevo y ligero, no `BookingBar`.
2. **Paso 0 — selector de experiencia.** Ver §7 para el comportamiento completo.
3. **Paquetes** (grid) — migrado de `/catalogo` (`PaqueteCard`, sin tocar su
   UI ni su botón de reserva), filtrado a la sede. `moneda` viene de `?moneda=`
   en la URL de la página de sede, igual que hoy en `/catalogo` (default
   `MXN`), y se pasa tal cual a `PaqueteCard`.
4. **Servicios sueltos** (grid) — migrado de `/catalogo`
   (`ServiciosSueltosSection`, sin tocar su UI ni su botón de reserva), mismo
   manejo de `moneda`. Si `sedes.<slug>.servicioTransporte` no es `null`, esta
   sección incluye una card de traslados cuyo CTA enlaza a
   `servicioTransporte.hrefTraslados` en vez del `/reservar?servicio=` genérico
   — es un producto con flujo propio, no un `ServicioCatalogo` más.
5. **Sobre la colaboración** (`sedes.<slug>.colaboracion`) — historia de la
   empresa fundadora y de la alianza que dio origen a la sede. Va después de
   ver la oferta (3-4), no antes.
6. **Qué se pesca / Temporada** (`temporada`) e **Incluye/Licencia**
   (`incluye`/`licencia`) — cada una se renderiza solo si su clave no es
   `null` en el diccionario de esa sede (hoy: solo `la-paz`).
7. **Otras empresas de la sede** (`otrasEmpresas`) — solo si el arreglo no está
   vacío: una card chica por empresa, foto/logo pequeño, nombre, una línea de
   qué ofrece, link que sale del sitio (`enlaceExterno`, `target="_blank"`)
   hacia su página o redes. Directorio/reconocimiento, no un segundo camino de
   venta — nunca compite visualmente con la sección 5 ni con las cards de
   compra de 3-4.
8. **Galería** (`galeria`), **Reseñas** (`resenas`), **FAQ** (`faq`) — cada una
   se omite si su clave es `null` (hoy, todas `null` para La Ventana y Puerto Chale).
9. Footer — dirección/ciudad vienen de `sedes.<slug>.negocio` (`null` → el
   footer omite ese bloque en vez de mostrar el de La Paz).

Las secciones 6-9 son opcionales por sede; la plantilla no obliga a rellenar lo
que esa sede no tiene todavía.

## 7. Selector de experiencia y booking bar — comportamiento

**Regla mecánica, no editorial, para decidir qué se abre inline:** un chip solo
puede comportarse como "inline" si, en tiempo de render, cumple las tres
condiciones a la vez: `sede.slug === 'la-paz'`, la entrada es de
`tipo: 'servicio'` con `slug === 'pesca-deportiva'`, y `empresaSlug ===
process.env.NEXT_PUBLIC_EMPRESA_SLUG`. Esta condición vive en código, no se
confía en el `inlineable: true` del diccionario por sí solo — si alguien marca
`inlineable: true` en una entrada que no cumple la condición, el código la
trata como `false` y el chip navega en vez de abrir el formulario de pesca de
La Paz. Esto evita que un error de captura en el diccionario cobre un viaje en
la cuenta equivocada sin que nada lo detecte.

- **Selector de experiencia (todas las sedes, dentro del hero, §6.1).**
  Muestra chips a partir de `sedes.<slug>.destacadas` (§4), resueltos contra el
  catálogo real de esa sede (`getPaquetesSede`/`getServiciosSede`, ya
  necesarios para §6.3-6.4) en tiempo de render: el nombre del chip sale del
  objeto del catálogo (no del diccionario, que no lo tiene), y si una entrada
  de `destacadas` no tiene contraparte en el catálogo (producto renombrado o
  desactivado desde el admin) esa entrada se omite en silencio — no rompe la
  página, solo aparecen menos chips. Se completa con un link `Ver todo →`.
- **Click en el chip que sí cumple la regla mecánica (hoy: solo pesca en
  La Paz)** → monta/revela el `BookingBar` inline **existente, sin cambios**
  (mismo `ProveedorReserva`, mismo `getCupoRango`, mismas horas fijas) — no se
  generaliza nada, se usa tal cual para el único caso en que ya es correcto.
- **Click en cualquier otro chip** → navega de inmediato (sin expandir nada) a
  la URL que produce el helper compartido `src/lib/booking-href.ts` (extraído
  de la lógica que hoy vive inline en `PaqueteCard`/`ServiciosSueltosSection`
  — mismo cálculo exacto, sin reinventarlo: mono-empresa vs. cruza-empresa vía
  `esPaqueteCruzaEmpresa`, con `paquete_empresa` como *fallback* igual que hoy,
  con `moneda` en ambas rutas, con el prefijo `/${lang}` siempre presente). El
  chip y la card de la sección correspondiente llaman al mismo helper — nunca
  pueden desincronizarse porque no hay dos implementaciones del cálculo.
  - transporte → `hrefServicio()`; el contenido solo declara `empresaSlug` y no
    guarda una segunda copia de la ruta.
- **`Ver todo`** → `scrollIntoView` a la sección de Paquetes (§6.3). Las cards
  de ahí usan su botón de reserva **actual, sin cambios** — no ganan un botón
  nuevo, no hay "volver a subir al bar".
- **Consecuencia aceptada:** en las sedes pendientes (sin flujo heredado de pesca), ningún
  chip cumple la regla mecánica — todo chip navega directo a checkout, igual
  de rápido que hoy hacer click en una card de `/catalogo` (cero regresión). El
  beneficio de "menos pasos" aplica donde ya existe esa capacidad (La Paz/pesca);
  en el resto, la ganancia es de descubrimiento (ver la oferta sin ir a una
  página aparte), no de menos clics.
- **`StickyBookingBar` solo puede aparecer en `/sede/la-paz`** — es la única
  página que monta un elemento con `ID_BARRA_PORTADA` (§6.1); en cualquier otra
  sede, `StickyBookingBar` simplemente no encuentra ese id (su comportamiento
  normal y ya existente hoy en cualquier página sin hero) y no se muestra. No
  requiere ningún cambio en `StickyBookingBar` para lograr esto.

## 8. Componentes reutilizados vs. nuevos

**Reutilizados sin cambio de UI ni de destino de navegación:** `PaqueteCard`,
`ServiciosSueltosSection` (su lógica interna de armado de `href` se extrae a
`booking-href.ts`, §7 — el componente sigue produciendo exactamente la misma
URL y el mismo botón que hoy), `Hero` (contenido, mantiene su `BookingBar`
inline con `ID_BARRA_PORTADA` **únicamente en `la-paz`**, §6.1), `AboutSection`,
`SeasonSection`, `IncludedSection`, `LicenseSection`, `GallerySection`,
`ReviewsSection`, `FaqSection`, `SiteFooter`, `StickyBookingBar`/
`ProveedorReserva`/`BookingBar` (sin generalizar, sin cambios de código — su
único punto de montaje sigue siendo el hero de `la-paz`), `SedeSelector`
(cambia su destino de navegación y de dónde lee la sede activa — §3).

**Nuevos:** página `/[lang]/sede/[slug]`, helper `src/lib/booking-href.ts`
(extracción, §7), sección de mapa ilustrado + pines + popover, grid de sedes
del hub, sección "por qué la agencia", sección "sobre la colaboración",
sección "otras empresas de la sede", el selector de experiencia del Paso 0
(§6.1, §7).

## 9. Qué se retira / redirige / ajusta

- **`/[lang]/catalogo/page.tsx`** deja de tener contenido propio; se reemplaza
  por un componente que solo resuelve `redirect()`: si trae `?sede=<slug>`
  válido → `redirect('/'+lang+'/sede/'+slug)`; si no → `redirect('/'+lang)`.
  No se borra el archivo (Next necesita algo en esa ruta para poder
  redirigir); se borra su `loading.tsx`.
- **`SedeSelector`** deja de construir `/${lang}/catalogo?sede=${slug}` como
  destino; construye `/${lang}/sede/${slug}` directo. El stub de arriba queda
  solo para links viejos/externos.
- **`/[lang]/traslados/page.tsx`** (link de "volver" del estado no-disponible)
  y **`traslado-view.tsx`** (línea ~500, link de "volver" del flujo normal):
  ambos hoy apuntan a `/${lang}/catalogo`. Cambian a `/${lang}/sede/${slug}`
  buscando, entre las entradas del diccionario (§4), cuál trae
  `servicioTransporte.empresaSlug` igual al `empresaSlug` de ese traslado; si
  ninguna coincide, cae a la primera sede activa.
- **`paquete-checkout.tsx`** (línea ~557, mismo patrón: link a `/${lang}/catalogo`)
  cambia a `/${lang}/sede/${sede de la orden}` (el slug de sede ya viaja en los
  datos del paquete/orden).
- **`SiteHeader`** — se le agregan props (`variante: 'hub' | 'sede'`,
  `sedeSlugActual?: string`) y se actualizan **todos** sus puntos de montaje:
  `app/[lang]/{page,catalogo/page,deslinde/page,privacidad/page,traslados/page,
  not-found}.tsx` y `components/{checkout-view,paquete-checkout,
  booking-confirmation,traslado-view}.tsx`. En una página de sede,
  `sedeSlugActual` viene del parámetro de ruta. En cualquier otra página
  (hub, checkout, deslinde, privacidad, 404), viene de
  `leerSedePreferidaCliente()` (`src/lib/sede.ts`, ya existe, ya se lee en
  cliente/post-hidratación igual que hace `SedeSelector` hoy) con fallback a la
  primera sede activa; esto es una conveniencia de navegación, no contenido
  primario, así que un fallback client-side post-hidratación es aceptable (un
  crawler ve el fallback por defecto, no un valor en blanco).
  - `brandMain`/`brandAccent`/`location` dejan de ser un valor fijo de
    diccionario raíz: en el hub, marca de agencia sin ubicación; en cualquier
    otra página, nombre/ubicación de `sedeSlugActual`.
  - El logo (`logo2salysol.webp`, hoy fijo en `SiteHeader`) se muestra solo
    cuando `sedeSlugActual === 'la-paz'`; en el hub y en cualquier otra sede se
    usa un logo/wordmark genérico de agencia (asset placeholder, mismo criterio
    de "hardcodeado" que el resto del contenido — §2).
  - Los links `#temporadas`, `#nosotros`, `#galeria`, `#preguntas` pasan a
    apuntar a `/${lang}/sede/${sedeSlugActual}#nosotros` etc. en vez de a `/`;
    en el hub esos anchors no existen (se ocultan del nav ahí, ver §5).
  - El link `catalogo: "Experiencias"` cambia de destino: en el hub, ancla a
    la sección "Grid de sedes" (§5.3); en una página de sede, ancla a su propia
    sección de Paquetes (§6.3).
- **SEO/datos estructurados**: `<StructuredData>` se mueve de `/` a
  `/[lang]/sede/[slug]`, parametrizado con `sedes.<slug>.negocio` (§4) —
  cuando `negocio` es `null` (hoy, `la-ventana` y `puerto-chale`), el componente no renderiza
  nada (sin datos inventados). El hub no lleva `StructuredData` de negocio en
  esta v1 (§5). `RUTAS` en `src/lib/site.ts` (hoy `['', '/reservar', '/deslinde',
  '/privacidad']`) gana una entrada `/sede/<slug>` por cada slug del
  diccionario que además siga activo según la misma regla de reconciliación
  del hub (§4) — así una sede desactivada en el admin también sale del sitemap,
  con el mismo comportamiento de fallo-abierto si la API no responde al
  momento de generar el sitemap.

## 10. Riesgos / preguntas abiertas

- El mapa ilustrado necesita el asset (SVG/ilustración) — se genera en la fase
  de implementación con los skills de diseño de imagen, no en este spec.
- La Ventana y Puerto Chale sin contenido narrativo/fotos/reseñas reales y sin chip inline
  puede sentirse "menos pulido" que La Paz — aceptado a propósito (§2, §7); si
  el dueño consigue contenido y empresas colaboradoras reales o se construye disponibilidad
  por servicio más adelante, se llena sin cambiar la plantilla.
- Llenar `sedes.la-paz.*` implica mover, no reescribir, el contenido que hoy
  vive en las claves globales del diccionario (`hero`, `about`, `season`,
  `included`, `license`, `gallery`, `reviews`, `faq`, `NEGOCIO`) — es trabajo
  mecánico de recorte/pegado, pero es real y hay que contarlo en el plan de
  implementación, no asumirlo gratis.
- Si en el futuro se necesita más de un chip inline (ej. La Ventana también gana
  un flujo de pesca propio con horarios propios), eso requiere generalizar
  `getCupoRango`/`TimeField`/`PeopleStepper` por servicio — trabajo de API
  explícitamente fuera de este spec (§2).
- Ninguno de los cambios toca datos de producción ni requiere migración de
  base de datos — reversible con un revert de PR.

## 11. Verificación

Sin backend ni datos nuevos: `tsc --noEmit`, `eslint`, `next build` limpios, y
smoke visual manual del dueño en `localhost` (política del proyecto: no se
verifica UI abriendo el navegador desde el agente). Casos a revisar a mano:
- Hub → click de pin → página de sede → chip inline (solo en La Paz) →
  Personas/Fecha/Hora → mismo flujo de pago de siempre sin tocar.
- `/es/sede/la-ventana` y `/es/sede/puerto-chale`: sin `BookingBar`/`StickyBookingBar`, sin
  temporada/licencia/galería/reseñas/FAQ, con placeholder honesto donde
  corresponda, sin ningún dato de La Paz visible.
- Chip no-inline → aterriza en la misma URL de checkout que hoy daría la card
  equivalente en `/catalogo` (mismo `paquete_empresa`, misma `moneda`, mismo
  prefijo de idioma).
- `Ver todo` → card de Paquetes/Servicios → su botón de reserva de siempre.
- `/catalogo`, `/catalogo?sede=la-ventana` y el alias legado
  `/catalogo?sede=los-cabos` redirigen a donde corresponde.
- `/traslados` (ambos links de "volver") y el back-link de `paquete-checkout.tsx`
  aterrizan en la página de sede correcta, no en `/catalogo`.
- Nav: los anchors `#nosotros` etc. funcionan desde `/reservar`, `/deslinde`,
  `/privacidad`, apuntando a la sede correcta; en el hub no aparecen.
- Header en `/`, `/sede/la-paz`, `/sede/la-ventana` y `/sede/puerto-chale` muestra el logo/marca
  correcta en cada caso.
- `SedeSelector` en `/es/sede/la-ventana` muestra "La Ventana" marcado, no la
  última sede guardada en localStorage.
- `sitemap.xml` incluye La Paz, La Ventana y Puerto Chale (y sus rutas `/en`).
- Desconectar backend y cargar el hub: sigue mostrando las 3 sedes (fallo
  abierto), no una página vacía.
