# ADRs — Expansión multi-sede

Fecha: 2026-08-31 (Revisión 3 — Secciones 2-8 implementadas)
Estado global: **ADR-001/002 ACEPTADOS; ADR-003/004 IMPLEMENTADOS; ADR-005 PROPUESTO**.
Ver también `2026-09-06-ADR-005-paquetes-cruza-empresa.md` para el tratamiento de paquetes multi-empresa.
Documento de diseño que los sustenta: `2026-08-31-expansion-multi-sede-design.md`
(misma carpeta).

> Estos ADR viven en `docs/superpowers/specs/` a propósito, junto al diseño y a
> las specs previas del proyecto, para no abrir una tercera convención de
> documentación. Son la versión formal y referenciable de las 4 decisiones
> grandes; el "por qué" en lenguaje llano está en el documento de diseño.

---

## ADR-001: Aislamiento por Empresa con una sola Postgres (FK `empresa_id` + RLS); Sede agrupa N Empresas (marketplace)

Fecha: 2026-08-31
Estado: PROPUESTO (frontera Empresa **CONFIRMADA** por el dueño; mecanismo de BD
—Opción A— pendiente de ratificar)

### Contexto

El sistema es hoy de un solo negocio: no existe ninguna noción de empresa, sede o
tenant en el código (verificado: cero referencias en `backend/`). **No es una alianza
de 3 dueños iguales: es una plataforma de marketplace** (corrección 1 del dueño). El
dueño del sistema es una empresa de marketing (2 personas) que no aparece en el
catálogo; agrupa empresas proveedoras (pesca, transporte, hospedaje) por localidad,
con exclusividad solo con la pesquera de La Paz. Aislamiento TOTAL entre empresas
proveedoras. Debe poder sumar empresas y localidades sin límite. Equipo de 2
programadores, Supabase (Postgres), pre-lanzamiento.

Dos fuerzas: (1) separar dinero y datos por empresa proveedora de forma confiable;
(2) agrupar por localidad de cara al cliente y crecer sin rediseñar.

### Decisión

1. **Una sola base Postgres** con una columna de tenancy (`empresa_id`, directa o
   vía relación) en cada tabla del dominio. Aislamiento en tres capas: filtro del ORM
   por empresa, admin de Django filtrado por empresa, y **RLS de Postgres como red
   de seguridad** que rechaza filas de otra empresa aunque se olvide el filtro.
2. **Modelar Sede y Empresa como dos niveles, con cardinalidad de marketplace**:
   **Sede** = localidad/ciudad, agrupador geográfico de cara al cliente, **no aísla
   nada**; agrupa **N Empresas** (`empresa.sede_id`). **Empresa** = proveedora dentro
   de una Sede, frontera de dinero y aislamiento (dueña de su cuenta Stripe, sus
   reservas y su flota). La empresa de marketing es el **operador de plataforma**, por
   encima de todas, fuera del catálogo (ver ADR-002).
3. **La frontera de aislamiento es la Empresa — CONFIRMADO por el dueño.** Dos
   Empresas de la misma Sede jamás se ven entre sí, aunque compartan localidad.

### Alternativas consideradas

- **Una Postgres por empresa (N deploys)** — rechazada: N× infraestructura, costo y
  mantenimiento para 2 programadores; desproporcionado, y peor aún a escala de
  marketplace donde las empresas se suman sin límite.
- **Schema separado por empresa (`django-tenants`)** — rechazada como recomendación:
  más aislamiento por construcción, pero migraciones de N schemas más complejas
  (agravado por el marketplace: N crece), peor encaje con Supabase, y menos
  continuidad con el código actual (un Django, una Postgres, núcleos puros). El único
  punto donde gana (aislamiento por construcción) lo cubre RLS, que ya tiene
  precedente en el proyecto (fix `2a64a2b`).
- **Colapsar Sede y Empresa en un solo concepto** — rechazada: el marketplace exige
  distinguir "localidad que el cliente elige" de "proveedora que se aísla"; sin los
  dos niveles no se puede mostrar un catálogo por ciudad con varias empresas aisladas.
  La columna extra hoy es barata; el retrofit de tenancy después es el peor tipo de
  migración.

### Consecuencias

- Positivo: barato, simple, continúa el diseño actual, y RLS convierte un filtro
  olvidado en un bug visible ("no aparecen mis datos") en vez de una fuga silenciosa.
