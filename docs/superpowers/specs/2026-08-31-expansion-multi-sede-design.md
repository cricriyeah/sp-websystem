# Expansión multi-sede: aislamiento, catálogo por capas, cupo y precio

Fecha: 2026-08-31
Estado: **PROPUESTA DE DISEÑO — para que el dueño la apruebe antes de escribir plan de implementación.**
Autor: fase de arquitectura (great_cto/architect), sin tocar código de producción.

> **Revisión 2 (2026-08-31).** Incorpora 5 correcciones del dueño: (1) cardinalidad
> invertida a marketplace — Sede agrupa N Empresas, no al revés; (2) el % de la
> plataforma se cobra fuera del sistema, confirma Stripe estándar sin Connect a escala
> de plataforma; (3) el operador de plataforma es la empresa de marketing, y quitar
> `is_superuser` a los jefes queda **aprobado**; (4) Paquete es producto de primera
> clase, editable in-place (Perception-First Design); (5) cupo simplificado — todos los
> paseos comparten `por_recurso_dia`, sin `multi_slot` en v1. Las secciones afectadas
> llevan la marca de la corrección correspondiente.

> **Para quién es este documento.** Lo lee el dueño, que opera el negocio además
> de programarlo. Cada sección tiene primero la decisión en lenguaje llano (para
> decidir con criterio de negocio) y después el detalle técnico. No hay que leer
> código para entender los trade-offs; sí para implementarlos después.

> **Dónde vive esto.** Se guarda en `docs/superpowers/specs/` a propósito, junto
> a las specs anteriores (cupo por tamaño, agenda, extras checkout), para no
> fragmentar la documentación del proyecto. Los ADR formales van en el archivo
> hermano `2026-08-31-expansion-multi-sede-ADRs.md`, en esta misma carpeta.

> **Qué NO es esto.** No es un plan de implementación, no hay migraciones ni
> código. Es el paso previo: 2-3 caminos por cada decisión grande, con su costo y
> su riesgo, y una recomendación. El plan (skill `writing-plans`) se escribe
> después, en la conversación principal, solo si apruebas esto.

---

## 0. Resumen para decidir rápido

Cuatro decisiones, cuatro recomendaciones en una frase cada una:

| # | Decisión | Recomendación en una frase |
|---|---|---|
| **(a)** | Aislamiento Sede/Empresa/tenant | **Una sola base de datos con `empresa_id` en cada tabla + RLS de Postgres como red de seguridad (Opción A). Cardinalidad de marketplace: Sede (localidad/ciudad) agrupa **N Empresas** proveedoras; Empresa = frontera de aislamiento/dinero/Stripe (confirmado por el dueño); la empresa de marketing dueña de la plataforma es el operador por encima de todas.** |
| **(b)** | Modelo Sede→Paquete→Servicio→Personalización | **Híbrido (confirmado por la vía de los hechos, ver correcciones 4 y 5): catálogo, personalizaciones y paquetes 100% desde el admin (datos); las reglas de cupo y precio de cada *tipo* de servicio en código (estrategias). Paquete es producto de primera clase, editable in-place. Un servicio genuinamente nuevo con reglas nuevas requiere código, pero aislado para que no rompa lo existente.** |
| **(c)** | Estrategias de cupo/disponibilidad | **Estrategias tipadas en código sobre un núcleo compartido de "ocupación de recurso por rango" (`por_recurso_dia`, `por_noche`, `bajo_demanda`), más un eje independiente `modo_ocupacion` (exclusivo/compartido) configurable por Servicio — corrección 8: NO todos los paseos son exclusivos, algunos (ej. tours a playas) comparten panga entre grupos distintos. Pesca sigue siendo la implementación de referencia del modo exclusivo. `por_recurso_multi_slot` queda fuera de v1 (corrección 5).** |
| **(d)** | Estrategias de precio | **Estrategias tipadas en código (`por_persona`, `por_grupo/plano`, `por_noche`, `tarifa_fija`) más reglas de paquete, todas funciones puras en `apps/payments/pricing.py` — extendiendo el "todo el dinero se calcula en un solo lugar" que ya existe, no reemplazándolo.** |

**Actualización (correcciones del dueño, 2026-08-31).** Las decisiones grandes que
antes estaban abiertas ya se cerraron: la cardinalidad se invirtió a marketplace
(Sede agrupa N Empresas), el % de la plataforma se cobra fuera del sistema
(confirma Stripe estándar por empresa sin Connect), el dueño **aprobó** quitar
`is_superuser` a los jefes, Paquete quedó definido como producto de primera clase, y
el cupo se **simplificó** (todos los paseos comparten una sola regla). El alcance del
punto 6 (híbrido vs motor configurable) queda **resuelto por la vía de los hechos**:
las correcciones 4 y 5 toman decisiones *por tipo de servicio* (paseos = una regla,
hotel = noches, chef/transporte = bajo demanda), que es exactamente el patrón de
estrategias, no un motor configurable. El diseño procede sobre el enfoque híbrido.

**Lo único genuinamente nuevo que queda por decidir** (no bloquea la dirección de
arquitectura, sí bloquea *implementar paquetes que cruzan empresas*): cómo se cobra
un Paquete cuyos Servicios pertenecen a **empresas distintas**, dado que cada empresa
tiene su propia cuenta Stripe, sin Connect y sin reparto automático. Lo detallo en la
sección (b), con un default recomendado consistente con "el dinero se mueve fuera del
sistema".

---

## 1. Qué existe hoy (verificado contra el código, no supuesto)

Antes de proponer nada, esto es lo que el sistema **es hoy**, leído de
`backend/apps/fleet/models.py`, `backend/apps/bookings/models.py`,
`backend/apps/payments/` y `backend/CLAUDE.md`:

- **Es de un solo negocio, sin ninguna noción de empresa/sede/tenant.** Busqué
  `empresa`, `sede`, `tenant` en todo el backend: **cero resultados**. Todo es
  global: `Embarcacion`, `Capitan`, `Reserva`, los catálogos, la `Tarifa`.
- **`Tarifa` es un singleton forzado** (`self.pk = 1` en `save()`). Hay un solo
  precio de tour en todo el sistema. Multi-sede rompe esto de raíz: cada
  servicio de cada sede tiene su propio precio.
- **El motor de cupo es una joya y hay que preservarlo.** `caben()` y
  `motivo_sin_lugar()` son funciones **puras** (no tocan la base), probadas, y
  las comparten los cuatro caminos que deciden disponibilidad (validación al
  pagar, `/api/cupo/`, próxima fecha disponible, `revisar_cupo`). Su regla no es
  "cuenta asientos": es un **emparejamiento** de grupos contra pangas de
  distinto tamaño, de mayor a menor. Un grupo de 4 necesita una de las 2 pangas
  grandes **aunque queden 20 lugares libres**. Esto importa muchísimo para la
  sección (c).
- **El candado de concurrencia es por fecha, global.** `bloquear_cupo_del_dia()`
  toma un advisory lock de Postgres con clave `fecha.toordinal()`. Hoy funciona
  porque hay un solo negocio y un solo servicio. Con multi-sede, dos empresas
  distintas reservando la misma fecha se **bloquearían entre sí sin razón**, y
  peor: contarían cupo mezclado. La clave del lock tiene que incluir el ámbito
  (servicio/recurso), no solo la fecha.
- **El dinero se calcula en un solo lugar**, `apps/payments/pricing.py`, con
  funciones puras que reciben primitivos (`cargo_por_extra`,
  `cargo_por_transporte`, `cargo_por_descuento`, `monto_inicial`…). El precio se
  **congela al pagar** (`CrearPagoView`), nunca se confía del cliente. MXN y USD
  son dos precios de lista independientes, sin tipo de cambio. Esto es la
  garantía más delicada del sistema (lo dice `backend/CLAUDE.md`) y **no se
  parte** en la sección (d).
