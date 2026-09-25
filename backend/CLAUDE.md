# CLAUDE.md — backend/

Notas especificas de este modulo. Contexto de negocio completo: ../docs/contexto-negocio.md.

## Estructura y settings

- Apps viven bajo `apps/` (paquete), no como apps top-level: `apps.fleet`, `apps.bookings`.
  Cada `AppConfig` usa `name = 'apps.<app>'` y `label = '<app>'`.
- Settings split en `config/settings/{base,local,production}.py`. `manage.py` usa
  `local` por defecto; `wsgi.py`/`asgi.py` usan `production` por defecto (Render las sobreescribe
  via `DJANGO_SETTINGS_MODULE` solo si hace falta otra cosa).
- `production.py` lee todo de variables de entorno (`DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DJANGO_ALLOWED_HOSTS`) — falla explicito si faltan, no hay defaults.

## Comandos (Windows, venv en `backend/venv/`)

```
venv/Scripts/python.exe manage.py runserver 8000
venv/Scripts/python.exe manage.py makemigrations
venv/Scripts/python.exe manage.py migrate
```

### Data migrations y RLS

Toda data migration que haga `Modelo.objects.create/update/delete` sobre una tabla con RLS debe envolverse en `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):` — si no, revienta en Postgres bajo el rol de la app (ej. `ci_rls` o roles sin `BYPASSRLS`).

### Correr la suite contra Postgres en local

sqlite serializa toda escritura con un solo escritor: los tests de RLS, de
advisory locks y de constraints `EXCLUDE` **no prueban nada real ahí**. Para
correrlos como en CI hace falta Postgres con un rol sin `BYPASSRLS`:

```
docker run -d --name psd-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=pescadeportiva_test -p 5433:5432 postgres:17
docker exec psd-pg psql -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
  "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;"
```

Puerto 5433 en el host (el 5432 suele estar ocupado por otro contenedor). Luego:

```
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
venv/Scripts/python.exe manage.py test apps config
```

`config.settings.ci` hereda de `local` y solo cambia la base (ver el docstring
de `config/settings/ci.py`). El rol `ci_rls` es `NOSUPERUSER NOBYPASSRLS`, así
que `tests_rls.py` prueba el aislamiento de verdad en vez de pasar en verde por
estar exento.

## Estado de las apps

- `fleet`, `bookings`: modelos + admin implementados. Backoffice basico (item 1 de
  contexto-negocio.md) ya cubre catalogo + reservas + roles, ver abajo.
- `payments`: API implementada (crear PaymentIntent + webhook), ver seccion "API
  publica (frontend)" abajo.
- `notifications`: `services.py` con `notificar_reserva_pagada(reserva)` — correo via
  Resend + WhatsApp Business API (plantilla de Meta). Lo llama el webhook de Stripe
  despues de guardar la reserva como `pagada`. Cada canal se activa solo si sus env
  vars estan puestas y **nunca lanza**: el cobro ya ocurrio, una notificacion caida no
  debe hacer que Stripe reintente el webhook.
- `fleet.Servicio`: pesca usa el servicio `pesca-deportiva` de cada Empresa y la
  estrategia `por_grupo`. `precio_base`/`precio_base_usd` y los dos recargos por
  persona son precios de lista independientes; sin precio USD no se cobra en esa
  moneda. El negocio fija cada precio a mano, sin tipo de cambio.
- `finance`: solo lectura, sin modelos. El panel de dinero para jefes, ver seccion
  "Panel de finanzas" abajo.
- Tests: `apps/bookings/tests.py`, `apps/fleet/tests.py`, `apps/payments/tests.py` y
  `apps/finance/tests.py` cubren cupo, ventana de salida, deslinde, capacidad, regla
  de 48h, las tres rutas publicas, el cobro y los balances.
  `venv/Scripts/python.exe manage.py test apps`.

## API publica (frontend)

Sin autenticacion (`AllowAny` en `REST_FRAMEWORK`) — la web nunca loguea, solo crea
reservas/pagos. CORS restringido a los origenes del frontend
(`CORS_ALLOWED_ORIGINS` en `settings/local.py` y `settings/production.py`, esta ultima
via env var). Rutas montadas bajo `/api/` en `config/urls.py`:

- `GET /api/<empresa>/servicios/pesca-deportiva/` — catálogo de pesca, con los cuatro
  precios y personas incluidas (`apps/fleet`). 404 si el servicio no existe o está
  inactivo. Sus amenidades (brunch, licencia, carnada) viven en `personalizaciones`,
  el mismo catálogo unificado de cualquier otro servicio o paquete — no hay endpoint
  de extras aparte.
- `GET /api/cupo/?fecha=YYYY-MM-DD&personas=N` — si cabe un grupo de N ese dia, solo
  informativo (`apps/bookings`); la validacion definitiva ocurre al confirmar el pago.
  `personas` es opcional (default 1), asi que una peticion sin el responde lo mismo que
  antes. Responde ademas `motivo_no_disponible`: `'lleno'` (se acabaron los viajes del
  dia) o `'sin_panga'` (queda dia pero no embarcacion para ese grupo). 400 si falta
  `fecha`, no es una fecha ISO, o `personas` no es un entero entre 1 y `MAX_PERSONAS`.
