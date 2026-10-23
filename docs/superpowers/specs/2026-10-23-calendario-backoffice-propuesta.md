# Calendario del backoffice — propuesta (taste, borrador para PFD)

Fecha: 2026-10-23. Estado: propuesta; pendiente de evaluación PFD y luego implementación.
Origen: un compañero del dueño pidió "algo tipo Google Calendar" para que los jefes vean todas las reservas por
día, semana y mes, con su estado y el detalle al hacer clic. Además dijo que la "Agenda" actual es operativa y
no debería llamarse así.

Estilo de taste (app screen): `accent-ladder`, seed 1820232695, `--keep palette,type` (el shell es Unfold y no se
toca). Hoja en `.taste-skill/app-calendario/direction.json`.

## 1. Inventario

**Objetos** (todo sale de `Reserva`; no hay tabla nueva, igual que Finanzas):

| Qué se ve | De dónde sale | Cómo ocupa el tiempo |
|---|---|---|
| Pesca / paseo suelto (`por_recurso_dia`) | `Reserva.fecha` + `hora` (5–7 am la pesca) | Un evento en un día, con hora |
| Hospedaje suelto (`por_noche`) | `Reserva.fecha` → `fecha_salida` | Una estancia de varias noches |
| Paquete de una empresa | `inicio_paquete` → salida del hospedaje; días de mar en `ReservaSalida` | Una estancia + sus salidas al mar |
| Traslado | `ViajeTransporte` (único / ida / regreso), cada tramo con su fecha y hora | Un evento por tramo |
| Orden cruza-empresa | Cada `Reserva` de la orden es de su empresa | Cada jefe ve solo su parte |

**Estados** (`Reserva.Estado`): pendiente de pago · pagada sin asignar · asignada · completada · cancelada.

**Magnitudes reales.** Recién lanzado, sin ventas reales: el calendario va a abrir casi vacío por semanas. En
temporada, Sal y Sol llega a 10 pangas al día (10 viajes como tope); La Ventana tiene 5 pangas, un hotel y
paquetes de 4 a 7 noches. Un mes lleno por empresa: del orden de 50–200 reservas. El operador ve las 4 empresas.

**Personas.** Jefe de cada empresa: lo abre una o dos veces al día en laptop para saber cómo va la semana y el
mes. Vendedora: lo tiene abierto en su jornada; su trabajo diario de asignar sigue en la pantalla de asignar.
Operador de plataforma (el dueño): las 4 empresas juntas.

**Trabajos desde aquí**, del más frecuente al menos: (1) abrir una reserva para ver o cambiar algo; (2) ver qué
falta por asignar y saltar a asignarlo; (3) ver qué tan lleno está un día antes de prometer un lugar por WhatsApp.

**Cosas propias del producto:** las pangas (flota fija por empresa), la salida al amanecer, las estancias de
varias noches de La Ventana, los tramos de ida y regreso del traslado, el nombre y el sello de cada empresa.

## 2. La pregunta de la pantalla

> **¿Qué tenemos en estos días y cuál de esas reservas necesita algo de mí?**

**Hallazgo** (línea bajo el título, calculada para el periodo visible):
"Del 20 al 26 de octubre: 14 reservas · 3 pagadas sin panga · 1 atrasada". Si no hay nada pendiente:
"Del 20 al 26 de octubre: 14 reservas, todas asignadas". Sin reservas: "Sin reservas del 20 al 26 de octubre".

## 3. Nombres en el menú

| Hoy | Propuesta | Por qué |
|---|---|---|
| Agenda | **Asignar pangas** | Dice el trabajo que se hace ahí. |
| Traslados | **Asignar vehículos** | Pareja de la anterior: las dos pantallas de asignar se reconocen juntas. |
| — | **Calendario** (primero en "Operación") | Es lo que el jefe busca primero. |

Solo cambian el título del menú y el `verbose_name` de los proxies; las URLs no cambian.

## 4. La pantalla

### 4.1 Fila de título

- h1 **Calendario** (24px) y debajo el hallazgo (14px gris).
- A la derecha, en una sola fila de controles de 32px: `‹` **Hoy** `›`, el periodo en palabras
  ("20 – 26 oct 2026"), y un control segmentado **Día | Semana | Mes**.
- Operador: un selector **Empresa** (Todas / cada una) a la izquierda de esa fila. Jefe y vendedora no lo ven:
  RLS ya les limita la vista a su empresa.
- Segunda fila, un solo interruptor de texto: "Mostrar canceladas" (apagado). Las pendientes de pago no se
  muestran: cada checkout abandonado deja una y llenarían el calendario. Para eso existe "Checkouts abandonados".
- La vista elegida, el periodo y la empresa viven en la URL (`?vista=semana&desde=2026-10-20&empresa=…`), así
  Atrás y los enlaces funcionan.

### 4.2 Cómo se pinta cada estado

Regla del calendario de taste: cada tipo tiene su marca, y el color completo solo va en lo que pide una decisión.

