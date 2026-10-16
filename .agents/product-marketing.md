# Contexto de marketing — Sun Baja Experience

> Lo leen las skills de marketing (`cro`, `site-architecture`, `copywriting`…) antes de preguntar. Escrito el 2026-10-16 con las respuestas del dueño. **Lo marcado «PENDIENTE» no se sabe todavía: no lo inventes, pregúntalo o márcalo como supuesto en tu informe.** El contexto operativo y de pagos está en `docs/contexto-negocio.md`.

## 1. Qué es

**Sun Baja Experience** es una marca paraguas (el *hub*) que reúne a varias empresas independientes de turismo en Baja California Sur y les da un solo sitio para mostrar su oferta y vender en línea. **El sitio es una vitrina: no es la empresa que presta el servicio.** Cada empresa cobra directo al turista con su propia cuenta de pagos y es quien opera el servicio.

Sitio bilingüe (es/en), con el mismo peso en los dos idiomas. **Aún no está lanzado**: no hay clientes, reseñas reales, métricas de conversión ni historial de ventas.

## 2. Estructura comercial

| Sede | Empresa | Qué vende |
|---|---|---|
| La Paz | Sal y Sol Sportfishing | Pesca deportiva |
| La Paz | DLS Transporte | Traslados |
| La Ventana | La Ventana Travel | Pesca con mosca, avistamiento de ballenas y orcas, hospedaje, traslado de aeropuerto, paquetes de varios días por persona |
| Puerto Chale | Piratas Adventures | Safari marino, avistamiento de ballenas, pesca deportiva |

- No todas las empresas venden lo mismo. Los tipos de servicio que se pueden reservar en el sitio: **pesca deportiva, paseos y tours (no pesca), hospedaje y paquetes, transporte y traslados**, según sede y empresa.
- Hay paquetes que combinan servicios de una empresa y paquetes que cruzan dos empresas (por ejemplo pesca + traslado en La Paz); en estos el turista paga a cada empresa por separado dentro de un mismo checkout.
- Sitios de las empresas ya revisados (ver `docs/marketing/contenido-empresas.md`): ninguno publica precios, modo de pago, cancelación, clima, licencias ni qué incluye; el catálogo de La Ventana Travel cargado en el sistema es lo que el cliente quiere mostrar. Precios, flotas y descripciones de La Ventana Travel y Piratas Adventures siguen siendo de ejemplo hasta que cada empresa los confirme.

## 3. Cliente

- **Principal:** turista de EE. UU. y Canadá. **Secundario:** turista nacional (México).
- Compra en móvil y en escritorio; el checkout es lo más sensible.
- Llega por **búsqueda en Google (orgánico)** y por **Instagram y Facebook**. Hoteles, concierge y recomendación no se marcaron como canal actual.
- PENDIENTE: cuánto tardan en decidir, qué comparan y si ya están hospedados cuando reservan.

## 4. Qué debe lograr cada página

- **Hub (portada):** *mandar al turista a la sede correcta*, rápido y sin dudas. Debe explicar la dinámica real del sitio (reúne servicios de distintas empresas locales en un solo lugar; cada una opera y cobra directo) y listar todas las empresas con enlace a su página oficial y redes (decisión del dueño).
- **Sede:** llevar a reservar el servicio que busca (meta principal) y resolver las dudas de quien aún investiga (meta secundaria). *Es una propuesta de la skill `cro`, pendiente de confirmar por el dueño.*
- **Conversión final:** una reserva pagada en el checkout.

## 5. Pagos, cancelación y qué incluye

- **Pago:** cada empresa recibe **solo una de dos formas**: 100 % en línea, o 30 % en línea y el resto en efectivo. La empresa decide cuál; el sitio muestra la que aplica a ese servicio.
- **Cancelación:** solo hay reembolso completo por **mal clima**; cambio de fecha permitido con **mínimo 48 horas** de anticipación. (El dueño confirmó que esta regla sigue igual.) PENDIENTE: garantía y su plazo en días; si cada empresa varía.
- **Qué incluye cada servicio varía por empresa, por servicio, por temporada, disponibilidad y economía.** Regla para el contenido: **el sitio no debe prometer de forma general que un equipo, amenidad o personalización está incluido.** Cada servicio muestra su propia lista y los extras se pueden pedir o contratar aparte.
- Monedas: pesos y dólares; un solo precio base en pesos y el dólar se deriva del tipo de cambio de la sede.

## 6. Miedos y objeciones (el dueño confirmó los cuatro)

1. **Pagar por adelantado a un desconocido** (marca nueva, sitio sin historial, y además el pago va a la empresa y no al sitio).
2. **Clima y cancelación** (qué pasa si no se puede salir).
3. **Qué incluye el precio realmente.**
4. **Seguridad, licencias y seguros.**

PENDIENTE: las preguntas reales que hacen los clientes por WhatsApp antes de reservar. Como no se ha lanzado, **no existen todavía**: las objeciones anteriores son hipótesis del dueño y deben validarse con las primeras conversaciones reales.

## 7. Pruebas de confianza disponibles hoy

- **Sí hay:** fotos propias de viajes y de clientes.
- **No hay (o no confirmado):** reseñas propias verificadas (las del sitio son de ejemplo), licencias y permisos mostrables, póliza de seguro mostrable. No se debe simular ninguna.
- **Reseñas de las empresas (decisión del dueño):** se pueden mostrar las que cada empresa ya publica en su sitio, **atribuidas a esa empresa** y con su confirmación previa de que son reales; nunca como verificadas por Sun Baja Experience. Varias de las revisadas parecen de plantilla y no deben publicarse sin esa confirmación.
- Marca nueva sin historial: la confianza debe construirse con claridad (qué pagas, a quién, qué pasa si llueve) más que con prestigio.

## 8. Competencia (a comparar; ver `docs/marketing/analisis-competidores.md`)

Viator, GetYourGuide y sitios de resorts/hoteles con tours en Baja.

## 9. Voz y estilo

- Segunda persona, verbos de acción, copy sin jerga ni mayúsculas decorativas (ver `docs/design/design-guidelines.md`).
- Identidad visual: `docs/design/design.md` (café y arena, Consola Mono en titulares, azul = mar, coral = ciudad, verde = outside o montaña).
- Español e inglés al mismo nivel; el inglés no es traducción literal.

## 10. Restricciones del producto que el contenido debe respetar

- El checkout está en 3 pasos (Viaje, Tus datos, Pago); ver `docs/superpowers/plans/2026-10-15-frontend-base-rediseno.md`.
- Logo y fotos definitivos de la marca nueva: PENDIENTES del dueño.
- Sin lanzar: no hay métricas; las recomendaciones de CRO se basan en buenas prácticas y en los competidores, y se deben marcar como hipótesis a probar después del lanzamiento.