- `POST /api/reservas/` — crea `Reserva` en `pendiente_pago`, `canal_origen='web'`
  (`apps/bookings`). No ocupa cupo todavia. Requiere `moneda`, `deslinde_aceptado` y
  `deslinde_nombre`; la fecha/hora y la IP del deslinde las sella el servidor. Acepta
  un `ref` opcional (codigo de vendedora, write-only) para atribuir la venta; si no
  resuelve se ignora sin romper el checkout.
- `POST /api/reservas/<id>/crear-pago/` — crea el `PaymentIntent` de Stripe. El monto
  (tarifa en la moneda de la reserva + extras, con pago completo o el porcentaje de
  anticipo configurado cuando está disponible) se calcula siempre en el servidor;
  nunca se confia el total que manda el cliente (`apps/payments`). 503 si la moneda
  pedida no tiene precio.
- `POST /api/stripe/webhook/` — en `payment_intent.succeeded` marca la reserva
  `pagada`, corre `full_clean()` (motor de cupo) y dispara las notificaciones. Si el
  cupo se lleno mientras el cliente pagaba, reembolsa via `stripe.Refund` y deja la
  reserva `cancelada` + `reembolsada` con el motivo real, para que la vendedora la vea.

### Garantias del cobro (apps/payments)

Lo mas delicado del sistema. Reglas que **no** hay que romper:

- El servidor calcula el precio base y el reparto en `apps/payments/pricing.py`, y
  cotiza las personalizaciones en `apps/payments/extras.py`. El cliente manda su
  selección y, cuando aplica, si paga completo o anticipo; nunca un total.
- `crear-pago` es idempotente: reusa el intent de la reserva si sigue sin cobrar, lo
  ajusta con `PaymentIntent.modify` si cambiaron las amenidades, y manda
  `idempotency_key` para el doble clic. Si el intent ya esta en `succeeded`/`processing`
  responde 409 — jamas se crea un intent nuevo encima de uno que ya esta cobrando.
- El webhook es la unica fuente de verdad: nada se marca pagado desde el navegador.
  Corre en `transaction.atomic` con `select_for_update` para que dos entregas
  simultaneas del mismo evento no dupliquen nada.
- Si llega un pago para una reserva que ya estaba pagada **con otro intent**, es un
  cobro duplicado: se reembolsa solo. Si es el mismo intent, es Stripe reintentando y se
  ignora.
- Un pago cuya `reserva_id` no existe se reembolsa.
- `_verificar_monto` recalcula lo que se debia cobrar y registra el descuadre en el log;
  no rebota el pago (el cliente se quedaria sin viaje y sin dinero). El descuadre se ve
  en el admin, columna "Cobro", en rojo.
- Los reembolsos tambien llevan `idempotency_key`. Si el reembolso falla, la reserva
  **no** se marca `reembolsada`.
- El webhook siempre responde 200 salvo firma invalida: un 500 haria que Stripe
  reintente en bucle un evento que no se va a arreglar solo.
- La logica de aplicar un pago vive en `apps/payments/services.py`
  (`aplicar_pago_exitoso`), no en la vista: tiene dos entradas y las dos deben
  decidir igual.
- El webhook tambien escucha `charge.refunded` (un reembolso hecho a mano desde el
  panel de Stripe marca `reembolsada`) y `charge.dispute.created` / `.closed` /
  `.funds_reinstated` (levantan y bajan `en_disputa`). Una disputa **no** cambia el
  estado de la reserva: que hacer con un viaje en contracargo lo decide una persona.
- **Efectivo**: `monto_efectivo` guarda lo que se recibio el dia del viaje — el 70%
  restante del anticipo y lo que el agente haya cotizado aparte (bebidas, transporte),
  por eso puede superar el saldo del tour y no se valida contra el. `saldo_pendiente`
  ya lo descuenta. La accion de admin "Registrar liquidacion en efectivo" rellena el
  saldo exacto y sella quien y cuando; para un monto distinto se edita a mano.
- **Una panga hace una sola salida por dia, y un capitan tambien.** Se valida en
  `Reserva._validar_una_salida_por_dia()`, llamada desde `clean()`, asi que aplica igual
  desde la agenda, desde el admin de Reservas y desde el shell. Cuentan los estados de
  `ESTADOS_QUE_OCUPAN_CUPO`: una cancelada suelta su panga. Las salidas son de 5 a 7am y
  el viaje dura de 6 a 7 horas — escalonar no existe. (Esta nota decia lo contrario hasta
  agosto de 2026, cuando el negocio aclaro la regla.)
- **Red de seguridad**: `manage.py conciliar_pagos [--dias 7] [--dry-run]` busca reservas
  `pendiente_pago` que ya tengan PaymentIntent, le pregunta a Stripe como quedo y aplica
  lo mismo que el webhook. Existe porque una entrega de webhook puede perderse para
  siempre (backend caido, secret mal puesto, Stripe se rinde tras sus reintentos) y
  entonces hay un cliente que pago y no tiene reserva. Correrlo por cron cada hora.
  Es idempotente: en la segunda vuelta esas reservas ya no estan pendientes.