| Estado | Marca | Por qué |
|---|---|---|
| Pagada, sin asignar (fecha futura) | Fondo ámbar pálido, texto ámbar oscuro, "Sin panga" | Pide una decisión: es lo único que debe saltar. |
| Atrasada (pagada sin asignar, fecha pasada) | Pastilla roja pálida, "Atrasada" | Se cobró y nadie la repartió. |
| Asignada | Fondo azul pálido de la marca (`#e8eff2`), texto tinta | Está lista. Es lo normal y va callado. |
| Completada | Fondo gris un tono, texto gris | Ya pasó. |
| Cancelada (solo con el interruptor) | Contorno discontinuo gris, nombre tachado | Ocupa sitio solo si se pide verla. |

Hospedaje y paquetes sin panga que asignar no usan "Sin panga": su estado pagada se pinta como asignada. La
leyenda va en la fila del título, hecha con las mismas marcas a escala, y solo lista los tipos que hay en
pantalla.

**Cara de la pantalla (el estilo pide una):** la escalera sale del azul del sitio (`--color-azul #1b607f`): el
azul completo solo en marcas chicas (la línea de hoy, el día seleccionado, el evento abierto) y sus tintes
pálidos (`#e8eff2`, `#dde6eb`) en las áreas de las reservas asignadas. Así se ve como Sun Baja y no como un kit.

### 4.3 Elemento propio: la tira de pangas del día

Bajo la fecha de cada día (en semana y en mes), una pista de 4px con las pangas ocupadas sobre la flota de
ese día ("6 de 10 pangas"), hecha con la misma lógica del motor de cupo (`capacidades_disponibles`, las pangas
fuera de servicio y el tope del día). Contesta la pregunta 3 sin abrir nada. Solo aparece para empresas con
pangas; el operador la ve por empresa al filtrar por una.

### 4.4 Vista Semana (la vista por defecto)

- **No es una rejilla por horas.** Casi todo sale entre 5 y 7 am: una rejilla de 24 horas quedaría vacía en un
  85 % (regla de taste: un bloque mayormente vacío no se lleva el espacio).
- 7 columnas, lunes a domingo; hoy con una línea azul de 1px y su fecha en tinta; sábado y domingo un tono más
  oscuros.
- **Franja de estancias** arriba (como los eventos de "todo el día" de Google Calendar): las estancias de
  hospedaje y los paquetes como barras de 22px que cruzan sus días, con el nombre del cliente y las noches
  dentro ("Pérez · 5 noches"). Una barra que empieza antes del lunes o sigue después del domingo lleva el borde
  recto de ese lado.
- Debajo, en cada columna, los eventos del día ordenados por hora, en renglones de una línea:
  "6:00 · García · 4 pers." más la marca de estado. Debajo, en gris: el servicio y la panga, o el vehículo
  ("Pesca · Panga Dorado"). Un tramo de traslado lleva "Ida" o "Regreso".
- Los días de mar de un paquete aparecen como eventos en su día ("Paquete · día 2 de mar"), además de la barra
  de la estancia.

### 4.5 Vista Mes

- Rejilla de 7 × 5 (o 6) semanas, lunes primero. Cada día: su número, la tira de pangas y hasta 3 renglones
  ("6:00 García · 4"); si hay más, "+5 más", que abre ese día en la vista Día.
- Las estancias cruzan las celdas como barras, igual que en la semana, una por renglón, hasta 2; luego "+N".
- Días de otro mes en gris.

### 4.6 Vista Día

Una lista, no una rejilla: agrupada por **Al mar** (pesca y paseos), **Estancias** (hospedaje y paquetes que
están ese día) y **Traslados**. Cada renglón: hora · cliente · personas · panga y capitán (o vehículo) · estado
· "Abrir". Arriba, la tira de pangas en grande ("6 de 10 pangas ocupadas").

### 4.7 Detalle al hacer clic

- **Escritorio:** un popover junto al evento, sin salir de la pantalla: cliente y teléfono; servicio, fecha y
  hora (o noches); personas; estado en pastilla; panga y capitán, o vehículo; pagado de total, con moneda;
  canal y vendedora.
- Acciones: **Abrir reserva** (lleva a su ficha en el admin) y, si está pagada sin panga, **Asignar panga**
  (lleva a "Asignar pangas" filtrado a ese día). No se edita nada dentro del calendario: es de solo lectura.
- **Teléfono:** el mismo contenido en una hoja que sube desde abajo.

### 4.8 Teléfono

Unfold ya dobla el menú. En menos de 640px: la vista Día es la única con renglones; Semana se vuelve la lista de
los 7 días seguidos; Mes se queda como rejilla con un punto por reserva y al tocar un día se abre su lista.

### 4.9 Estados vacíos y de carga

- Periodo sin reservas: la rejilla se queda con su marco y una frase que cruza la semana o el mes
  ("Sin reservas esta semana"). Nada de ilustración.
- Servidor de plantillas: no hay estado de carga (la página llega completa). Si una consulta falla, el
  middleware de errores del admin ya avisa.