- Negativo: el aislamiento depende de disciplina en cada query nueva; por eso RLS es
  obligatorio, no opcional. Hay que correr la app con un rol de base que **no** sea
  superuser de Postgres, o RLS no aplica.
- Riesgo: la `Tarifa` singleton (`pk=1`) desaparece y el precio baja a nivel
  servicio — cambio estructural que toca el checkout y el panel de finanzas.

---

## ADR-002: Los jefes dejan de ser superusuarios; roles por empresa; Stripe y webhook por empresa

Fecha: 2026-08-31
Estado: **ACEPTADO** (el dueño aprobó de-superuser a los jefes y el rol de operador de
plataforma el 2026-08-31; pendiente solo de implementar)

### Contexto

Aislamiento TOTAL entre empresas, sobre el modelo de una sola base (ADR-001). Dos
piezas del sistema actual son incompatibles con eso:

1. **Los jefes son `is_superuser=True`** (`setup_roles.py`), y el panel de finanzas
   corta con `is_superuser` (`finance/views.py:143`). Un superusuario de Django ve y
   edita **todas** las filas de **todas** las empresas — la negación del aislamiento.
2. **Stripe es una sola cuenta global**: `stripe_client.py` hace
   `stripe.api_key = settings.STRIPE_SECRET_KEY`, y hay un único webhook
   `POST /api/stripe/webhook/`. Con una cuenta Stripe por empresa, una llave global
   y un webhook único aplicarían pagos a la empresa equivocada.

El modelo de marketplace agrega una razón de negocio (corrección 3): la empresa de
marketing cobra un % a cada empresa, negociado y cobrado **fuera del sistema** (igual
que la comisión de la vendedora hoy; corrección 2). El sistema solo da
visibilidad/atribución de ese %, nunca lo mueve. Esa visibilidad de comisión **ningún
jefe de empresa debe verla** — refuerza que el operador de plataforma sea un rol
separado y real, no un simple "admin técnico".

### Decisión

1. **Jefes = staff con rol por empresa**, no superusuarios (**aprobado por el dueño**).
   El admin de Django y el panel de finanzas se filtran por la empresa del usuario. El
   rol **"operador de plataforma" es la empresa de marketing dueña del sistema** (real,
   no hipotético): por encima de todas las empresas, ve todo para soporte, alta de
   empresas **y su visibilidad de comisión**; ninguna empresa lo ve a él ni ve su
   comisión. El corte `is_superuser` del panel de finanzas pasa a "jefe de esta
   empresa" (ve lo suyo) más el operador de plataforma (ve todo).
2. **Credenciales de Stripe por Empresa**: cada Empresa guarda
   `stripe_secret_key`/`stripe_webhook_secret`/`publishable_key` como referencia a
   secreto (no en texto plano). `stripe_client` recibe la empresa en vez de leer una
   global.

   **Enmienda (Revisión 7 del plan de Pieza 1, N7-F):** el plan de implementación
   guarda las tres llaves como **campos en tabla, en texto plano** — decisión v1
   explícita, no un descuido: sin gestor de secretos en el stack hoy, llaves de
   prueba pre-lanzamiento (`estado-prelanzamiento`), widget de solo-escritura en el
   admin, nunca logueadas, validadas por prefijo en `Empresa.clean()`. Se documenta
   aquí la desviación en vez de re-escribirla en silencio. **Disparador de
   reversión:** antes de que exista cualquier llave `sk_live_` en la tabla, migrar a
   referencia a secreto (Render secret files, o el gestor que se adopte) — no
   esperar a que haya dinero real corriendo con la llave en texto plano.
3. **Un endpoint de webhook por empresa**: `POST /api/stripe/webhook/<empresa_slug>/`,
   cada uno verificando la firma con el `webhook_secret` de *esa* cuenta. Un evento
   nunca se aplica fuera de su empresa. `conciliar_pagos` itera por empresa con su
   llave.

### Alternativas consideradas

- **Mantener jefes como superusuarios y confiar solo en el filtro del ORM** —
  rechazada: un superusuario bypassa el sistema de permisos de Django por completo;
  no hay filtro de ORM que lo contenga en el admin. Incompatible con aislamiento total.