Llaves de Stripe (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`)
se leen de variables de entorno, vacias por defecto en local — `crear-pago` responde
503 si no estan configuradas (el frontend lo maneja mostrando `checkout.paymentUnavailable`).
Igual con las notificaciones: `RESEND_API_KEY`, `RESEND_FROM`, `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE` (default `reserva_confirmada`),
`WHATSAPP_TEMPLATE_LANG` (default `es_MX`).

## Panel de finanzas (apps/finance)

Pantalla unica de dinero, en `/admin/finanzas/` (`apps/finance/views.py`, montada en
`config/urls.py` **antes** de `admin/`, que si no se traga la ruta).
Corta con `scope.es_operador_plataforma(request.user)` (ve todas las Empresas) o
`scope.empresa_actual(request)` no vacío (ve la suya) — ya no con `is_superuser` (ver expansión multi-sede).
Muestra entradas (tarjeta / efectivo), salidas (reembolsos), balance de hoy, del mes y
del año, historico por dia con navegacion de meses, y los dos saldos teoricos contra
los que se cuadra: lo que deberia haber en la cuenta de Stripe y lo que deberia haber
en caja.

**No hay tabla de movimientos.** Todo sale de `Reserva` agregando por fecha
(`apps/finance/services.py`), porque cada peso ya deja su rastro en la reserva que lo
genero y un libro paralelo solo puede acabar descuadrado con ella. Tres movimientos
posibles por reserva, cada uno con monto y fecha propios:

| Movimiento | Monto | Fecha | Quien la sella |
|---|---|---|---|
| Entrada tarjeta | `monto_pagado` | `pagada_en` | webhook de Stripe |
| Entrada efectivo | `monto_efectivo` | `efectivo_cobrado_en` | la vendedora |
| Salida (reembolso) | `monto_reembolsado` | `reembolsada_en` | webhook de Stripe |

Reglas que no hay que romper:

- **Cada moneda por separado, nunca sumadas.** No hay tipo de cambio en el sistema
  (ver precios de `fleet.Servicio`); sumar MXN con USD daria una cifra sin significado.
- **`reembolsada` (bool) no es una salida.** Es la decision de devolver, que toma la
  vendedora al cancelar por mal clima. La salida se registra cuando el dinero sale de
  verdad y llega `charge.refunded`. Por eso una reserva cancelada puede aparecer
  todavia como dinero en la cuenta: es que ahi sigue.
- **La fecha del dinero es la del movimiento, no la del viaje.** Un viaje de diciembre
  pagado hoy sube el balance de hoy. `pagada_en` se toma del `created` del
  PaymentIntent y no de `now()` justo por esto: `conciliar_pagos` puede aplicar dias
  despues un pago cuyo webhook se perdio.
- **"En la cuenta" es bruto.** Stripe descuenta su comision antes de depositar y esa
  comision no se registra en ningun lado; el deposito real siempre es menor. Para
  tenerlo neto habria que leer el `balance_transaction` del cargo en el webhook.
- Los reembolsos no bajan el saldo en efectivo: se devuelven por Stripe, salen de la
  cuenta.
- El menu lateral del admin se arma a mano en `UNFOLD['SIDEBAR']`
  (`config/settings/base.py`) porque esta pantalla no es un modelo y no aparece sola.
  Un modelo nuevo hay que darlo de alta ahi; mientras tanto sigue alcanzable por
  "All applications". Un link mal escrito en ese bloque tumba el admin completo, no
  solo su renglon.

## Registro de ventas: quien vendio que (bookings.Vendedora)

`Vendedora` es un perfil sobre una cuenta de Django (`OneToOneField` al User del grupo
`Vendedora`) con un `codigo` y una bandera `activo`. `Reserva.vendedora` apunta ahi.
Escala a varias vendedoras sin tocar codigo.

**La comision se calcula y se paga fuera del sistema.** Aqui no hay porcentajes,
montos ni saldos a proposito: lo unico que se lleva es el registro de a quien le
corresponde cada venta.

- `canal_origen` (web/whatsapp) y `vendedora` no son lo mismo: una reserva que entro
  por la web puede ser venta suya si el cliente llego por su link. Es el que **vende**,
  no el que administra — asignar panga o capitan despues no cambia el campo.
- Dos formas de atribuir, las dos hacen falta:
  1. **Link**: `?ref=<codigo>` en cualquier pagina de la web. El frontend lo guarda 30
     dias (`frontend/src/lib/ref.ts`) y lo manda al crear la reserva. Un codigo que no
     existe o de alguien inactivo se ignora en silencio — un link viejo mal copiado no
     puede impedir que alguien reserve.
  2. **A mano**: accion "Marcar como venta mia" en `ReservaAdmin`, para lo que se cerro
     por WhatsApp o por telefono. Se autoasigna a quien la ejecuta; no se puede
     atribuir una venta a otra persona desde ahi.
- Reenviar el checkout sin `ref` **no** borra una atribucion ya hecha.
- `vendedora_asignada_en` lo sella `Reserva.save()`, no la vista: hay varias entradas
  (link, panel, shell) y todas deben dejar la misma constancia.
- `on_delete=PROTECT` en las dos puntas: borrar la cuenta dejaria ventas sin dueño.
  Para dar de baja a alguien se desmarca `activo`.
- La vendedora tiene `view_vendedora` (ver `setup_roles`) para consultar su propio
  codigo. Dar de alta vendedoras y cambiar codigos es de jefes.

## Cupo diario

Motor unico en `apps/bookings/models.py`:
`validar_cupo_diario(fecha, personas, excluir_pk=None)`, llamado desde `Reserva.clean()`.
Decide dos cosas y las distingue en el mensaje:

1. **Tope de viajes del dia** — `CupoDiario` de esa fecha, o `CUPO_MAXIMO_DEFAULT = 10`.
2. **Que exista una panga donde quepa ese grupo** — `caben(grupos, capacidades)` empareja
   de mayor a menor los grupos ya vendidos mas el nuevo contra las capacidades a flote
   (`fleet.capacidades_disponibles(fecha)`). Un dia puede tener lugares libres y aun asi
   no admitir un grupo de 4: solo dos pangas de la flota llevan mas de 3 personas.

Los dos numeros son independientes a proposito y confundirlos es facil:

- `CupoDiario` es un **tope que decide el negocio**. Sirve para cerrar el dia entero
  (un 0), para cuando **faltan capitanes** —el motor de cupo no sabe contarlos, puede
  vender diez viajes un dia con seis capitanes— y para cualquier tope sin razon fisica.
- `fleet.EmbarcacionNoDisponible` es un **hecho fisico**: que panga no sale ese dia.
  Reemplaza al uso viejo de `CupoDiario` para "van a faltar embarcaciones", porque
  registra cual falta y por que, y le dice al motor que capacidad se perdio y no solo
  cuantos viajes.
- Una panga dada de baja para siempre se desmarca con `Embarcacion.activa`, no se borra.

No bajar el `CupoDiario` **y** marcar la panga fuera por el mismo motivo: no rompe nada
(queda mas restrictivo, no menos) pero deja dos registros diciendo lo mismo y ninguno
explicando el porque.

El nucleo (`caben`, `motivo_sin_lugar`) es puro y no toca la base: lo comparten la
validacion, `/api/cupo/`, `proxima_fecha_disponible` y el comando `revisar_cupo`, para
que los cuatro no puedan decidir distinto. `evaluar_cupo` consulta sin tomar el lock;
`validar_cupo_diario` lo toma antes de contar (ver `bloquear_cupo_del_dia`).

Solo cuentan contra el cupo los estados en `ESTADOS_QUE_OCUPAN_CUPO` (`pagada`,
`asignada`, `completada`) — `pendiente_pago` no bloquea a otros clientes. Cualquier flujo
nuevo que cree/edite una `Reserva` (API de pago, panel vendedora) debe llamar
`instance.full_clean()` antes de `save()` para que este motor corra — no duplicar la
logica en otro lado.

**El catalogo `Embarcacion` tiene que estar completo en produccion.** Con la flota
incompleta `capacidades_disponibles` devuelve una lista corta y el sitio deja de vender:
fallo seguro y no silencioso, pero fallo.

- Auditoria: `manage.py revisar_cupo [--dias 90]` lista los dias ya vendidos que la flota
  real no puede operar. La validacion corre al guardar, asi que las reservas anteriores a
  este motor sobrevivieron intactas.

## Cupo multidimensional, hospedaje y paquetes turísticos

Con la expansión multi-servicio y paquetes turísticos:

- **Estrategias de cupo (`Servicio.estrategia_cupo`)**:
  1. `por_recurso_dia` (pesca deportiva / embarcaciones): aplica `validar_cupo_diario` y toma advisory lock `bloquear_cupo(empresa_id, fecha, servicio_id)`.
  2. `por_noche` (hospedaje): multi-día sobre rango `[fecha, fecha_fin_servicio)`. Se crean registros `ReservaOcupacion` por habitación/recurso asignado. La base de datos protege contra sobreventa mediante constraint PostgreSQL `EXCLUDE USING gist` sobre `(recurso_id WITH =, daterange(fecha_inicio, fecha_fin, '[)') WITH &&) WHERE (ocupa_cupo)`. Lock de serialización: `bloquear_recurso(empresa_id, recurso_id)`.
  3. `bajo_demanda` (tours/experiencias sin límite físico estricto): no bloquea inventario previo.
- **Sincronización de `ReservaOcupacion.ocupa_cupo`**:
  `Reserva.save()` propaga automáticamente `ocupa_cupo = (estado in ESTADOS_QUE_OCUPAN_CUPO)` a sus `ocupaciones` únicamente cuando la reserva cruza la frontera de ocupación (usando `_estado_original`).
- **Paquetes turísticos**:
  - Todo `Paquete` pertenece a una `sede` y a una `empresa_lider`.
  - `PaqueteServicio.clean()` permite empresas distintas dentro de la misma sede. Los paquetes cruza-empresa usan `Orden` (ver abajo); los mono-empresa conservan su flujo de reserva.
  - Al pagar la reserva de un paquete, `reservar_cupo_al_confirmar()` dentro de `aplicar_pago_exitoso` valida y crea un `ReservaPaqueteComponente(estado_cupo=OK)` por cada componente no removido, y crea las `ReservaOcupacion` correspondientes para hospedaje. Si algún componente no tiene cupo, lanza `SinCupoError`, la transacción hace rollback y se emite reembolso automático 100%.
  - Al cancelar la reserva, `Reserva.save()` sincroniza `componentes` a `LIBERADO` y libera las ocupaciones.
- **Marketplace dinámico en el checkout**:
  - Rutas de API operan bajo `/api/<empresa_slug>/...`.
  - El frontend resuelve dinámicamente la empresa del producto (`paquete.empresa_lider_slug` o `servicio.empresa_slug`), de modo que `crear-pago` cobra directo en la cuenta de Stripe de dicha empresa proveedora (`pago.publishable_key`).

## Agenda operativa

`bookings.Agenda`, proxy de `Reserva` (mismo patron que `CheckoutAbandonado`). Es donde
se reparten los viajes vendidos: que panga y que capitan le toca a cada uno.

- Lista solo `pagada` y `asignada`, con `list_editable` para embarcacion y capitan: se
  reparte desde el listado, sin entrar a cada reserva.
- **Poner la panga sube el estado a `asignada`; quitarla lo regresa a `pagada`.** La
  transicion vive en `Reserva._derivar_estado_de_asignacion()`, llamada desde `save()` —
  no en el admin, y no en `clean()`, que solo corre cuando alguien valida.
- **El capitan no se exige.** Un viaje `asignada` sin capitan se marca "SIN CAPITAN" en
  rojo; es un riesgo aceptado a cambio de que poner la panga baste.
- Un viaje `pagada` con fecha pasada se marca "ATRASADO": se cobro y nadie lo repartio.
  Uno `pagada` con fecha futura no se marca — eso es el trabajo pendiente, no un error.
- Filtro "Cuando" con dos modos: **Manana** (cerrar el dia, que se hace la tarde
  anterior) y **Proximos 7 dias** (repartir la semana, incluye los atrasados que siguen
  en `pagada`). Sin filtro abre en la semana.
- Los permisos son propios del proxy: `manage.py setup_roles` se los da a la vendedora.

## Cancelacion y reembolso

`Reserva` tiene `motivo_cancelacion`, `cancelada_por` (FK user), `cancelada_en`,
`reembolsada`. Accion de admin "Cancelar por mal clima (reembolso completo)" en
`ReservaAdmin` marca los 4 campos de una. Mal clima es la unica causa de cancelacion
iniciada por el negocio (ver contexto-negocio.md); la otra la dispara el webhook cuando
el dia se llena mientras el cliente pagaba. Por eso el estado se llama solo "Cancelada
(reembolsada)" y el motivo real vive en `motivo_cancelacion`. No hay flujo de
cancelacion sin reembolso todavia. Auditoria de quien cambio que reserva: el boton
"History" nativo del admin de Django (no se agrego nada custom).

## Aviso de reservas nuevas en el admin

El admin es HTML renderizado en el servidor: no hay push ni reactividad. Para que la
vendedora no tenga que recargar a ciegas, el listado de `Reserva` trae un contador:

- `ReservaAdmin.reservas_nuevas_view` (`admin:bookings_reserva_nuevas`, montada en
  `get_urls()` **antes** de `super()` porque el admin termina en un catch-all
  `<path:object_id>/`). Sin `desde` devuelve la hora del servidor y `nuevas: 0`; con
  `desde` cuenta las creadas despues. Gateada con `has_view_permission` + `admin_view`.
- Cuenta solo las que ya ocupan cupo: cada checkout abandonado deja una fila
  `pendiente_pago` y avisar de esas volveria el contador ruido. Para incluirlas, quitar
  el filtro `estado__in` de la vista.
- `static/bookings/reservas-nuevas.js` (cargado via `ReservaAdmin.Media`) consulta cada
  30 s y pinta un boton flotante. **Nunca recarga sola** — la vendedora puede estar a
  media asignacion de capitan. El ancla `desde` no se mueve, asi el contador sube hasta
  que ella recarga.
- Si agregas otra carpeta `static/` a una app, reinicia el server:
  `AppDirectoriesFinder` arma la lista de carpetas al arrancar y una creada despues da 404.

## Checkouts abandonados (recuperacion)

`CheckoutAbandonado` es un **proxy de `Reserva`**, no un modelo nuevo: son las mismas
filas en `pendiente_pago` (cliente lleno sus datos, le dio a pagar y no termino), vistas
con otro filtro. Si despues paga, la fila cambia de estado sola y desaparece de la lista.

- Se considera abandonado a partir de `HORAS_PARA_CONSIDERAR_ABANDONADO = 2`, para no
  hablarle a alguien que sigue metiendo su tarjeta en ese momento.
- `CheckoutAbandonadoAdmin` es **solo lectura** (sin add/change/delete, ni para
  superusuario): no es una reserva todavia, lo unico que se hace es contactar al cliente
  para que termine el pago en la web.
- Columna `contacto`: enlaces a WhatsApp (con el mensaje ya redactado, incluida la fecha
  que el cliente pidio), `tel:` y `mailto:`. `telefono_marcable()` limpia el numero y le
  pone lada 52 si venia a 10 digitos; si esta incompleto muestra el texto crudo en vez de
  un enlace roto.
- Limpieza: `manage.py limpiar_checkouts_abandonados [--dias 30] [--dry-run]`. Solo borra
  `pendiente_pago`, nunca una reserva pagada. Para un cron diario en Render.
- El grupo `Vendedora` lleva `view_checkoutabandonado` (ver `setup_roles`).

## Estaticos

En local no hay que hacer nada: con `DEBUG=True` el runserver los sirve desde cada app.
En produccion los sirve whitenoise (Render no tiene nginx delante), con
`STATIC_ROOT = BASE_DIR / 'staticfiles'` y `CompressedManifestStaticFilesStorage` — este
ultimo solo en `production.py`, porque exige haber corrido `collectstatic` y en local
dejaria el admin sin estilos. Build de Render:

```
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

## Otras reglas que corren en `Reserva.clean()`

Todas viven en el modelo, no en las vistas, para que apliquen igual desde la web, el
admin y el shell:

- **Deslinde**: una reserva con `canal_origen='web'` no es valida sin `deslinde_aceptado`.
  Los 4 campos (`deslinde_aceptado`, `deslinde_nombre`, `deslinde_aceptado_en`,
  `deslinde_ip`) son readonly en el admin: son constancia legal, no datos editables.
  Las reservas por WhatsApp no lo requieren (el cliente no firma en el sistema).
- **Personas**: 1 a `servicio.capacidad_maxima` si el servicio la define (con fallback a `MAX_PERSONAS = 5` para pesca legacy), y si ya hay
  embarcacion asignada tampoco puede exceder su `capacidad_maxima`.
- **Cambio de fecha**: minimo `HORAS_MINIMAS_CAMBIO_FECHA = 48` de anticipacion sobre la
  salida original. `from_db()` guarda la salida original en `_salida_original` para poder
  compararla. No aplica a canceladas (mal clima no avisa con 48 horas) ni a reservas que
  todavia no ocupan cupo.

## Transporte como servicio

Con el hito SP1 de transporte multi-empresa, los traslados dejan de ser un extra ad-hoc y pasan a ser un servicio formal de catálogo (`TipoServicio.TRANSPORTE`):

- **`fleet.TransporteTarifa`**: catálogo de precios escalonado por ruta y capacidad (`tipo_traslado`, `zona`, `personas_min`, `personas_max`, `precio` en MXN y `precio_usd`). Tabla protegida por política RLS `tenancy_alcance` bajo `empresa_id`. Admin administrable únicamente por jefes (permisos en `setup_roles`).
- **Estrategia de precio `PorRuta`** (`apps/payments/strategies/por_ruta.py`): resuelve el monto mediante `apps.fleet.tarifa_transporte.resolver_tarifa_transporte(empresa, demanda)` según `tipo_traslado`, `zona` y `numero_personas`. La cotización ocurre siempre en el servidor; `CrearPagoView` congela el `precio_calculado` en `DetalleTransporte`.
- **`bookings.DetalleTransporte`**: detalle operativo asociado `OneToOne` a `Reserva`. Guarda `tipo_traslado`, `punto_encuentro` (FK a `PuntoEncuentro`), `direccion_personalizada`, `zona`, `fecha_regreso` (para `redondo_aeropuerto`), `numero_personas` y `precio_calculado`. Su política RLS de Postgres se aplica vía FK referida a `reserva.empresa_id` y está verificada en el guardarraíl de `apps/tenancy/tests_rls.py`. Visible como `DetalleTransporteInline` en `ReservaAdmin`. La `Agenda` operativa de pangas filtra y omite traslados.
- **Ventana horaria y capacidad por Servicio**: `Servicio.hora_apertura` y `Servicio.hora_cierre` permiten ventanas horarias por servicio (pesca 5:00–7:00am, transporte sin ventana fija). `Servicio.capacidad_maxima` fija el tope de personas (ej. 14 para transporte).
- **Ruta pública `GET /api/<empresa_slug>/traslados/`**: (`apps/fleet/views.py::TrasladosView`), throttled, entrega el catálogo (`servicio`, `tarifas`, `puntos_encuentro`, `publishable_key`) bajo el alcance RLS de la empresa proveedora de transporte.

## Roles: Jefes vs Vendedora

- **Jefes** = cuentas `is_staff=True`, `is_superuser=False`, asociadas al grupo Django `Jefe`
  y con `MembresiaEmpresa(rol=JEFE)`. Ven y operan su propia Empresa, incluyendo la configuracion
  de catalogo/tarifas y el panel de finanzas (`/admin/finanzas/`).
- **Vendedora** = cuentas `is_staff=True`, `is_superuser=False`, agregadas al grupo Django `Vendedora`
  y con `MembresiaEmpresa(rol=VENDEDORA)`. Permisos del grupo: `Reserva` (add/change/view, sin delete —
  se cancela, no se borra), `CupoDiario` (add/change/view), `Embarcacion`/`Capitan` (view only),
  `Vendedora` (view only, para consultar su codigo de link). El catálogo financiero
  de `fleet.Servicio` queda reservado a jefes y operadores.
- **Operador de plataforma** = cuenta en grupo Django `OperadorPlataforma`, sin `MembresiaEmpresa`.
  Acceso global multi-tenant (Sedes, Empresas, Membresias y finanzas consolidadas).
- **Alta de vendedoras**: accion unificada "Dar de alta vendedora" en `/admin/auth/user/` (un jefe la ve
  para su propia Empresa; el operador de plataforma elige la Empresa). Crea el `User`, lo agrega al grupo
  `Vendedora`, su `MembresiaEmpresa(rol=VENDEDORA)` y su `bookings.Vendedora` en una sola transaccion atomica
  — reemplaza el flujo manual de tres pasos sueltos de antes de la expansion multi-sede.

## Gotchas

- `bookings.Reserva.hora` ya no tiene `validar_ventana_salida` como validador de campo fijo. La ventana horaria se valida en `Reserva.clean()` vía `_validar_ventana_horaria()` gateado por `self.servicio.ventana_horaria()`; servicios como transporte no restringen a 5:00–7:00am. El helper `validar_ventana_salida` se conserva como helper utilitario.
- `embarcacion`/`capitan` en `Reserva` son nullable a proposito: quedan vacios hasta que la
  vendedora asigna manualmente.
- **Reactivación manual CANCELADA -> PAGADA**: si un admin cambia a mano el estado de una reserva de `CANCELADA` a `PAGADA`, `Reserva.save()` reactiva sus `ReservaOcupacion` (`ocupa_cupo=True`) sin re-validar cupo contra otras reservas que se hayan creado mientras estuvo cancelada. Es una deuda técnica conocida; no reactivar sin verificar disponibilidad manualmente.
- **Paquetes turísticos**: el paquete es un bundle cerrado; el cliente no puede retirar servicios. En un paquete de una empresa, `precio_paquete_total` suma las personalizaciones al precio ancla y, al confirmar el pago, se reserva cupo para sus componentes y se generan sus `ReservaPaqueteComponente`. Un paquete de dos empresas usa una `Orden` y reparte el precio y los extras por empresa.

## Checkout unificado de paquetes

Contrato y reglas de producto: [spec de checkout unificado](../docs/superpowers/specs/2026-09-21-checkout-unificado-design.md).

- **Anticipo**: un servicio individual usa `Servicio.permite_anticipo` y su
  `porcentaje_anticipo` (1–99). Un paquete de una empresa usa los campos del
  `Paquete` e ignora el anticipo de sus servicios. Un paquete de dos empresas
  siempre exige pago completo (`Paquete.anticipo_disponible=False`). El endpoint
  `crear-pago` de una reserva responde 400 si se solicita `forma_pago=anticipo`
  cuando no aplica; las órdenes se crean con `forma_pago=completo`. Para indicar
  pago completo se usa `permite_anticipo=False`, no `porcentaje_anticipo=100`.
- **Configuración**: cada `PaqueteServicio` fija `dia_estancia` (día 1 = inicio),
  `noches` solo para hospedaje y `personas_incluidas` para ese servicio. El cliente
  puede usar menos lugares sin reducir el precio ancla. Las reglas de
  `apps/fleet/paquete_reglas.py` se ejecutan antes de vender: como máximo un
  hospedaje, que empieza en día 1 y tiene noches positivas; los demás servicios
  no llevan noches; las actividades comparten día y caen antes de la salida del
  hospedaje; sin hospedaje todos los componentes van en día 1; las personas
  incluidas respetan la capacidad del servicio. `Paquete.validar_configuracion()`
  valida además el precio contra la peor tarifa de transporte aplicable en las
  monedas configuradas; el cobro de una orden protege también el reparto.
- **Fechas**: el cliente elige el inicio. Cada componente ocurre en
  `inicio + (dia_estancia - 1)` días y el hospedaje sale en `inicio + noches`.
  En un paquete de una empresa, `Reserva.fecha` es el día de la actividad operativa;
  `Reserva.inicio_paquete` guarda el inicio elegido y `fecha_inicio_paquete` lo
  devuelve (o usa `fecha` para reservas anteriores). En uno de dos empresas, cada
  `Reserva` lleva la fecha de su componente.
- **Personas**: la reserva de un paquete de una empresa guarda
  `personas_por_servicio` como `{"<servicio_id>": n}`; `Reserva.personas_de(servicio_id)`
  obtiene ese valor y usa `numero_personas` como respaldo. Al reservar, las
  actividades de una empresa deben llevar el mismo número de personas. En una
  orden, cada componente tiene su propio `numero_personas`.
- **Extras**: `apps/payments/extras.py` es la única implementación de cotización y
  congelado de personalizaciones. En una orden, cada empresa cobra los extras de
  sus servicios; se congelan después de que Stripe acepta los PaymentIntents.
- **API**: `POST /api/<empresa>/reservas/` recibe `fecha` de inicio y
  `personas_por_servicio` para un paquete de una empresa; rechaza `fecha_salida`.
  `POST /api/<sede>/ordenes/` recibe `fecha` de inicio y `componentes[]` con
  `servicio`, `numero_personas` y `personalizaciones` (`id`, `cantidad` o `respuesta`
  según el extra). Rechaza `fecha` dentro de un componente y `fecha_regreso` cuando
  el paquete tiene hospedaje. Una orden admite como máximo un servicio por empresa.
- **USD en órdenes**: la moneda se elige para toda la orden y se usan los precios
  USD cargados en el paquete, las tarifas de transporte y los extras, sin conversión.
  `crear-pago` responde 400 si falta el precio del paquete o una tarifa de transporte
  en esa moneda; un extra sin precio responde 503.

## Órdenes cruza-empresa

SP2 implementa ADR-005: `bookings.Orden` agrupa una `Reserva` por empresa; v1 admite
un servicio base de la líder y un traslado de otra empresa de la misma sede.
Solo `forma_pago=completo`, sin anticipo. El precio fijo sigue almacenado en
`Paquete.precio_ancla` / `precio_ancla_usd`; no existe un campo `precio_paquete`.

- Modelo B: `apps/payments/ordenes.py` crea un PaymentIntent de tarjeta con captura
  manual por cuenta Stripe. Se autorizan todos antes de capturarlos. El reparto
  vive exclusivamente en `pricing.monto_por_empresa`: transporte recibe su tarifa
  y la líder recibe el residuo. No se usa Stripe Connect.
- Las escrituras Stripe (`create`, `update`, `capture`, `cancel`, `refunds.create`)
  llevan claves idempotentes. Las consultas `retrieve` no modifican dinero.
- `ordenes.revertir_orden` centraliza void/refund de los componentes, incluido el
  fallo de cupo del webhook. Guarda la cancelación mediante `Reserva.save()` para
  liberar ocupaciones y componentes; no sustituirlo por `QuerySet.update()`.
- El navegador solicita la captura, pero no marca la orden pagada.
  `services.aplicar_pago_exitoso` aplica cada `payment_intent.succeeded` y cierra
  la orden cuando todos sus componentes están pagados/asignados. El cierre usa
  locks y la misma función sirve al webhook y a la conciliación.
- `Orden` tiene RLS por **sede**, excepción documentada en el guardarraíl de
  `tenancy/tests_rls.py`. Sus reservas siguen aisladas por empresa. Para inspeccionar
  componentes se usa `bookings.orden_lectura.reservas_de_orden`, que invoca la
  función PostgreSQL `estado_reservas_de_orden` de lectura acotada por ID.
  `0044` elimina el antiguo bypass de lectura basado en `current_query()`;
  `WITH CHECK` conserva la excepción de inserción pública para sedes existentes.
- `conciliar_pagos` es orden-aware: si todos los intents están `succeeded`, llama
  al mismo servicio del webhook; si la autorización incompleta venció (24 horas)
  o hay un intent cancelado, revierte la orden. Ejecutarlo cada hora.
  `revisar_ordenes --horas 2` diagnostica estados intermedios sin modificar datos.
- Una notificación combinada por orden: email con componentes y WhatsApp según
  empresa; `notificada_en` evita repetirla. Un único deslinde se copia a las reservas.
- Cada empresa necesita su webhook en `/api/<empresa_slug>/stripe/webhook/` y su
  propio `Empresa.stripe_webhook_secret`. Configurar las credenciales por empresa.
- `seed_local_demo` crea `pesca-traslado` (Sal y Sol + Transportes La Paz), con
  precio inicial demo 7500 MXN / 450 USD. Es solo local y no reemplaza credenciales
  existentes. No ejecutar el seed demo en producción.
- **`Orden.estado=CAPTURADA` es terminal.** `revertir_orden` refresca la orden bajo
  el scope de la líder y rechaza con `OrdenCerradaError` antes de tocar Stripe si ya
  está capturada — nunca reembolsa y luego falla la transición de estado. El admin
  de `OrdenAdmin` atrapa ese error y avisa con `message_user`, sin tumbar la acción
  para el resto del queryset.
- **El correo combinado de `notificar_orden_pagada` puede llegar por el webhook de
  cualquier empresa del paquete**, no solo la líder — la orden en memoria puede no
  traer `paquete` cacheado, o traerlo bajo RLS de la empresa equivocada. El servicio
  relee `orden.paquete` bajo el scope de `empresa_lider` antes de armar el correo.