- **El patrón de catálogo reutilizable ya existe a nivel de un servicio.**
  `ExtrasItem` (catálogo) + `ReservaExtra` (asociación con precio congelado) es
  exactamente el patrón de Personalización que quieres promover — tu
  retroalimentación #4 es correcta y la valida el código. Hoy le falta la tabla
  de asociación con *overrides* (precio local, obligatorio/opcional) porque solo
  hay un servicio; la sección (b) la agrega.
- **Stripe es una sola cuenta, una sola llave, un solo webhook.**
  `stripe_client.py` hace `stripe.api_key = settings.STRIPE_SECRET_KEY` (global),
  y hay un único endpoint `POST /api/stripe/webhook/`. Cada empresa con su propia
  cuenta Stripe obliga a llaves y webhooks **por empresa** — lo detallo en (a).
- **Los jefes son `is_superuser=True`.** Esto es incompatible con "aislamiento
  TOTAL entre empresas": un superusuario de Django ve **todas** las filas de
  **todas** las empresas en el admin. Lo confirmé en `setup_roles.py` y en
  `finance/views.py:143` (el panel de finanzas corta con `is_superuser`). Este es
  **el hallazgo más importante de aislamiento** y lo trato en (a) y en el ADR-002.
- **Pre-lanzamiento.** No hay clientes ni dinero real (Stripe en `sk_test_`). Una
  migración destructiva no destruye nada de valor. **Pero** el código y el negocio
  de La Paz sportfishing deben migrar limpio al modelo nuevo, no descartarse.

### Restricciones fijas que traigo de sesiones previas (no las re-derivo)

De `[[plan-expansion-multi-empresa]]`, del contexto que me diste y de las
correcciones del dueño del 2026-08-31:

- **No es una alianza de 3 dueños iguales: es una plataforma de marketplace.** El
  dueño real del sistema es una **empresa de marketing** (el usuario, 2 personas)
  que **no** es "una empresa más" del catálogo. Tiene contrato de exclusividad con
  la pesquera de La Paz (esa sí exclusiva a la plataforma) y cobra un % de sus
  ganancias; la plataforma **no** es exclusiva — se están sumando otras empresas
  independientes (transporte, hospedaje) de La Paz y de otras localidades, sin
  exclusividad.
- **El % de la plataforma se negocia y se cobra 100% FUERA del sistema** (acuerdo
  comercial por empresa), igual que ya funciona hoy la comisión de la vendedora: el
  sistema solo da visibilidad/atribución, **nunca mueve el dinero**. Esto confirma
  Stripe estándar por empresa, sin Connect, sin reparto automático — a escala de
  plataforma completa, no solo para 3 empresas fijas.
- Cada Empresa es dueña de su dinero, con su propia cuenta Stripe estándar.
  Aislamiento TOTAL entre empresas; sin vista consolidada para ningún jefe de
  empresa (la empresa de marketing sí ve todo, ver ADR-002).
- Marca pública única con selector de ubicación; un solo Next.js multi-tenant.
- Catálogo de servicios varía por empresa (dentro de una sede); flota/recursos
  dedicados por tipo de servicio (no se comparte recurso entre servicios).
- Equipo de 2 programadores, un mes de plazo por pieza, gates-only.

---

## 2. SEÑALES de riesgo de esta expansión (para no perderlas de vista)

Este cambio cruza fronteras que el sistema hoy no tiene. Las nombro para que
ninguna se cuele:

- **Frontera tenant→tenant (lo más delicado).** La frontera es la **Empresa**, no
  la Sede: Empresa A jamás debe ver reservas, flota ni dinero de Empresa B, aunque
  compartan Sede (misma localidad). La Sede es solo un agrupador geográfico de cara
  al cliente, no aísla nada. Hoy no existe ninguna frontera; se crea desde cero. Un
  filtro `empresa_id` olvidado en **una sola** consulta nueva filtra todo. Por eso
  la recomendación incluye RLS como red de seguridad, no como lujo.
- **Frontera de dinero.** Cada empresa cobra a **su** cuenta Stripe. Un evento de
  webhook mal ruteado marca pagada una reserva de la empresa equivocada, o peor,
  atribuye ingreso de A a B. Son negocios distintos: esto es plata de alguien más.
  **Nuevo con el marketplace:** un Paquete puede combinar Servicios de empresas
  distintas dentro de una Sede — y una cuenta Stripe estándar sin Connect solo puede
  cobrar a **una** cuenta por cargo. Cómo se cobra ese paquete es una decisión de
  frontera de dinero que hay que cerrar antes de implementar paquetes cruzados (ver
  (b), pregunta abierta única).
- **Entrada controlada por el cliente.** El checkout público ahora manda
  `sede`, `empresa`, `servicio`, `zona`, opciones de personalización — todo elegible
  por el cliente. Ya hay precedente de resolver esto en el servidor y no confiarlo
  (`ReservaTransporte.zona` se deriva del punto de encuentro, no del cuerpo de la
  petición). El mismo principio aplica a `servicio_id`/`empresa_id`: el precio y la
  disponibilidad los decide el servidor contra el catálogo de esa empresa, nunca el
  monto que mande el navegador.
- **Control nuevo con riesgo inverso.** Quitarles `is_superuser` a los jefes cierra
  la fuga entre empresas, pero su inverso es dejar a un jefe sin acceso a lo suyo, o
  que el "operador de plataforma" (la empresa de marketing) sea una llave maestra
  sobre todas las empresas. Este operador es real y necesario (ve todo para soporte
  y para su visibilidad de comisión, que ningún jefe de empresa debe ver), así que
  su acceso debe auditarse. Hay que diseñar ambos lados (ADR-002).
- **Ejecución que cambia.** El webhook se rutea por empresa; `conciliar_pagos`
  corre por empresa; el advisory lock del cupo se re-llavea por ámbito. Nada de
  esto es opcional para que el aislamiento sea real.

**Tamaño: Large.** (Ya está así en `.great_cto/PROJECT.md`.) Se agrega una
dimensión de tenancy a **cada** modelo del sistema y se generaliza el motor de
cupo y el de precio. No es una tarea acotada.

**Gate que esto obliga.** Antes de implementar, una revisión de seguridad del
modelo de aislamiento (frontera tenant→tenant + dinero por empresa, sobre un
archetype `commerce` con PCI-DSS SAQ-A). Lo obligan las líneas de *frontera* y
*dinero* de arriba. En términos del proyecto: tu aprobación de este diseño es el
gate previo a `writing-plans`.

---

## (a) Modelo de aislamiento: Sede / Empresa / tenant (marketplace)

### En lenguaje llano

> **Corrección del dueño (2026-08-31): la cardinalidad estaba al revés.** La
> versión anterior de este documento decía "una Empresa tiene N Sedes". Es al
> contrario, porque esto **no** es una alianza de 3 dueños iguales — es una
> **plataforma de marketplace**. El dueño del sistema es una empresa de marketing
> (2 personas) que no aparece en el catálogo. Lo correcto: **una Sede (localidad)
> agrupa N Empresas proveedoras.**

Necesitamos tres cosas a la vez que hoy no existen:

1. **Separar el dinero y los datos por empresa proveedora.** La pesquera de La Paz,
   una empresa de transporte, un hospedaje — son dueños distintos. Ninguno ve lo del
   otro. Esa es la **frontera de aislamiento**.
2. **Agrupar por localidad de cara al cliente.** El cliente entra, elige (o se
   detecta) su ciudad, y ve todo lo que se ofrece ahí — de todas las empresas de esa
   localidad, junto.
3. **Sumar empresas y localidades sin límite** ("las veces que necesite"), sin
   exclusividad (salvo la pesquera de La Paz, que sí es exclusiva por contrato).

Los dos conceptos y cómo se relacionan:

- **Sede** = una localidad/ciudad (La Paz, La Ventana, Puerto Chale…). Es un
  **agrupador geográfico de cara al cliente, NO una frontera de aislamiento**.
  Agrupa **N Empresas**.