- **Un solo endpoint de webhook que resuelve la empresa por la cuenta del evento** —
  rechazada frente a endpoint-por-empresa: con cuentas estándar, cada cuenta
  configura su propio webhook apuntando a su propia URL; un endpoint por empresa es
  más simple de verificar y deja el aislamiento explícito en la ruta.
- **Stripe Connect** — fuera de alcance, **confirmado a escala de plataforma completa**
  (corrección 2): el % de la plataforma y cualquier liquidación entre empresas se
  cobran fuera del sistema, igual que la comisión de la vendedora. No hace falta
  reparto automático en ningún nivel. (La excepción a vigilar: un Paquete que cruza
  empresas — ver ADR-004 / pregunta abierta del diseño.)

### Consecuencias

- Positivo: aislamiento real en el admin y en el dinero; el webhook no puede cruzar
  empresas.
- Negativo: reescribe el modelo de roles (`setup_roles`), el corte del panel de
  finanzas, `stripe_client`, las rutas de webhook y `conciliar_pagos`. Es la pieza
  con más superficie de cambio.
- Riesgo: dar de baja el superusuario mal hecho puede dejar a un jefe sin acceso a lo
  suyo; hay que probar el rol por empresa antes de quitar el superusuario. El
  "operador de plataforma" es una llave con alcance amplio: su acceso debe auditarse.

---

## ADR-003: Cupo/disponibilidad como estrategias tipadas en código

Fecha: 2026-08-31 (Implementado: 2026-09-06)
Estado: **IMPLEMENTADO**

**Desviaciones y detalles de implementación:**
- Se implementaron 3 estrategias de cupo concretas en `apps.fleet.models`: `por_recurso_dia`, `por_noche` y `bajo_demanda`.
- `por_noche` (hospedaje) implementa `ReservaOcupacion` multi-día sobre `[fecha, fecha_fin_servicio)` serializado con `bloquear_recurso(empresa_id, recurso_id)` y protegido a nivel PostgreSQL mediante constraint `EXCLUDE USING gist` sobre `(recurso_id WITH =, daterange(fecha_inicio, fecha_fin, '[)') WITH &&) WHERE (ocupa_cupo)`.
- La selección de recursos para hospedaje es determinista vía `elegir_recursos(libres, personas, cantidad)`.
- `Reserva.save()` sincroniza `ocupa_cupo` solo al cruzar frontera de estados de ocupación.
- El campo `modo_ocupacion` se mantuvo como enum extensible en el modelo `Servicio`, operando en modo exclusivo en v1.

### Contexto

Los servicios del marketplace tienen reglas de disponibilidad distintas, aunque la
corrección 5 del dueño las **simplificó**: **todos los paseos basados en embarcación**
(pesca, seasafari, avistamiento de ballenas, nado con tiburón ballena, paseo a islas,
snorkel) comparten **una sola regla — 1 viaje/recurso/día, sin excepción** — con
emparejamiento por tamaño de grupo. Quedan aparte el hotel (noches con check-in/out) y
chef/transporte (bajo demanda). El motor de cupo actual (`caben`, `motivo_sin_lugar`)
es puro, probado y compartido por 4 caminos; su regla **no es contar asientos** sino un
emparejamiento de grupos contra recursos de distinto tamaño.

### Decisión

Definir una interfaz `EstrategiaCupo` (`disponibilidad`, `validar_al_confirmar`,
`bloquear`) sobre un **núcleo compartido** (corrección 6, 2026-08-31):
`ocupacion_por_rango(recurso, fecha_inicio, fecha_fin, tamaño_grupo)` — el
emparejamiento por tamaño (`caben`/`motivo_sin_lugar` actuales) aplicado a un rango
de fechas, exigiendo el mismo Recurso libre en todo el rango. Implementaciones para
v1: **`PorRecursoDia`** = el núcleo con rango de 1 día (envuelve el motor de pesca
actual sin cambiar su comportamiento) — lo **reutilizan todos los paseos y
transporte con flota propia limitada** (confirmado por el dueño: vehículo =
`Recurso`, mismo emparejamiento por tamaño). **`PorNoche`** = el mismo núcleo con
rango de N noches (check-in→check-out), no una implementación aparte. `BajoDemanda`
queda para servicios sin flota que se agote (ej. chef privado). Cada una es un
núcleo puro (testeable sin base, como `caben` hoy) más un adaptador delgado. Un
registro `tipo_servicio -> EstrategiaCupo` las conecta. **Pesca es la
implementación de referencia**: los demás paseos y transporte no necesitan código
nuevo, solo apuntan a `PorRecursoDia`. `PorRecursoMultiSlot` (2+ viajes/día)
**queda fuera de v1 por defecto** (non-goal, corrección 5) — incluido transporte,
salvo que el negocio confirme que un vehículo hace 2+ viajes/día, a decidir en
planeación. `Recurso` ya no lleva `slots_por_dia`. El advisory lock se re-llavea
de `fecha` a `(servicio_id, fecha)`.

