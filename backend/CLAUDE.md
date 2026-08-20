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
- `fleet.Tarifa`: singleton (`pk` forzado a 1 en `save()`, que ignora `force_insert`
  para que un segundo `create()` actualice en vez de reventar). Dos precios de lista
  independientes: `precio` (MXN) y `precio_usd` (nullable, sin el la web solo ofrece
  pesos). No hay tipo de cambio en ningun lado, el negocio fija cada precio a mano.
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

- `GET /api/tarifa/` — `{precio, precio_usd, amenidades}` (`apps/fleet`). Las amenidades
  vienen de aqui a proposito: la web no tiene ninguna cifra hardcodeada. 503 si no hay
  `Tarifa` creada.
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
  (tarifa en la moneda de la reserva + amenidades de `apps/payments/pricing.py` +
  100%/30% anticipo) se calcula siempre en el servidor, nunca se confia el total que
  manda el cliente (`apps/payments`). 503 si la moneda pedida no tiene precio.
- `POST /api/stripe/webhook/` — en `payment_intent.succeeded` marca la reserva
  `pagada`, corre `full_clean()` (motor de cupo) y dispara las notificaciones. Si el
  cupo se lleno mientras el cliente pagaba, reembolsa via `stripe.Refund` y deja la
  reserva `cancelada` + `reembolsada` con el motivo real, para que la vendedora la vea.

### Garantias del cobro (apps/payments)

Lo mas delicado del sistema. Reglas que **no** hay que romper:

- Todo el dinero se calcula en `apps/payments/pricing.py`. El cliente manda que
  amenidades y si paga completo o anticipo; nunca un total.
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
`config/urls.py` **antes** de `admin/`, que si no se traga la ruta). Solo
superusuarios: la vista corta con `is_superuser`, igual de cerrada que `fleet.Tarifa`.
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
  (ver `fleet.Tarifa`); sumar MXN con USD daria una cifra sin significado.
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
- **Personas**: 1 a `MAX_PERSONAS = 5` (la embarcacion mas grande), y si ya hay
  embarcacion asignada tampoco puede exceder su `capacidad_maxima`. El mismo tope vive
  en `frontend/src/lib/dates.ts` (`MAX_PEOPLE`) y en la copia de las dos dictionaries:
  se mueven juntos o el cliente llena todo el checkout para toparse con un 400 al final.
- **Cambio de fecha**: minimo `HORAS_MINIMAS_CAMBIO_FECHA = 48` de anticipacion sobre la
  salida original. `from_db()` guarda la salida original en `_salida_original` para poder
  compararla. No aplica a canceladas (mal clima no avisa con 48 horas) ni a reservas que
  todavia no ocupan cupo.

## Roles: Jefes vs Vendedora

- **Jefes** = cuentas Django con `is_superuser=True`. Ven/editan todo, sin restriccion
  (bypassa el sistema de permisos). No usan un Group.
- **Vendedora** = cuentas `is_staff=True`, `is_superuser=False`, agregadas al grupo
  Django `Vendedora`. Correr `python manage.py setup_roles` (idempotente) para
  crear/sincronizar los permisos del grupo: `Reserva` (add/change/view, sin delete —
  se cancela, no se borra), `CupoDiario` (add/change/view), `Embarcacion`/`Capitan`
  (view only), `Vendedora` (view only, para consultar su codigo de link).
  **`fleet.Tarifa` deliberadamente sin permisos** — informacion financiera, asi el
  modulo ni aparece en su admin. El panel de finanzas (`/admin/finanzas/`) va por la
  misma linea: corta con `request.user.is_superuser`, nunca con solo "es staff".
- Crear cuentas de vendedora: `createsuperuser` es solo para jefes. Para vendedora,
  crear un `User` normal (`is_staff=True`) desde el admin o shell, agregarlo al grupo
  `Vendedora` y darle de alta su fila en `bookings.Vendedora` con su codigo de link.

## Gotchas

- `bookings.Reserva.hora` valida ventana 5:00–7:00am (`validar_ventana_salida` en `models.py`).
- `embarcacion`/`capitan` en `Reserva` son nullable a proposito: quedan vacios hasta que la
  vendedora asigna manualmente.