- **Empresa** = una empresa proveedora dentro de una Sede (pesca, transporte,
  hospedaje…). Es la **frontera del dinero y del aislamiento**: tiene su cuenta
  Stripe, es dueña de sus reservas/flota/finanzas, y su jefe solo ve **lo de su
  Empresa** (confirmado por el dueño). Cada Empresa ofrece sus propios tipos de
  servicio.
- **Operador de plataforma** = la empresa de marketing dueña del sistema. **No** es
  una Empresa del catálogo; está **por encima de todas**, ve todo (para soporte y
  para su visibilidad de comisión), y ninguna Empresa la ve a ella ni ve su comisión.
  Cobra su % a cada Empresa **fuera del sistema** (ver ADR-002 y corrección 2).

Cardinalidad, entonces: **Sede 1 → N Empresas**; cada Empresa pertenece a una Sede
(campo `empresa.sede_id`). Un mismo cliente en la Sede "La Paz" ve, en una sola
pantalla, servicios de la pesquera, del transporte y del hospedaje — tres Empresas
aisladas entre sí en datos y dinero, pero agrupadas geográficamente para él. Un
Paquete puede combinar Servicios de varias de esas Empresas (ver (b)).

El costo de modelar los dos niveles ahora es una columna (`empresa.sede_id`). El
costo de meterlos después, con datos ya cargados, es una migración de tenancy — el
peor tipo. Pre-lanzamiento el riesgo es bajo hoy, pero es tan barato que no vale la
pena apostar a no necesitarlo.

### La decisión técnica de aislamiento: A vs C (B ya está descartada)

Son tres formas de separar los datos en la base:

- **Opción A — Una Postgres, `empresa_id` en cada tabla + RLS.** Todo en la misma
  base (la Supabase que ya usas). Cada fila lleva de qué empresa es. El
  aislamiento se hace en tres capas: (1) el ORM filtra por empresa en cada
  consulta, (2) el admin de cada jefe solo ve su empresa, (3) RLS de Postgres
  (Row-Level Security) rechaza a nivel de base cualquier fila de otra empresa,
  aunque alguien olvide el filtro en (1). La capa (3) es la red de seguridad.
- **Opción B — Una Postgres por empresa (3 deploys).** Descartada en la sesión del
  26 de agosto: 3× infraestructura, costo y mantenimiento para 2 programadores.
  La menciono solo para dejar constancia de que se evaluó y por qué no.
- **Opción C — Una Postgres, schema separado por empresa** (`django-tenants` o
  similar). Punto medio: más aislamiento "por construcción" (cada empresa en su
  propio schema de Postgres), pero migraciones más complejas (hay que migrar N
  schemas), peor integración con las herramientas de Supabase, y menos trillado.

### Comparación con puntaje (criterios de este proyecto: 2 devs, pre-lanzamiento, Supabase)

Peso alto = importa más para *este* negocio. Escala 1 (malo) a 5 (excelente).

| Criterio | Peso | A (FK + RLS) | C (schema por empresa) |
|---|---|---|---|
| Simplicidad para 2 devs | ×3 | 5 | 2 |
| Encaja con Supabase/herramientas actuales | ×3 | 5 | 2 |
| Fuerza del aislamiento | ×3 | 4 (con RLS) | 5 |
| Complejidad de migraciones | ×2 | 5 | 2 |
| Costo de infraestructura | ×2 | 5 | 4 |
| Continuidad con el código actual | ×2 | 5 | 3 |
| **Total ponderado** | | **69 / 75** | **41 / 75** |

**Recomendación: Opción A.** No solo por el puntaje, sino porque el código actual
ya está construido como "un Django, una Postgres, núcleos puros" — A es su
continuación natural; C sería un cambio de eje. El único punto donde C gana
(aislamiento por construcción) lo cierra A con RLS, y ya tienes precedente de RLS
en este proyecto: la fuga de la Data API que se arregló en `2a64a2b`. La debilidad
real de A —"depende de no olvidar el filtro por empresa"— es exactamente para lo
que existe la capa RLS. Ese trade-off es honesto y aceptable; el de C (migraciones
de N schemas con 2 devs y Supabase) no lo es.

> **Chequeo escéptico del criterio que decide.** La premisa de C es "el aislamiento
> por FK es frágil". ¿Es vinculante? Solo si RLS no existiera o no fuera confiable.
> RLS de Postgres es un mecanismo probado, ya lo usas, y la app corre con un rol de
> base que no es superuser (condición para que RLS aplique). Con RLS puesto, el
> filtro olvidado deja de ser una fuga y se vuelve un bug de "no aparecen mis
> datos" — visible y seguro, no silencioso y peligroso. La premisa de C se debilita.
> Veredicto: A.

### Lo que A obliga a cambiar (y son cambios grandes, hay que verlos)

1. **Los jefes dejan de ser `is_superuser=True`. — APROBADO POR EL DUEÑO
   (2026-08-31).** Un superusuario ve todas las empresas: es la negación del
   aislamiento. Pasan a ser staff con un rol por empresa; el admin de Django se
   filtra por `request.user` → su empresa. El rol **"operador de plataforma" es la
   empresa de marketing dueña del sistema** (no un hipotético): cruza todas las
   empresas por doble razón de negocio — soporte **y** visibilidad de su comisión,
   que ningún jefe de empresa debe ver. El panel de finanzas (`finance/views.py:143`)
   cambia su corte de `is_superuser` a "jefe de esta empresa" (ve lo suyo) más el
   operador de plataforma (ve todo, incluida la comisión). Ya no es una recomendación
   abierta: es decisión tomada, pendiente solo de implementar. Detalle en ADR-002.
2. **Stripe por empresa.** Cada Empresa guarda su propia
   `stripe_secret_key`/`stripe_webhook_secret`/`publishable_key` (como referencia
   a secreto, no en texto plano). `stripe_client.py` deja de leer una global y
   recibe la empresa. El webhook pasa a **un endpoint por empresa**
   (`/api/stripe/webhook/<empresa_slug>/`), cada uno verificando con la firma de
   *esa* cuenta — así un evento nunca se aplica a la empresa equivocada.
   `conciliar_pagos` itera por empresa con su llave. También en ADR-002.
3. **El candado de cupo se re-llavea.** `bloquear_cupo_del_dia(fecha)` pasa a
   llavear por `(ámbito, fecha)` donde ámbito es el servicio o el recurso, no el
   día global. Detalle en (c).
4. **`empresa_id` (o `sede_id`) baja a cada modelo** y a cada consulta. La `Tarifa`
   singleton desaparece: el precio vive por servicio.

### Qué migra de La Paz, y cómo (no se descarta)

La Paz se convierte en **Sede "La Paz" → Empresa "Sal y Sol" (la pesquera, exclusiva)
→ Servicio "Sportfishing" (tipo `por_recurso_dia`)**. Sus 10 pangas pasan a ser
`Recurso` de ese servicio; `ExtrasItem`/`TransportePrecio`/`PuntoEncuentro` pasan a
ser personalizaciones de ese servicio o de esa empresa; las reservas existentes (de
prueba) se re-etiquetan o se borran (pre-lanzamiento lo permite). El motor de cupo
actual **es** la estrategia `por_recurso_dia` — no se reescribe, se envuelve. Las
empresas de transporte/hospedaje que se sumen a la Sede "La Paz" son Empresas nuevas,
aisladas de la pesquera, con sus propios Servicios y su propia cuenta Stripe.

---

## (b) Modelo de datos Sede → Paquete → Servicio → Personalización

### En lenguaje llano

Tu modelo en capas es correcto y el código ya lo respalda a medias. La estructura,
con el nivel Empresa intercalado que exige el marketplace (corrección 1):

- **Sede**: la localidad/ciudad. Agrupa **N Empresas** de cara al cliente. No aísla
  nada; es geográfica.