La ramificación por tipo de servicio vive en el **código** (estas estrategias),
no en el modelo de datos: `Servicio` sigue siendo una sola tabla con
`tipo_servicio` como enum, sin subclases/herencia de tablas. Ramificar el modelo
de datos en vez del código reintroduce el riesgo del enfoque c2 (motor
interpretado) — ver documento de diseño §(c).

**Corrección 8 (dueño, 2026-08-31): eje `modo_ocupacion` (exclusivo/compartido),
revisa la corrección 5.** No todos los paseos son exclusivos: algunos (tours a
playas) permiten varios grupos distintos en la misma panga, y el transporte
dentro de un paquete de ese tipo hereda el modo. Es un eje independiente del
rango de fechas, configurable por Servicio desde el admin (no fijo por tipo).
`PorRecursoDia`/`PorNoche` ganan una variante por modo: **exclusivo** (`caben()`/
`motivo_sin_lugar()`, emparejamiento por tamaño — pesca, hospedaje) o
**compartido** (suma de personas ≤ `capacidad_maxima` del Recurso, sin reglas
finas — tours a playas, transporte en paquete). El argumento contra la tabla
genérica (c2) sigue vigente **solo para modo exclusivo**; en modo compartido,
contar es correcto por construcción — no es la misma falla, es un tipo de
servicio genuinamente distinto que la estrategia tipada ya contempla.
Transporte standalone con múltiples viajes/día y margen de traslado por ruta
queda **fuera de v1** (mismo patrón de día completo que paseos por ahora).

### Alternativas consideradas

- **Una tabla genérica de slots/inventario interpretada por un solo motor** —
  rechazada: no puede expresar el emparejamiento de pesca (diría "hay lugar" cuando
  no lo hay: un grupo de 4 necesita una panga grande aunque haya asientos libres en
  las chicas), modela mal las noches de hotel, y mueve la correctitud del cupo a
  datos interpretados. Es una regresión de correctitud sobre un flujo de cobro.
- **Un motor de reglas 100% configurable desde el admin** — rechazada por las mismas
  razones que su equivalente de precio (ADR-004) y de alcance: demasiado riesgo de
  correctitud para 2 devs.

### Consecuencias

- Positivo: preserva intacto el motor de cupo probado; agrega tipos nuevos aislados
  que no pueden romper los existentes; cada estrategia se prueba como el núcleo puro
  actual.
- Negativo: un tipo de servicio con reglas genuinamente nuevas requiere una
  estrategia nueva en código (horas, no semanas) en vez de configuración.
- Riesgo: re-llavear el advisory lock mal deja bloqueo cruzado entre empresas o
  conteo mezclado; `PorNoche` (bloqueo sobre rango de fechas) es el caso más distinto
  y debe diseñarse con cuidado.

---

## ADR-004: Precio como estrategias tipadas en código, sobre `pricing.py`

Fecha: 2026-08-31 (Implementado: 2026-09-06)
Estado: **IMPLEMENTADO**

**Desviaciones y detalles de implementación:**
- Se implementaron las estrategias tipadas en `apps.payments.estrategias_precio`: `PorPersona`, `PorGrupo`, `PorNoche`, `TarifaFija`.
- El precio de paquetes se consolidó en `pricing.py::precio_paquete_total`: ancla + Σ(personalizaciones obligatorias/preseleccionadas de servicios no removidos) + Σ(personalizaciones opcionales marcadas) − Σ(ajustes de servicios removidos). Personalizaciones por persona multiplican por el número de personas.
- Anticipo configurable por `Paquete.porcentaje_anticipo` y `Servicio.porcentaje_anticipo`.
- Paquetes cruza-empresa: formalmente bloqueados en v1 (`PaqueteServicio.clean`), formalizado como decisión arquitectónica en **ADR-005** (`docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md`). En v1 todo paquete y sus componentes pertenecen a una sola `empresa_lider`.