## 5. Arquitectura (resumen de la revisión Well-Architected)

- **Vista de admin propia**, montada como Finanzas: `path('admin/calendario/', admin.site.admin_view(...))`
  antes de `admin/`, con entrada a mano en `UNFOLD['SIDEBAR']`. Permiso: `bookings.view_reserva`.
- **Renderizado en el servidor** con plantillas de Unfold, sin librería de calendario ni CDN: la rejilla de
  mes y semana es una tabla CSS; un poco de JavaScript propio solo para el popover. (Corrige lo que dije antes
  de FullCalendar: así se respetan los estilos del admin, no hay que cargar nada externo y no hay API nueva que
  proteger.) Ojo con la trampa conocida de Unfold: las clases de Tailwind que su CSS no trae no existen; la
  geometría va en `style=` o en un CSS propio servido como `backoffice.css`.
- **Datos:** una función pura que convierte las reservas del rango en "eventos" y "estancias" (fáciles de
  probar), y una consulta por tipo con `select_related` (servicio, empresa, embarcación, capitán) y
  `prefetch_related` (salidas, viajes). Rango acotado al periodo visible. RLS limita por empresa solo; el
  operador ve todas.
- **Solo lectura:** no toca cobro, cupo ni estados; riesgo bajo. Costo cero; sin infraestructura nueva.
- **Pruebas:** la función de eventos (estancias que cruzan semanas, paquete con salidas, traslado de ida y
  regreso, canceladas ocultas, pendientes fuera), el hallazgo del periodo, permisos (vendedora sí, cliente no,
  RLS por empresa en Postgres) y que la página responda en día, semana y mes.

## 6. Decisiones de PFD (2026-10-23) — MANDAN sobre lo de arriba

Evaluación PFD sobre esta propuesta (sin construir): L0 55 · L1 72 · L2 64 · L3 74 · L4 58 · total 64.
Lo de abajo corrige las secciones 4.2–4.6 donde choquen.

1. **Vista por defecto: Semana.** La pregunta de la pantalla es "estos días"; el mes queda a un clic. La URL
   guarda la vista; sin parámetro abre Semana en la semana actual.
2. **Una reserva = una marca por vista (l018, Sweller 1988).** En Semana y Mes los paquetes y hospedajes son
   SOLO la barra de estancia; sus días de mar NO se repiten como eventos sueltos. La barra dice cuántos días de
   mar lleva ("Pérez · 5 noches · 3 al mar"). Los días de mar sí aparecen como renglón propio en la vista Día
   (grupo "Al mar"), que es donde se reparte. El hallazgo cuenta **reservas**, nunca eventos ni tramos.
   (Excepción natural: un traslado de ida y regreso son dos tramos en dos días distintos; se ven los dos, cada
   uno marcado "Ida"/"Regreso".)
3. **Mes: el día es el blanco del clic, no cada renglón (Cowan 2010, Hick 1952; F-CL-001).** Con 35 celdas y
   3 renglones clicables cada una, el mes pasa de ~150 elementos interactivos. En Mes cada celda muestra hasta
   2 renglones de texto (no clicables) + "+N más", y toda la celda es un enlace a ese día en la vista Día. El
   popover existe solo en Semana y Día.
4. **Semana: renglón de una línea.** Cada evento es una sola línea ("6:00 García · 4" + marca de estado); el
   servicio, la panga o el vehículo van al popover. A 7 columnas en ~1100 px, la segunda línea gris se trunca y
   duplica la altura en temporada (10 salidas al día). Si un día tiene más de 6 eventos, se muestran 5 y
   "+N más" lleva a la vista Día.
5. **Tira de pangas: Semana y Día, no Mes (Green & Swets 1966).** En Mes, 35 medidores son ruido; ahí solo se
   marca "Lleno" en el día que no admite otra salida. Solo con una empresa elegida (con "Todas" no se pinta).
6. **El hallazgo es un enlace (Pirolli & Card 1999; Thaler & Sunstein 2008).** "3 pagadas sin panga" lleva a
   "Asignar pangas" con el rango del periodo; "1 atrasada" lleva al mismo lugar con el filtro de atrasados.
   Con todo asignado, el hallazgo no lleva enlace.
7. **Operador: abre en una empresa, no en "Todas" (l018).** Empresa × estado × tipo en una sola celda es un
   producto cartesiano. El selector arranca en la primera empresa (por nombre); "Todas" sigue disponible y ahí la
   empresa va como texto corto al inicio del renglón, nunca como color.
8. **Color fuerte: solo "Sin panga" (ámbar) y "Atrasada" (rojo pálido).** Hoy se marca con la línea azul de
   1px y su fecha en tinta; no compite con el estado. Confirmado.
9. **Predicción tipo Google Calendar (Clark 2013):** el número del día (en Semana y Mes) es enlace a la vista
   Día. Hacer clic en un hueco vacío no hace nada (no hay "crear" aquí; el calendario es de solo lectura) y el
   cursor no lo sugiere.