- **Empresa**: la proveedora dentro de la Sede (frontera de dinero/aislamiento).
  Dueña de sus Servicios y Paquetes.
- **Servicio**: la experiencia vendible de una Empresa (sportfishing, seasafari,
  avistamiento, estadía en hotel, chef privado…). Cada uno con sus reglas propias.
- **Personalización**: opciones dentro de un Servicio (transporte, comida,
  licencia, carnada). **Catálogo reutilizable**, no duplicado por empresa ni sede.
- **Paquete**: agrupa 2+ Servicios en una sola venta. **Producto de primera clase,
  editable** (corrección 4, abajo). Puede combinar Servicios de varias Empresas de
  la misma Sede.

La regla "nada es obligatorio de lo anterior" se respeta así: un Servicio no
necesita pertenecer a un Paquete; una Personalización puede existir sin estar
atada aún a un Servicio; La Paz es 1 Servicio sin Paquete, y eso es válido.

**Sobre el alcance del punto 6 (¿cuánto "sin código"?): resuelto por la vía de los
hechos.** Las correcciones 4 y 5 del dueño toman decisiones concretas *por tipo de
servicio* (todos los paseos = una regla; hotel = noches; chef/transporte = bajo
demanda) — eso **es** el patrón de estrategias, no un motor configurable. Dejo abajo
la comparación de los tres enfoques para que quede el razonamiento, pero el diseño
procede sobre el híbrido (Enfoque 3):

### Los tres enfoques del alcance

- **Enfoque 1 — Estrategias en código (chico, rápido, seguro).** El catálogo
  (Sede, Servicio, Personalización, Paquete, precios) se administra 100% desde el
  admin. Pero *cómo se calcula el cupo y el precio* de cada **tipo** de servicio
  vive en código, detrás de una interfaz. Tipos que ya conoces (paseo por día,
  paseo multi-salida, estadía por noches, bajo demanda) ya vienen implementados.
  Un servicio con reglas **genuinamente nuevas** (algo que no encaje en ninguno de
  esos tipos) requiere que un programador agregue una estrategia — pero aislada,
  de modo que **no puede romper** las que ya funcionan.
  - *Para el negocio:* das de alta seasafari, hotel, chef, otro sportfishing, otra
    sede — todo desde el admin, sin llamar al programador, **mientras el tipo ya
    exista**. Solo un tipo de regla nunca visto necesita código (probablemente
    unas horas, no semanas).
- **Enfoque 2 — Motor de reglas 100% configurable (grande, flexible, riesgoso).**
  Una tabla de reglas de cupo y de precio interpretadas en tiempo de ejecución.
  Das de alta *cualquier* servicio con *cualquier* regla desde el admin, sin código
  nunca.
  - *Para el negocio:* nunca dependes del programador para un servicio nuevo. A
    cambio: es mucho más código de base, más difícil de probar, y —lo más grave—
    mueve el cálculo del dinero y del cupo de "un solo lugar en código, probado" a
    "configuración interpretada". El sistema hoy protege el dinero con fiereza
    *justamente* porque vive en un solo lugar; un motor configurable lo dispersa.
    Para 2 programadores, es el camino que más fácil termina en un cobro mal
    calculado que nadie ve.
- **Enfoque 3 — Híbrido (RECOMENDADO).** Es el Enfoque 1 pero nombrando explícito
  qué es dato y qué es código: **catálogo, personalizaciones, paquetes, precios,
  activar/desactivar, textos, fotos → dato (admin)**. **Motor de cupo y de precio
  por tipo → código (estrategias)**. Es exactamente cómo ya está construido el
  sistema: `pricing.py` es código, `ExtrasItem` es dato. No inventamos un patrón;
  extendemos el que ya probó funcionar.

### Comparación con puntaje

| Criterio | Peso | Enfoque 1/3 (estrategias) | Enfoque 2 (motor config) |
|---|---|---|---|
| Rapidez para el equipo de 2 | ×3 | 5 | 2 |
| Seguridad del dinero/cupo (correctitud) | ×3 | 5 | 2 |
| "Alta de servicio sin programador" | ×3 | 4 (si el tipo ya existe) | 5 |
| Continuidad con el código actual | ×2 | 5 | 2 |
| Costo de mantenimiento | ×2 | 4 | 2 |
| Techo de flexibilidad a largo plazo | ×1 | 3 | 5 |
| **Total ponderado** | | **59 / 70** | **35 / 70** |

**Recomendación: Enfoque 3 (híbrido).** El único criterio donde el motor
configurable gana es "nunca depender del programador", y lo gana por poco: con
estrategias, los tipos que ya cubren tus 6-8 servicios observados **no** necesitan
programador. El costo del motor configurable (dinero y cupo interpretados, para 2
devs) es demasiado alto para el beneficio marginal. Si algún día el negocio vende
docenas de tipos radicalmente distintos, se puede migrar a un motor configurable
*desde* las estrategias; al revés (de un motor frágil a estrategias) es mucho más
caro.

### Entidades propuestas (sin sobre-construir)

Solo lo necesario para las capas. Nombres en español, siguiendo el repo.