### Contexto

El precio es tan heterogéneo como el cupo (por persona, por grupo/plano, por noche,
tarifa fija, y precio ancla de paquete que se ajusta al editar Servicios) y necesita
su propia abstracción, separada del cupo. El sistema ya calcula **todo el dinero en un solo
lugar** (`apps/payments/pricing.py`, funciones puras que reciben primitivos), congela
el precio al pagar (`CrearPagoView`), y lleva MXN/USD como dos precios independientes
sin tipo de cambio. `backend/CLAUDE.md` marca esto como la garantía que no se rompe.

### Decisión

Definir una interfaz `EstrategiaPrecio` (`precio_base(servicio, demanda, moneda)`)
con implementaciones tipadas: `PorPersona`, `PorGrupo`, `PorNoche`, `TarifaFija`,
todas como funciones puras en `pricing.py` (mismo estilo que `cargo_por_personas`,
`cargo_por_extra`). El precio de Paquete es otra función pura sobre el **ancla**
editable (corrección 4): `precio_paquete(precio_ancla, ajustes_de_servicios_removidos)`
— arranca en el ancla del paquete y se ajusta al quitar/cambiar Servicios, no es
suma-de-partes con descuento. El congelado al pagar sigue en `CrearPagoView` como único
escritor del precio. Cada precio nuevo lleva su hermano `_usd`. Cupo y precio son ejes
independientes: `Servicio` tiene `estrategia_cupo` y `estrategia_precio` por separado.
**Pendiente para paquetes cruza-empresa:** qué cuenta Stripe cobra el paquete (ver
diseño §(b), pregunta abierta) — no cambia el cálculo del precio, solo a quién se cobra.

### Alternativas consideradas

- **Reglas de precio configurables (fórmulas en el admin)** — rechazada: mueve la
  matemática del dinero fuera del "un solo lugar" que el sistema protege; para 2 devs
  y cobros reales es donde más fácil se cuela un descuadre invisible. La flexibilidad
  extra no compensa el riesgo, porque el precio de un servicio de tipo ya conocido ya
  se edita 100% desde el admin (montos y `_usd`).
- **Reusar la estrategia de cupo para el precio** — rechazada: son ejes
  independientes (un servicio puede ser `por_noche` en cupo y `tarifa_fija` en
  precio); acoplarlos limita combinaciones válidas.

### Consecuencias

- Positivo: conserva intacta la garantía "el dinero en un solo lugar"; el precio de
  un servicio de tipo conocido no necesita programador; se prueba como `pricing.py`
  hoy.
- Negativo: un modelo de precio genuinamente nuevo requiere una estrategia nueva en
  código.
- Riesgo: olvidar el hermano `_usd` en un precio nuevo hace que una reserva en USD
  reciba 503 en ese ítem (comportamiento ya conocido y aceptado con `Tarifa`).

---

## Estado de las decisiones tras las correcciones del dueño (2026-08-31)

Ver §4 del documento de diseño. Resumen:

**Resueltas:**
- ✅ **ADR-001**: frontera de aislamiento = **Empresa** (confirmado); cardinalidad
  Sede → N Empresas (marketplace). Falta solo ratificar el mecanismo de BD (Opción A).
- ✅ **ADR-002**: de-superuser a los jefes + operador de plataforma (empresa de
  marketing) = **ACEPTADO**; Stripe estándar sin Connect **confirmado** a escala de
  plataforma (el % se cobra fuera del sistema).
- ✅ **ADR-003**: **IMPLEMENTADO** (estrategias tipadas `por_recurso_dia`, `por_noche` con `ReservaOcupacion` y `EXCLUDE USING gist`, y `bajo_demanda`).
- ✅ **ADR-004**: **IMPLEMENTADO** (estrategias tipadas `PorPersona`, `PorGrupo`, `PorNoche`, `TarifaFija`, fórmula de paquetes y anticipo configurable).
- 📋 **ADR-005**: **PROPUESTO** — Paquetes cruza-empresa (fuera de v1). Bloqueados formalmente en v1 (`PaqueteServicio.clean`). Ver `docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md`.