| Entidad | Qué es | Campos clave (no exhaustivo) | De dónde sale hoy |
|---|---|---|---|
| **Sede** | Localidad; agrupador geográfico (NO aísla) | `nombre`, `slug`, `zona_horaria`, `activo` | nueva |
| **Empresa** | Proveedora; frontera de dinero/aislamiento | `sede` (FK), `nombre`, `slug`, `stripe_*` (ref a secreto), `exclusiva`, `activo` | nueva |
| **Servicio** | Experiencia vendible de una Empresa | `empresa` (FK), `tipo_servicio` (enum→estrategia), `nombre`, `slug`, `estrategia_cupo`, `estrategia_precio`, `modo_ocupacion` (exclusivo/compartido, corrección 8), `activo` | generaliza el "único servicio" implícito |
| **Recurso** | Inventario reservable del servicio | `servicio` (FK), `nombre`, `capacidad_maxima`, `activo` | generaliza `Embarcacion` |
| **RecursoNoDisponible** | Recurso fuera un día | `recurso` (FK), `fecha`, `motivo` | generaliza `EmbarcacionNoDisponible` |
| **TopeDiario** | Tope de operaciones que decide el negocio | `servicio` (FK), `fecha`, `tope` | generaliza `CupoDiario` |
| **Personalizacion** | Opción/complemento (catálogo reutilizable) | `nombre`, `tipo`, `cobrar_por_persona`, `activo`, `servicios_permitidos` (M2M opcional — si vacío, cualquier Servicio puede asociarla; si tiene valores, SOLO esos Servicios la ven/asocian); **sin precio aquí** | generaliza `ExtrasItem` |
| **ServicioPersonalizacion** | Asocia una personalización a un servicio, con *overrides* | `servicio` (FK), `personalizacion` (FK), `precio`/`precio_usd`, `obligatorio`, `preseleccionado`, `activo` | **la tabla que falta hoy** (tu punto #4) |
| **Paquete** | Producto de primera clase; agrupa 2+ Servicios (posiblemente de varias Empresas de la Sede) | `sede` (FK), `empresa_lider` (FK, ver pregunta abierta), `nombre` (experiencial, ej. "Día completo en La Paz"), `precio_ancla`/`precio_ancla_usd`, `regla_precio`, `activo` | nueva (corrección 4) |
| **PaqueteServicio** | Qué servicios integran un paquete y si son removibles | `paquete` (FK), `servicio` (FK), `orden`, `removible` (default True), `ajuste_precio`/`ajuste_precio_usd` | nueva (corrección 4) |
| **Reserva** | La venta | +`empresa` (FK), +`servicio` (FK), +`paquete` (FK, null), + detalle por tipo | generaliza `Reserva` |
| **ReservaOcupacion** | Qué Recurso(s) ocupa una Reserva y en qué rango (corrección 7) | `reserva` (FK), `recurso` (FK), `fecha_inicio`, `fecha_fin` (medio-abierto `[)`) | nueva — paseos/transporte generan 1 fila (rango=1 día), hospedaje puede generar 1..N filas (varias habitaciones) |

**Decisión de diseño clave para Personalización (tu punto #4):** el precio **no**
vive en `Personalizacion` (el catálogo global), vive en `ServicioPersonalizacion`
(la asociación). Así "transporte" existe una vez como concepto reutilizable, pero
cuesta distinto en el sportfishing de La Paz que en el seasafari de La Ventana, sin
duplicar el ítem. Esto es la promoción exacta del patrón `ExtrasItem`/`ReservaExtra`
que pediste: hoy `ExtrasItem` lleva el precio porque solo hay un servicio; al haber
muchos, el precio baja a la asociación.

**Sobre `Recurso` genérico:** un solo `Recurso` con `capacidad_maxima` cubre toda
embarcación de paseo (panga de pesca capacidad 3-5, lancha de seasafari, etc.) — y
gracias a la corrección 5, **todas hacen 1 viaje/día**, así que `Recurso` ya no
necesita `slots_por_dia` (quitado del modelo; multi-slot es non-goal de v1). Los
servicios sin recurso real (chef/transporte privado) no modelan `Recurso`: su
estrategia es `bajo_demanda`. El hotel es el caso que **no** encaja en `Recurso`
simple (habitaciones × noches) — su estrategia `por_noche` lee su propio inventario;
lo trato en (c) y es la razón de que el cupo sea estrategias, no una sola tabla.

### Paquete: producto de primera clase, editable in-place — DECISIÓN TOMADA (corrección 4)

Esto ya **no** es una pregunta abierta. Tras una sesión de *Perception-First Design*
que el dueño corrió aparte, quedó decidido:

- **Paquete es un producto vendible de primera clase**, con su propia tarjeta y
  precio, **nombrado como experiencia** (ej. "Día completo en La Paz"), no como una
  lista de tipos de servicio. Es la **opción dominante** en la pantalla de entrada
  del catálogo.
- **Cada Servicio dentro del Paquete se puede quitar o cambiar desde la misma
  tarjeta, sin perder el anclaje de precio del paquete.** Esto resuelve el caso real
  que preocupaba al dueño: alguien que solo quiere paseo + transporte, sin el
  hospedaje que trae el paquete completo. Por eso el modelo lleva `precio_ancla` en
  `Paquete` y `ajuste_precio` + `removible` en `PaqueteServicio`: el precio arranca
  en el ancla del paquete y se ajusta al editar, no colapsa a suma-de-partes.
- **Servicios sueltos** ("solo transporte") se compran por un **camino secundario**,
  de menor peso visual (búsqueda, link directo), con **cross-sell** de servicios
  complementarios al agregar algo suelto al carrito.

**Qué cambia y qué no.** A nivel de dato cambia poco frente al borrador anterior:
Paquete sigue siendo entidad propia + conjunto de Servicios + su regla de precio
combinado. Lo que cambia es que el **frontend** lo trata como producto de entrada con
edición in-place, no como algo que aparece solo si el carrito calza (descarta la idea
de "Paquete = solo una regla de descuento dinámica sobre carrito").

*Justificación (resumida, ya resuelta con el dueño):* el agrupamiento perceptual
pre-atento necesita una unidad dominante visible de entrada; la carga cognitiva sube
con el número de opciones sueltas a ensamblar; un default editable ancla el precio sin
quitar agencia; un paquete curado baja el riesgo percibido de combinar proveedores
desconocidos; framing experiencial > framing de inventario de partes.

**Las 3 sub-reglas que antes marqué abiertas, ahora resueltas por esta decisión:**

1. *Precio:* el Paquete tiene **precio propio (ancla)** que se ajusta al quitar/cambiar
   Servicios (`precio_ancla` − `ajuste_precio` del servicio removido), no una suma de
   partes con descuento. `regla_precio` queda para futuras variantes.
2. *Disponibilidad:* como los Servicios son removibles/cambiables in-place, un Servicio
   sin cupo **no bloquea el paquete entero**: se ofrece quitarlo o cambiarlo (misma
   mecánica de edición), degradación elegante en vez de bloqueo duro.
3. *Personalización:* vive **en cada Servicio** (`ServicioPersonalizacion`); el Paquete
   no tiene personalización propia en v1.

**La única pregunta genuinamente nueva (frontera de dinero, no bloquea la
arquitectura):** un Paquete puede combinar Servicios de **Empresas distintas** de la
misma Sede, pero una cuenta Stripe estándar sin Connect solo cobra a **una** cuenta por
cargo. ¿Cómo se cobra?

- *Default recomendado, consistente con "el dinero se mueve fuera del sistema":* el
  Paquete tiene una **`empresa_lider`** que cobra el total a **su** Stripe, y liquida a
  las otras Empresas fuera del sistema — igual que la pesquera ya liquida a capitanes y
  que la plataforma cobra su % fuera. Simple, sin Connect, y encaja con el patrón
  existente.
- *Alternativa (más compleja, probablemente no en v1):* el checkout genera un cargo por
  Empresa (varios PaymentIntents en un flujo).
- *Alternativa mínima:* en v1, restringir Paquetes a Servicios de **una sola Empresa**.

Esto lo decide el dueño en la fase de planeación, antes de implementar paquetes
cruzados; no cambia el resto del diseño.

---

## (c) Abstracción de estrategias de cupo/disponibilidad

### En lenguaje llano

Este es **el mayor riesgo arquitectónico** (tu punto #2, correcto), aunque la
corrección 5 lo **simplificó bastante**. Los servicios se agrupan en tres estrategias:

- **Todos los paseos basados en embarcación** (sportfishing, seasafari, avistamiento
  de ballenas, nado con tiburón ballena, paseo a islas, snorkel): un recurso hace **un
  solo viaje al día, sin excepción** (corrección 5). Disponibilidad se calcula por
  rango de un día → `por_recurso_dia`. **Pesca es la implementación de referencia**
  del sub-caso **exclusivo** — no todos los paseos lo son, ver corrección 8.
- **Hotel:** no hay "salidas", hay **noches** con check-in/check-out y un
  inventario de habitaciones. → `por_noche`, siempre exclusivo por habitación.
- **Transporte con flota propia limitada** (confirmado por el dueño: número fijo
  de vehículos que se puede agotar) → `por_recurso_dia`, igual que un paseo:
  vehículo = `Recurso`, capacidad = asientos. **No** es `bajo_demanda` — sí tiene
  cupo real que puede agotarse. Exclusivo o compartido según el Servicio (ver
  corrección 8).
- **Chef privado (u otro servicio sin flota fija que se agote):** no hay cupo
  real, se agenda bajo demanda (quizás con un tope suave). → `bajo_demanda`

> **Corrección 6 (dueño, 2026-08-31): el core de `por_recurso_dia` y `por_noche`
> se unifica.** El dueño observó que paseo (1 día) y hotel (N noches) son el
> mismo problema con distinto largo de rango: **ocupar un Recurso específico
> durante un rango de fechas, emparejando tamaño de grupo/huésped contra
> capacidad del recurso.** No son dos estrategias independientes: `por_noche` es
> `por_recurso_dia` con rango de N días en vez de 1, más la regla "debe ser el
> mismo Recurso durante todo el rango" (que en rango=1 es trivial). Esto **no**
> es la tabla genérica interpretada del enfoque c2 (sigue rechazada) — sigue
> siendo código tipado y puro, solo que un núcleo compartido en vez de tres
> implementaciones sin relación. Detalle abajo. Transporte con flota limitada
> confirma que **este núcleo compartido tiene un tercer usuario** (paseos, hotel,
> transporte), lo que refuerza que vale la pena construirlo una vez.
>
> **Nota para planeación (no bloquea):** si algún vehículo de transporte llegara
> a necesitar 2+ viajes/día (distinto de los paseos, que confirmaste 1/día sin
> excepción), sería una variante del mismo núcleo (rango=1 día, pero N usos en
> vez de 1), a decidir cuando se implemente transporte. Por defecto asume 1
> uso/vehículo/día, igual que paseos, salvo que digas lo contrario.

> **Corrección 7 (dueño, 2026-08-31): semántica de hospedaje — auditoría de
> detalles que la corrección 6 no cubría.** Al revisar performance del núcleo
> compartido, salieron diferencias reales de negocio entre paseo y hospedaje que
> no eran solo de rango de fechas:
>
> 1. **El traslape debe ser medio-abierto (`[check-in, check-out)`), no
>    inclusivo.** Con fechas inclusivas, un check-out en la mañana y un check-in
>    esa misma tarde se marcarían como conflicto — **perdería reservas válidas**,
>    no es solo un tema de velocidad, es un bug de correctitud. El núcleo debe
>    construirse con este límite desde el diseño, no como optimización después.
> 2. **Una reserva de hospedaje puede necesitar varias habitaciones a la vez**
>    (grupo grande, más de un cuarto, un solo pago). Es un patrón estándar en
>    sistemas de hotel reales. **Decisión: sí se soporta desde v1.** Una Reserva
>    ya no asume "un Recurso"; puede tener **1..N asignaciones** de Recurso — ver
>    `ReservaOcupacion` en la tabla de entidades de (b). Paseos y transporte
>    siguen siendo 1 asignación (su caso de uso no cambia), hospedaje puede tener
>    varias.
> 3. **Buffer de limpieza entre checkout y checkin — SÍ existe, pero no bloquea
>    el cuarto todo el día** (confirmado por el dueño). Se resuelve con
>    **horario fijo de checkout/checkin por Servicio** (ej. checkout 11:00,
>    checkin 15:00): el margen de limpieza queda implícito en la diferencia de
>    horas, sin agregar un campo de buffer al motor de cupo. El motor sigue
>    trabajando a nivel de noche/fecha, no de hora — la hora de corte es un dato
>    de catálogo del Servicio, no parte del cálculo de traslape.
> 4. **Extender una estadía ya empezada** (el huésped pide 2 noches más a medio
>    camino) — **fuera de v1.** No es una operación que exista para paseos; para
>    hospedaje se resuelve como cancelar/reservar de nuevo el tramo extra sujeto
>    a disponibilidad, no como modificación in-place. Se puede agregar después
>    sin tocar el núcleo.
> 5. **Cancelar solo algunas noches de una reserva ya pagada** (partir el rango
>    en dos) — **fuera de v1**, mismo motivo que el punto 4. Se documenta en
>    Non-goals (§3) para que no quede implícito.

> **Corrección 5 (dueño, 2026-08-31): fuera `por_recurso_multi_slot`.** El dueño
> confirmó que **ningún** paseo hace 2+ viajes/día — todos comparten la regla de
> pesca. La estrategia antes llamada `por_panga_dia` se generaliza a `por_recurso_dia`
> y aplica a cualquier paseo basado en embarcación. `por_recurso_multi_slot` sale del
> alcance de v1 (queda como non-goal, §3).

> **Corrección 8 (dueño, 2026-08-31): revisa la corrección 5 — no todos los
> paseos son exclusivos.** Al auditar transporte salió que ciertos paseos (ej.
> "tours a playas") pueden llevar **varios grupos distintos en la misma panga a
> la vez**, y que el transporte incluido en un paquete de ese tipo hereda el
> mismo modo. Esto es un eje **nuevo e independiente** del rango de fechas
> (día/noche/hora): **`modo_ocupacion`**, con dos valores:
>
> - **Exclusivo:** 1 reserva ocupa el Recurso completo, emparejado por tamaño.
>   Pesca sigue siendo la referencia. Hospedaje siempre es exclusivo por
>   habitación (corrección 7).
> - **Compartido:** N reservas distintas suman personas contra la
>   `capacidad_maxima` del Recurso — **suma simple, sin reglas finas** (confirmado
>   por el dueño). Tours a playas y el transporte que va dentro de un paquete
>   compartido caen aquí.
>
> **Decisión: `modo_ocupacion` es un campo en `Servicio`, configurable desde el
> admin** (no fijo por tipo) — cualquier servicio nuevo elige exclusivo o
> compartido sin programador, igual que ya eligen `estrategia_cupo`/
> `estrategia_precio`. El núcleo de "ocupación por rango" (corrección 6) sigue
> siendo el mismo para ambos modos — lo único que cambia es la función de
> disponibilidad: **emparejar** (exclusivo, `caben()`/`motivo_sin_lugar()`) vs
> **sumar y comparar contra capacidad** (compartido). No son estrategias de cupo
> nuevas por tipo de servicio; son dos variantes del mismo `PorRecursoDia`/
> `PorNoche`, seleccionadas por `modo_ocupacion`.
>
> **Transporte standalone con varios viajes/día + margen de traslado por
> ruta — confirmado fuera de v1** (mismo criterio que la nota de la corrección
> 6): en v1, transporte standalone usa el mismo patrón de día completo que
> paseos, aunque subutilice el vehículo. Viajes múltiples por vehículo por día
> con margen de traslado se diseña después, sin tocar lo aprobado aquí.

La tentación es hacer **una sola tabla genérica** de "slots con capacidad" y meter
todo ahí, **para todos los servicios sin distinguir modo**. **No funciona en el
caso exclusivo, y hay que ver por qué**, porque ahí es un error caro (en el caso
compartido, contar SÍ es correcto — ver corrección 8):

> El cupo de pesca (modo **exclusivo**) **no es contar asientos**. Es un
> emparejamiento: ¿puedo darle a cada grupo una panga *lo bastante grande*, una
> por panga? Un grupo de 4 necesita una de las 2 pangas grandes **aunque haya 20
> lugares libres** en las chicas. Una tabla de "capacidad = N asientos vendidos <
> N" **no puede** expresar esto en modo exclusivo — diría que hay lugar cuando no
> lo hay. La función `caben()` actual lo resuelve exacto, y una tabla genérica sin
> distinguir modo lo **regresaría**. Ese es el argumento contra el enfoque
> genérico **para servicios exclusivos**; para servicios compartidos (tours a
> playas, transporte en paquete), contar SÍ es el modelo correcto — por eso
> `modo_ocupacion` es una variante dentro de la estrategia tipada, no una
> excepción que la invalide.

Por eso la recomendación es **estrategias**: cada tipo implementa su propia lógica
de disponibilidad detrás de una interfaz común. La de pesca **es el código que ya
tienes**; solo se envuelve.

### Los enfoques

- **Enfoque c1 — Estrategias tipadas en código (RECOMENDADO).** Una interfaz
  `EstrategiaCupo` con, por ejemplo:
  - `disponibilidad(servicio, fecha_o_rango, demanda) -> motivo | None`
  - `validar_al_confirmar(servicio, ..., excluir_pk) -> raise ValidationError`
  - `bloquear(servicio, fecha_o_rango)` (el advisory lock, re-llaveado)

  Implementaciones para v1, sobre un **núcleo compartido** (corrección 6):
  `ocupacion_por_rango(recurso, fecha_inicio, fecha_fin, tamaño_grupo) -> motivo | None`
  — el emparejamiento por tamaño (`caben`/`motivo_sin_lugar` actuales) aplicado a un
  rango de fechas, exigiendo el mismo Recurso libre en cada fecha del rango.
  - `PorRecursoDia` = ese núcleo con rango de 1 día. Envuelve `caben`/
    `motivo_sin_lugar` actuales sin cambiar su comportamiento. Lo reutilizan
    **todos** los paseos y **transporte con flota limitada** (confirmado por el
    dueño — vehículo = `Recurso`, mismo emparejamiento por tamaño de grupo).
  - `PorNoche` = ese mismo núcleo con rango de N noches (check-in→check-out). No
    es una implementación aparte, es el núcleo con un rango más largo.
  - `BajoDemanda` = sin núcleo de ocupación; para servicios sin flota que se
    agote (ej. chef privado).

  Cada una es un **núcleo puro** (sin tocar la base, testeable como `caben` hoy) +
  un **adaptador delgado** que lee las reservas/recursos de ese servicio. Un
  registro `tipo_servicio -> EstrategiaCupo` las conecta. Con la corrección 5,
  `PorRecursoDia` **es** el motor de pesca actual, sin cambios de comportamiento;
  los demás paseos y transporte solo lo apuntan. (La idea previa de "multi-slot
  como caso general" queda descartada por el dueño: ningún servicio de v1 la
  necesita por defecto — ver nota de transporte en la corrección 6.)

  **Por qué esto no es "un modelo de Servicio del que se ramifican los tipos"
  (pregunta del dueño, 2026-08-31):** la ramificación pasa por **código**
  (`EstrategiaCupo`/`EstrategiaPrecio` tipadas), no por el **modelo de datos**.
  `Servicio` sigue siendo una sola tabla uniforme con `tipo_servicio` como enum
  simple; no hay subclases de Servicio ni herencia de tablas (`ServicioHospedaje`,
  `ServicioTransporte`, etc.). Ramificar el modelo de datos por tipo reintroduce el
  mismo riesgo que el enfoque c2 (motor interpretado): cada subclase con su propia
  forma dispersa la garantía de "un solo lugar" que protege cupo y dinero, y
  Django maneja mal la herencia de tablas a nivel de queries y migraciones. El
  núcleo compartido de esta corrección da la reutilización que buscabas (menos
  código repetido entre paseo/hotel/transporte) sin pagar ese costo — la
  ramificación vive en la función de estrategia, no en la tabla.

- **Enfoque c2 — Tabla genérica de slots/inventario interpretada.** Una tabla
  `Slot(servicio, fecha, hora, capacidad)` y un solo motor que resta lo vendido.
  Uniforme, pero (1) no expresa el emparejamiento de pesca —regresión de
  correctitud—, (2) modela mal las noches de hotel, (3) mueve la lógica de
  disponibilidad a datos interpretados. Es el equivalente en cupo del "motor de
  reglas 100% configurable" de (b), con los mismos riesgos.

### Comparación con puntaje

| Criterio | Peso | c1 (estrategias) | c2 (tabla genérica) |
|---|---|---|---|
| Preserva la correctitud de pesca (`caben`) | ×3 | 5 | 1 |
| Cubre hotel (noches) y todos los paseos (1 viaje/día) | ×3 | 5 | 3 |
| Testeable como el núcleo puro actual | ×2 | 5 | 2 |
| Aísla un tipo nuevo sin romper los demás | ×2 | 5 | 3 |
| Uniformidad conceptual | ×1 | 3 | 5 |
| **Total ponderado** | | **48 / 55** | **26 / 55** |

**Recomendación: c1 (estrategias tipadas).** El criterio que hunde a c2 es la
correctitud de pesca: un sistema de cobro no puede permitirse decir "hay lugar"
cuando no lo hay. c1 preserva exactamente el motor probado y agrega los tipos
nuevos sin tocarlo.

### Detalles técnicos que no se pueden olvidar

- **El advisory lock se re-llavea.** Hoy `pg_advisory_xact_lock(fecha.toordinal())`.
  Pasa a una clave que combine `(servicio_id, fecha)` (por ejemplo un hash estable
  de ambos), para que dos servicios/sedes/empresas distintos no se serialicen entre
  sí y para que el conteo de cupo sea por servicio, no global. Sin esto: o hay
  bloqueo cruzado innecesario, o —peor— conteo de cupo mezclado entre empresas.
- **`por_noche` (rango de N noches) — obligatorio implementar como query de
  traslape, NO como loop día por día.** Revisión de performance (2026-08-31,
  Well-Architected Pilar 4/6): un `for noche in rango: verificar(noche)` genera N
  queries secuenciales por reserva (una estadía de 7 noches = 7 round-trips) — evitable
  y más lento que la alternativa. Usar una sola consulta de traslape de rango
  (`daterange && daterange` de Postgres, con índice GiST vía extensión `btree_gist`,
  ya disponible en Supabase) — O(log n), no escaneo. Mejor aún: un constraint
  `EXCLUDE USING gist` a nivel de tabla que rechaza atómicamente dos reservas del
  mismo Recurso con rangos traslapados — la base lo impide en el INSERT, sin
  necesitar el advisory lock de aplicación para este caso (lo reemplaza, no lo
  suma). El lock por `(servicio_id, fecha)` se queda igual solo para
  `PorRecursoDia`/transporte (rango=1 día). Con esta implementación, unificar
  `PorRecursoDia`/`PorNoche` en un núcleo compartido **no** agrega costo de
  recursos ni latencia frente a tenerlas separadas — el riesgo solo aparece si se
  implementa el rango largo como loop, no por compartir el núcleo.
- **`bajo_demanda`** puede empezar como "siempre disponible" (como hoy el
  transporte, que no valida cupo) y ganar un tope suave después si el negocio lo
  pide.

---

## (d) Abstracción de estrategias de precio

### En lenguaje llano

El precio tiene la misma heterogeneidad que el cupo, y por eso su **propia**
abstracción, separada:

- **Por persona** (sportfishing con persona extra, brunch, licencia).
- **Por grupo / plano** (un precio por la panga completa, sin importar cuántos).
- **Por noche** (hotel: precio × noches).
- **Tarifa fija** (chef privado, transporte roundtrip).
- **Precio ancla de paquete** que se ajusta al quitar/cambiar Servicios (regla de
  Paquete, corrección 4 — no es suma-de-partes con descuento).

La buena noticia: el sistema **ya** calcula todo el dinero en un solo lugar
(`apps/payments/pricing.py`) con funciones puras que reciben primitivos, congela el
precio al pagar, y lleva MXN/USD como dos precios independientes. La abstracción de
precio **extiende** eso, no lo reemplaza. **Esta es la garantía más delicada del
sistema y la recomendación la conserva intacta.**

### Los enfoques

- **Enfoque d1 — Estrategias de precio tipadas en código (RECOMENDADO).** Una
  interfaz `EstrategiaPrecio` con `precio_base(servicio, demanda, moneda) -> monto`,
  implementada por `PorPersona`, `PorGrupo`, `PorNoche`, `TarifaFija`. Todas son
  funciones puras en `pricing.py` (como `cargo_por_personas`, `cargo_por_extra` hoy),
  reciben primitivos, no instancias de modelo. La suma de personalizaciones ya está
  resuelta (`cargo_por_extra`/`cargo_por_transporte`). La regla de paquete es una
  función más (`precio_paquete(precios_partes, regla, descuento)`). El congelado al
  pagar en `CrearPagoView` no cambia de lugar: sigue siendo el único que escribe el
  precio. MXN/USD: cada precio nuevo lleva su hermano `_usd`, patrón ya establecido.

- **Enfoque d2 — Reglas de precio configurables en el admin (fórmulas/config).**
  El jefe define la fórmula de precio de cada servicio desde el admin. Flexible,
  pero mueve la matemática del dinero fuera del "un solo lugar" que
  `backend/CLAUDE.md` protege como la regla que no se rompe. Para 2 devs y cobros
  reales, es donde más fácil se cuela un descuadre invisible.

### Comparación con puntaje

| Criterio | Peso | d1 (estrategias) | d2 (config) |
|---|---|---|---|
| Preserva "el dinero en un solo lugar" | ×3 | 5 | 1 |
| Testeable como `pricing.py` actual | ×3 | 5 | 2 |
| Cubre por-persona/grupo/noche/fija/paquete | ×2 | 5 | 5 |
| Continuidad con el código actual | ×2 | 5 | 2 |
| Alta de precio sin programador | ×1 | 4 | 5 |
| **Total ponderado** | | **49 / 55** | **26 / 55** |

**Recomendación: d1 (estrategias de precio tipadas).** El precio de un servicio
*nuevo de un tipo ya conocido* se edita 100% desde el admin (montos, `_usd`,
por-persona sí/no) — no necesita programador. Solo un modelo de precio genuinamente
nuevo necesita una estrategia nueva, aislada. El riesgo de d2 (dispersar el cálculo
del dinero) no compensa.

### Separación explícita cupo ↔ precio

Cupo y precio son **dos ejes independientes** y así se modelan (dos campos en
`Servicio`: `estrategia_cupo`, `estrategia_precio`). Un mismo servicio puede ser
`por_noche` en cupo y `por_noche` en precio (hotel), o `por_recurso_dia` en cupo y
`por_grupo` en precio (una panga privada a precio plano). No se acoplan.

---

## 3. Qué NO se hace (Non-goals) — para no sobre-construir

- **No** vista consolidada para ningún jefe de empresa (el aislamiento entre
  empresas es total). El operador de plataforma (empresa de marketing) sí ve todo —
  eso es un rol, no una "vista de agencia" para las empresas.
- **No** Stripe Connect ni reparto automático de dinero en ningún nivel (confirmado
  a escala de plataforma: el % de la plataforma y cualquier liquidación entre
  empresas de un paquete se manejan fuera del sistema).
- **No** `por_recurso_multi_slot` (2+ viajes/recurso/día) en v1 — corrección 5:
  todos los paseos son 1 viaje/recurso/día. Si algún servicio futuro lo necesita, se
  agrega como estrategia nueva sin tocar las demás.
- **No** motor de reglas 100% configurable en v1 (enfoque 2 de (b)) — se puede
  llegar ahí después *desde* las estrategias si el negocio lo exige.
- **No** compartir recursos entre servicios (cada servicio su flota).
- **No** migración de datos reales heredados: pre-lanzamiento, las reservas de
  prueba se re-etiquetan o se borran. **Confirmar que sigue sin lanzarse** antes de
  implementar (`[[estado-prelanzamiento]]` puede haber caducado).
- **No** tipo de cambio MXN↔USD: siguen siendo dos precios de lista a mano.
- **No** resolver el hotel a profundidad en la primera iteración si el negocio
  arranca con paseos: `por_noche` es la estrategia más distinta y puede ir en una
  segunda tanda, siempre que la interfaz de cupo la contemple desde el diseño.
- **No** extender una estadía de hospedaje ya empezada in-place (corrección 7,
  punto 4) — se resuelve como nueva reserva del tramo extra, sujeta a
  disponibilidad.
- **No** cancelar parcialmente algunas noches de una reserva de hospedaje ya
  pagada (corrección 7, punto 5) — cancelación es de la reserva completa en v1.
- **No** buffer de limpieza configurable en el motor de cupo (corrección 7,
  punto 3) — se resuelve con horario fijo de checkout/checkin por Servicio, dato
  de catálogo, no lógica de disponibilidad.

---

## 4. Preguntas abiertas

Las correcciones del dueño (2026-08-31) cerraron casi todo. Estado:

**Resueltas en sesión de validación del modelo ER (2026-08-31, 4:41am):**
- ✅ *Rol de jefe:* **solo a nivel Empresa**, sin rol intermedio a nivel Sede.
  Confirma ADR-002 tal cual — el único rol que cruza Empresas es el operador de
  plataforma.
- ✅ *¿El "cupo" del modelo ER es un concepto nuevo?* **No** — es lo mismo que
  `TopeDiario` + `Recurso` ya definidos en (b) y (c). No se agrega tabla ni campo
  adicional de cupo.
- ✅ *Campos dinámicos por persona (nombre, altura, peso, identificación):*
  **fuera de v1.** No toca cupo, precio ni aislamiento — se puede sumar después sin
  retocar lo aprobado. Queda como pendiente de fase de planeación (ver seguimiento
  abajo).
- ✅ *Personalizaciones exclusivas de ciertos Servicios:* **sí necesita
  restricción real**, no solo convención de uso. Se agrega `servicios_permitidos`
  (M2M opcional) a `Personalizacion` — ver tabla de entidades en (b). Vacío =
  compartida (comportamiento default); con valores = solo esos Servicios pueden
  asociarla vía `ServicioPersonalizacion`, el resto ni la ve en el selector del
  admin.

**Ya resueltas (antes abiertas):**
- ✅ *Alcance punto 6 (híbrido vs configurable):* híbrido, resuelto por la vía de los
  hechos (correcciones 4 y 5 deciden por tipo de servicio).
- ✅ *Frontera de aislamiento:* la **Empresa** (confirmado); la Sede solo agrupa
  geográficamente.
- ✅ *De-superuser a los jefes + operador de plataforma:* **aprobado** por el dueño; el
  operador es la empresa de marketing.
- ✅ *Reglas de Paquete:* resueltas por la decisión de Perception-First Design (producto
  de primera clase, editable, precio ancla).
- ✅ *¿Paseos con 2+ viajes/día?* No — todos 1 viaje/día; `por_recurso_multi_slot` fuera
  de v1.

**Genuinamente abierta (frontera de dinero — no bloquea la arquitectura, sí bloquea
implementar paquetes cruzados):**
1. **Cobro de un Paquete que combina Empresas distintas** (cada una su Stripe, sin
   Connect). Default recomendado: `empresa_lider` cobra el total y liquida fuera del
   sistema. Ver sección (b). Se decide en planeación.

**Seguimiento para la fase de planeación (no bloquean este documento):**
2. **¿Con qué servicio/empresa arranca la expansión** en concreto (transporte y
   hospedaje de La Paz, otra localidad)? Define qué se implementa primero después de
   envolver el cupo de pesca en `por_recurso_dia`.
3. **¿Sigue sin lanzarse el sitio?** Reconfirmar antes de finalizar cualquier plan de
   migración de datos (`[[estado-prelanzamiento]]` puede haber caducado).
4. **Modelo de campos dinámicos por servicio/personalización** (nombre, altura,
   peso, identificación) — diseñar cuando se implemente el primer servicio nuevo,
   sin tocar lo ya aprobado en este documento.

---

## 5. Cómo seguir

Si apruebas la dirección de este documento, el siguiente paso es el skill
`writing-plans` en la conversación principal, que produce el plan bite-sized por
piezas — probablemente en este orden de dependencia:

1. Sede/Empresa + `empresa_id` (frontera) + RLS + roles-por-empresa + operador de
   plataforma (ADR-001, ADR-002) — la base de tenancy, todo lo demás cuelga de aquí.
2. Envolver el cupo de pesca en la interfaz `EstrategiaCupo` como `por_recurso_dia`,
   sin cambiar su comportamiento (ADR-003) — refactor con red de tests, La Paz sigue
   igual. Los demás paseos lo reutilizan sin código nuevo.
3. Servicio/Recurso/Personalización/ServicioPersonalizacion + estrategias de precio
   (ADR-004) — el catálogo por capas.
4. La primera estrategia nueva (`por_noche` o `bajo_demanda`, según con qué servicio
   arranque la expansión — pregunta de seguimiento 2).
5. Paquete como producto de primera clase, editable in-place (decisión de corrección
   4); antes de paquetes que cruzan empresas, cerrar el cobro (pregunta abierta 1).
6. Frontend multi-tenant: selector de Sede (localidad) → catálogo con Paquetes
   dominantes y Servicios sueltos en camino secundario.

Cada pieza produce software que funciona y se puede probar sola, con La Paz operando
sin interrupción en cada paso.

Los ADR formales de las 4 decisiones están en
`docs/superpowers/specs/2026-08-31-expansion-multi-sede-ADRs.md`.
