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
  **El punto de encuentro de los correos** (confirmacion, asignacion de panga/capitan y paquetes)
  sale de `Servicio.punto_salida` (el «Sales de» de la ficha del servicio, el mismo dato que ve el
  cliente en el sitio), nunca de texto fijo en el codigo. Vacio = el correo dice
  `SIN_PUNTO_DE_ENCUENTRO` («Te lo confirmamos por WhatsApp») y un hospedaje no lleva renglon; la
  lista de Servicios del admin marca «FALTA» en rojo los servicios de mar sin dato.
- `fleet.Servicio`: pesca usa el servicio `pesca-deportiva` de cada Empresa y la
  estrategia `por_grupo`. `precio_base` y `precio_persona_extra` se guardan en MXN;
  el USD se deriva del tipo de cambio de la sede y cada importe se redondea hacia
  arriba al dólar entero.
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

- `autorizado` y `autorización` son términos internos del código y el admin. En
  textos de cara al cliente (motivos del JSON de API, correo y WhatsApp) usar
  `retenido` y `retención`. Los valores técnicos de estado son parte del contrato
  del API; el frontend debe mostrar el vocabulario de cliente.
- El servidor calcula el precio base y el reparto en `apps/payments/pricing.py`, y
  cotiza las personalizaciones en `apps/payments/extras.py`. El cliente manda su
  selección y, cuando aplica, si paga completo o anticipo; nunca un total.
- **Ordenes cruza-empresa: el `checkout_id` es la prueba de posesion.** `crear-pago`, `confirmar-captura`, `cancelar` y
  la lectura por id (`GET .../ordenes/<id>/?checkout_id=`) lo exigen (403 si falta o no coincide); sin eso, recorrer
  ids enteros devolvia el `checkout_id` y los `client_secret` de otras ordenes. `GET .../ordenes/?checkout_id=` sigue
  siendo la lectura sin id. El comando `cifrar_llaves_stripe` corre sin chequeos de sistema a proposito.
- `crear-pago` es idempotente: reusa el intent de la reserva si sigue sin cobrar, lo
  ajusta con `PaymentIntent.modify` si cambiaron las amenidades, y manda
  `idempotency_key` para el doble clic. Si el intent ya esta en `succeeded`/`processing`
  responde 409 — jamas se crea un intent nuevo encima de uno que ya esta cobrando.
- **`crear-pago` aparta el cupo (apartado temporal)**, solo si `APARTADO_MINUTOS > 0` y el
  servicio/paquete tiene cupo fisico (`por_recurso_dia` o `por_noche`; no `bajo_demanda` ni
  ordenes cruza-empresa). Va en tres bloques, cada uno en su propio `scope.con_empresa` para que
  el candado se libere ANTES de hablar con Stripe: **A** (validaciones, monto, lectura del intent
  guardado; si ya esta `processing`/`succeeded` responde `pago_en_curso` sin tocar el apartado y
  calcula `tiene_cupo_fisico` AQUI, dentro del alcance: fuera de el RLS vacia la consulta de los
  componentes del paquete y el apartado se omitiria en silencio), **B** (transaccion corta:
  `select_for_update` de la fila de la reserva primero, luego los candados del cupo en el mismo
  orden que `reservar_cupo_al_confirmar`, `lock_timeout` de 5 s, un reintento si hay deadlock
  `40P01`; evalua el cupo excluyendo la propia reserva y escribe `apartado_hasta` +
  `apartado_demanda`; commit) y **C** (Stripe y escrituras finales). Contrato de errores, cuerpo
  plano `{"detail", "codigo", ...}`: 409 `sin_cupo` (`motivo` = `lleno`/`sin_panga`/`sin_lugar`,
  `proxima_disponible` = fecha solo para servicio suelto de mar; `null` en hospedaje y paquetes),
  409 `ya_no_pendiente`, 409 `pago_en_curso`, 403 `checkout_invalido`, 503 `reintentar` (candado
  no obtenido a tiempo). Si Stripe falla (502), el bloque C libera SOLO un apartado que esta
  llamada creo y con `UPDATE ... WHERE apartado_hasta = <valor que escribio>`: nunca borra uno que
  otra llamada renovo. Editar la reserva por `POST /reservas/` (upsert por `checkout_id`) borra el
  apartado si cambia algo relevante al cupo; los campos `apartado_*` no son escribibles por la API.
- **Avisos cuando aun asi se reembolsa por falta de cupo**: `_cancelar_sin_cupo(..., causa)` recibe
  `'cupo'` si la excepcion es `SinCupoError` o una `ValidationError` con codigo `sin_cupo`
  (recorriendo `error_dict`/`error_list` anidados), `'otra'` en cualquier otro caso. Cliente: correo
  (Resend) solo con causa `cupo`; aviso interno a `Empresa.correos_aviso` con cualquier causa;
  WhatsApp apagado hasta que exista `WHATSAPP_TEMPLATE_REEMBOLSO_SIN_CUPO`. Un reembolso que
  falla (`FALLO_REEMBOLSO`) genera una alerta urgente una sola vez por reserva, sellada con
  `Reserva.objects.filter(pk=..., alerta_reembolso_fallido_en__isnull=True).update(...)` (nunca
  `save()`: el objeto en memoria ya tiene `estado=PAGADA` sin persistir). **Todo `raise` de falla de
  cupo lleva `code='sin_cupo'`**; con mensaje en forma de diccionario el codigo va en el error
  interior (`ValidationError({'fecha': ValidationError(msg, code='sin_cupo')})`) porque Django
  ignora `code=` cuando el mensaje es un diccionario.
- **Codigos promocionales**: pertenecen a UNA empresa (`(codigo, empresa)` es unico; el mismo texto
  puede existir en otra) y solo aplican en el checkout de esa empresa. No aplican a un paquete
  cruza-empresa (`Orden`): ni el backend ni el checkout los leen ahi. La respuesta publica es
  generica a proposito; el motivo (`motivo_codigo_no_aplica`: desactivado, aun no empieza, vencido,
  bajo el minimo, agotado, agotado por cliente) es la unica regla de validez y la ve el admin en la
  columna «Hoy» de la lista de codigos (con la empresa, para el operador). Los limites se dejan
  **vacios** para no tener limite: un `0` en usos maximos se leia como «cero usos» (codigo agotado
  desde el inicio) y `CodigoPromocional.clean()` ya lo rechaza.
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
- El webhook tambien escucha `charge.refunded` (`services.aplicar_reembolso`). Un reembolso
  **total** hecho desde el panel de Stripe deja la reserva como «Cancelar por mal clima» +
  reembolso (estado `cancelada`, `reembolsada`, cupo/panga/capitan/habitacion liberados, sin
  correo de asignacion; `cancelada_por` queda vacio y el motivo dice que vino de Stripe). Uno
  **parcial** solo anota `monto_reembolsado`: no cancela ni marca `reembolsada`, y la columna
  Cobro lo muestra («· devuelto X»). `amount_refunded` es acumulado: un evento que no sube lo ya
  anotado (repetido o atrasado) no cambia nada; uno que lo sube actualiza `reembolsada_en`. Una
  `completada` reembolsada por completo conserva su estado; un reembolso que llega antes que
  el pago (reserva aun `pendiente_pago`) se ignora y queda en el log. Tambien escucha `charge.dispute.created` / `.closed` /
  `.funds_reinstated` (levantan y bajan `en_disputa`). Una disputa **no** cambia el
  estado de la reserva: que hacer con un viaje en contracargo lo decide una persona. En el
  admin se ve como «⚠ En disputa» en la columna Cobro (lista y resumen de la reserva), el campo
  esta junto al cobro y el filtro «en disputa» esta entre los filtros a la vista.
  Los seis eventos que el webhook escucha (los que hay que suscribir en Stripe, por empresa, en
  `/api/<slug>/stripe/webhook/`): `payment_intent.succeeded`,
  `payment_intent.amount_capturable_updated`, `charge.refunded`, `charge.dispute.created`,
  `charge.dispute.closed`, `charge.dispute.funds_reinstated` (`docs/deploy/GO-LIVE.md`).
  **Disputa perdida**: `charge.dispute.closed` con `status=lost` anota `contracargo_perdido` y
  `contracargo_perdido_en` (idempotente; `won` o `funds_reinstated` la borran). Finanzas lo cuenta como
  salida aparte, «Contracargos», y lo resta de «En la cuenta» y del neto; el admin lo marca en la
  columna Cobro. Tampoco cambia el estado de la reserva.
- **Efectivo**: `monto_efectivo` guarda lo que se recibio el dia del viaje — el 70%
  restante del anticipo y lo que el agente haya cotizado aparte (bebidas, transporte),
  por eso puede superar el saldo del tour y no se valida contra el. `saldo_pendiente`
  ya lo descuenta. La accion de admin "Registrar liquidacion en efectivo" rellena el
  saldo exacto y sella quien y cuando; para un monto distinto se edita a mano. Pide
  confirmacion, solo toca reservas `pagada`/`asignada` no reembolsadas con saldo > 0 y
  recalcula el saldo con la fila bloqueada (`apps/bookings/cobros.py`), asi que repetir el
  clic o dos clics a la vez no cobran de mas. Tambien sale como boton «Cobrar saldo en
  efectivo» en el resumen de la reserva (entra por la misma accion). Cualquier efectivo
  escrito en el formulario se sella una sola vez (`save_model`): corregir el monto no mueve
  la fecha del primer registro; quitarlo la borra.
- **Transferencia**: `monto_transferencia` guarda una entrada independiente de Stripe
  y de caja. Descuenta `saldo_pendiente`; `monto_pagado` sigue siendo solo lo cobrado
  por Stripe para verificar montos y reembolsos de tarjeta. El admin sella fecha y usuario
  **una sola vez** (igual que el efectivo): corregir o completar el importe no mueve el dinero
  ya registrado a la fecha de hoy; quitarlo borra el sello. Limite conocido: no hay libro de
  movimientos, asi que un importe completado despues cae entero en la fecha del primer registro.
- **Una panga hace una sola salida por dia, y un capitan tambien.** Se valida en
  `Reserva._validar_una_salida_por_dia()`, llamada desde `clean()`, asi que aplica igual
  desde la agenda, desde el admin de Reservas y desde el shell. En un paquete con varios
  dias de mar se revisa cada `ReservaSalida`; la panga y el capitan asignados en la
  reserva cubren toda la estancia. Cuentan los estados de
  `ESTADOS_QUE_OCUPAN_CUPO`: una cancelada suelta su panga. Las salidas son de 5 a 7am y
  el viaje dura de 6 a 7 horas — escalonar no existe. (Esta nota decia lo contrario hasta
  agosto de 2026, cuando el negocio aclaro la regla.)
  Esta validación consulta sin lock: dos operadores asignando al mismo tiempo la misma
  panga podrían pasar ambos, igual que antes de las salidas multidía. Una reserva en
  `pendiente_pago` con panga asignada aún no tiene `ReservaSalida`, así que la validación
  solo revisa `Reserva.fecha`. Ambas limitaciones se aceptan por ahora.
- **Red de seguridad**: `manage.py conciliar_pagos [--dias 7] [--dry-run]` busca reservas
  `pendiente_pago` que ya tengan PaymentIntent, le pregunta a Stripe como quedo y aplica
  lo mismo que el webhook. Existe porque una entrega de webhook puede perderse para
  siempre (backend caido, secret mal puesto, Stripe se rinde tras sus reintentos) y
  entonces hay un cliente que pago y no tiene reserva. Correrlo por cron cada hora.
  Es idempotente: en la segunda vuelta esas reservas ya no estan pendientes.

**IP del cliente y limite de peticiones (produccion).** `apps/bookings/ip_cliente.py` saca la IP real del cliente de
`X-Forwarded-For` recorriendolo de derecha a izquierda y saltando las direcciones de NUESTROS proxies (rangos de
Cloudflare y redes internas); la primera que no es de proxy es la que se conecto. No cuenta saltos: en produccion la IP
del deslinde de una reserva de prueba salio de un nodo de Cloudflare (172.x) contando "1 salto". La usan el limite de
peticiones (`LimitePorIpDelCliente`, el throttle por defecto), el deslinde, Turnstile y el bloqueo por intentos del
admin (`AXES_CLIENT_IP_CALLABLE`). `TRUSTED_PROXY_COUNT` solo enciende o apaga (0 = no se le cree al header); si
Cloudflare publica un rango nuevo, se agrega en `TRUSTED_PROXY_EXTRA_RANGES` (CSV). Los contadores del limite van en un
cache en archivos (`DJANGO_CACHE_DIR`, `/tmp/django-cache`, hasta 10,000 entradas) que comparten los 3 procesos de
gunicorn; con el cache por defecto cada proceso tenia el suyo y el limite real era el triple.

Llaves de Stripe (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`)
se leen de variables de entorno, vacias por defecto en local — `crear-pago` responde
503 si no estan configuradas (el frontend lo maneja mostrando `checkout.paymentUnavailable`).
Igual con las notificaciones: `RESEND_API_KEY`, `RESEND_FROM`, `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TEMPLATE` (default `reserva_confirmada`),
`WHATSAPP_TEMPLATE_LANG` (default `es_MX`).

- **IVA** (`settings.IVA_TASA`, env `IVA_TASA`, default 0.16; 0 al correr pruebas, que lo fijan con
  `override_settings`). Los precios del catalogo van SIN IVA y se suma al final: `pricing.con_iva(neto)`
  devuelve `(iva, total)` sobre el precio ya con descuento; Stripe cobra el total y el anticipo es el % de
  ese total. `Reserva.precio_total` es el total CON IVA; `iva_monto` e `iva_tasa` guardan el desglose
  (vacios en reservas anteriores y en las que captura la vendedora a mano, que no llevan IVA automatico).
  Subtotal sin IVA = `precio_total - iva_monto + descuento_aplicado`. En una orden cruza-empresa el IVA se
  calcula por empresa sobre su parte (cada cuenta de Stripe cobra su neto + su IVA). Espejo en el
  frontend: `src/lib/iva.ts` (`NEXT_PUBLIC_IVA_TASA`); paridad en `shared/precios_paridad.json`.

## Panel de finanzas (apps/finance)

Pantalla unica de dinero, en `/admin/finanzas/` (`apps/finance/views.py`, montada en
`config/urls.py` **antes** de `admin/`, que si no se traga la ruta).
Corta con `scope.es_operador_plataforma(request.user)` (ve todas las Empresas) o
`scope.empresa_actual(request)` no vacío (ve la suya) — ya no con `is_superuser` (ver expansión multi-sede).
Muestra entradas (tarjeta / efectivo / transferencia), salidas (reembolsos), balance de hoy, del mes y
del año, historico por dia con navegacion de meses, y los tres saldos teoricos contra
los que se cuadra: lo que deberia haber en la cuenta de Stripe, en caja y en el banco.

**Todo sale de `Reserva`, salvo que el dinero llegue en dos momentos.** Tarjeta y contracargo ocurren de
una vez y se agregan por su columna y su fecha. Efectivo, transferencia y reembolsos pueden moverse en
dos o mas momentos (una vendedora anota $500 el lunes y completa $700 el viernes; un segundo reembolso
parcial), y la reserva solo guarda UN total y la fecha del primer registro: ese total caia entero en la
primera fecha. Por eso esos tres conceptos tienen `bookings.MovimientoDinero`: una fila por cada
cambio de monto, con SU fecha. Reglas:

- `Reserva.save()` escribe las filas solo (`_registrar_movimientos_de_dinero`), comparando contra la
  foto que `from_db` tomo al cargar la reserva. Cubre el formulario del admin, el cobro del saldo, el
  webhook de reembolso y las acciones del admin; no hay que acordarse de llamarla.
- Con filas ya escritas, la diferencia es el monto actual menos la SUMA de sus filas (no una foto del
  objeto): `refresh_from_db`, dos personas editando o un campo fuera de `update_fields` no duplican ni
  pierden filas. Un monto sin fecha de primer registro queda en una fila de `fecha` nula (no cuenta, pero
  la suma sigue igual a la columna) y se fecha cuando llega el sello.
- Una correccion hacia abajo es una fila **negativa** con la fecha de la correccion: no reescribe el
  pasado. El total de la reserva y la suma de sus filas coinciden.
- Finanzas suma las filas de esos tres conceptos y, para las reservas que aun no tienen filas de un
  concepto (anteriores a la tabla), sigue leyendo su columna y su fecha de primer registro. La primera
  vez que cambia un monto de una reserva anterior se escribe su fila base con la fecha de siempre, mas
  la del cambio. No hay migracion de datos.
- Un primer registro **sin fecha** no cuenta (no tiene dia); el admin siempre la pone.
- La tabla lleva RLS por empresa (`0065`). Quien movio el dinero va en `registrado_por`.

| Movimiento | Monto | Fecha | Quien la sella |
|---|---|---|---|
| Entrada tarjeta | `monto_pagado` | `pagada_en` | webhook de Stripe |
| Entrada efectivo | `monto_efectivo` | `efectivo_cobrado_en` | la vendedora |
| Entrada transferencia | `monto_transferencia` | `transferencia_registrada_en` | la vendedora |
| Salida (reembolso) | `monto_reembolsado` | `reembolsada_en` | webhook de Stripe |
| Salida (contracargo perdido) | `contracargo_perdido` | `contracargo_perdido_en` | webhook de Stripe |

Reglas que no hay que romper:

- **Cada moneda por separado, nunca sumadas.** El tipo de cambio de la sede sirve
  para cotizar USD; sumar MXN con USD daria una cifra sin significado.
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
- Los reembolsos de reservas pagadas por transferencia se hacen fuera del sistema;
  no hay movimiento de salida bancaria ni se descuentan del saldo teorico del banco.
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
`asignada`, `completada`) — `pendiente_pago` no bloquea a otros clientes, **salvo por el apartado
temporal** (siguiente parrafo). `ESTADOS_QUE_OCUPAN_CUPO` NO cambia: lo consumen la Agenda, el
panorama, la restriccion EXCLUDE y la regla de 48 h. Cualquier flujo nuevo que cree/edite
una `Reserva` (API de pago, panel vendedora) debe llamar `instance.full_clean()` antes de `save()`
para que este motor corra — no duplicar la logica en otro lado.

**Apartado temporal de cupo (checkout web).** `Reserva.apartado_hasta` (vencimiento) y
`apartado_demanda` (un "retrato" JSON `{"v":1,"salidas":[{fecha,personas,servicio_id}],
"habitaciones":[{recurso_id,inicio,fin,servicio_id}]}` de lo que esa reserva ocuparia) hacen que
una reserva `pendiente_pago` con apartado vigente cuente contra el cupo, y solo dentro del adaptador
del motor (`bookings/cupo/adaptador.py` con `bookings/cupo/apartado.py`): pesca por fecha/servicio y
habitaciones por rango, excluyendo siempre la propia reserva (`excluir_pk`). Vence solo (comparar
con la hora, sin tarea que limpie). `APARTADO_MINUTOS` (variable de entorno, 0 = apagado, default 0;
15 en produccion) lo gobierna: con 0 el motor ignora los apartados aunque existan. Los endpoints
publicos `/api/cupo/` y `/api/cupo/rango/` aceptan la cabecera `X-Checkout-Id` para no contar el
apartado del propio cliente. `crear-pago` lo toma (ver "Garantias del cobro"); el webhook lo limpia
al pagar o cancelar. Tope: el apartado no se renueva pasados `APARTADO_TOPE_MINUTOS` (45) desde que se creo la
reserva, y una misma persona (correo o telefono) no sostiene mas de `APARTADO_MAX_POR_CONTACTO` (3)
apartados vigentes; en ambos casos el pago sigue, solo que sin guardar el lugar (el cupo se revisa de
nuevo al cobrar). Fuera de alcance: paquetes cruza-empresa (Orden).

Una actividad repetida dentro de un paquete ocupa cupo en cada fecha de `ReservaSalida`.
El motor cuenta esas salidas junto con las reservas sueltas y excluye `Reserva.fecha`
cuando la reserva ya tiene salidas, para evitar duplicar el primer dia.

**Que cuenta contra la capacidad de pangas.** Solo lo que sale al mar: servicio suelto
`por_recurso_dia` (pesca, paseo, safari: comparten la flota de la empresa), reserva sin servicio
ni paquete (pesca anterior al catalogo) y paquete con algun componente `por_recurso_dia` (por su
`Reserva.fecha`, o por cada `ReservaSalida` si tiene salidas). Hospedaje (`por_noche`), traslados y
tours `bajo_demanda` y paquetes sin actividad de mar **no** gastan viaje del tope diario ni panga en
`caben(...)`. La regla vive en una sola funcion, `cupo.solo_demanda_de_mar(queryset)`, usada por
`obtener_contexto_cupo`/`_rango`, `/api/cupo/`, `revisar_cupo`, el panorama y la Agenda
(`sin_lo_que_no_se_reparte`, `Agenda.por_repartir`): no escribir otro filtro por su lado. El apartado
temporal ya solo guarda demanda de mar (sus retratos).

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
  2. `por_noche` (hospedaje): multi-día sobre rango `[fecha, fecha_fin_servicio)`. Se crean registros `ReservaOcupacion` por habitación/recurso asignado; `habitaciones_necesarias` calcula cuántas habitaciones libres hacen falta para el grupo. La base de datos protege contra sobreventa mediante constraint PostgreSQL `EXCLUDE USING gist` sobre `(recurso_id WITH =, daterange(fecha_inicio, fecha_fin, '[)') WITH &&) WHERE (ocupa_cupo)`. Lock de serialización: `bloquear_recurso(empresa_id, recurso_id)`.
  3. `bajo_demanda` (tours/experiencias sin límite físico estricto): no bloquea inventario previo.
- **Cambiar fechas o grupo de un hospedaje ya pagado mueve sus habitaciones** (`cupo/hospedaje_sync.py`,
  llamado desde `Reserva._guardar_reserva`): si la firma de cupo cambia (fechas, personas) en una reserva
  que ya ocupaba, `sincronizar_ocupaciones` conserva las mismas habitaciones si siguen libres en el rango
  nuevo y alcanzan, y si no las vuelve a elegir; sin lugar lanza `SinCupoError` y el admin lo muestra como
  aviso en espanol (`CupoAgotadoAlGuardar`). Antes la habitacion se quedaba bloqueada en las fechas viejas.
- **Apartado de hospedaje**: no crea filas `ReservaOcupacion` (no toca el `EXCLUDE`); el retrato
  guarda las habitaciones elegidas por `elegir_habitaciones` (misma funcion pura que usa
  `_asignar_cupo_hospedaje`, orden determinista por `pk`) y `obtener_recursos_con_ocupaciones`
  suma esos intervalos `[inicio, fin)` a cada habitacion del mismo servicio.
- **Sincronización de `ReservaOcupacion.ocupa_cupo`**:
  `Reserva.save()` propaga automáticamente `ocupa_cupo = (estado in ESTADOS_QUE_OCUPAN_CUPO)` a sus `ocupaciones` únicamente cuando la reserva cruza la frontera de ocupación (usando `_estado_original`).
- **Paquetes turísticos**:
  - Todo `Paquete` pertenece a una `sede` y a una `empresa_lider`.
  - `PaqueteServicio.clean()` permite empresas distintas dentro de la misma sede. Los paquetes cruza-empresa usan `Orden` (ver abajo); los mono-empresa conservan su flujo de reserva.
  - Al pagar la reserva de un paquete, `reservar_cupo_al_confirmar()` dentro de `aplicar_pago_exitoso` valida y crea un `ReservaPaqueteComponente(estado_cupo=OK)` por cada componente no removido, y crea las `ReservaOcupacion` correspondientes para hospedaje. Si algún componente no tiene cupo, lanza `SinCupoError`, la transacción hace rollback y se emite reembolso automático 100%.
  - Al cancelar la reserva, `Reserva.save()` sincroniza `componentes` a `LIBERADO` y libera las ocupaciones.
- **Salidas en varios días**: `PaqueteServicio.salidas` (default 1) repite una actividad en días
  seguidos desde `dia_estancia` (día 2 con 4 salidas = días 2 a 5). Solo en paquetes de una empresa
  y dentro de la estancia (`paquete_reglas`). Al confirmar el pago, `reservar_cupo_al_confirmar`
  valida cada día (locks en orden de fecha) y crea un `ReservaSalida` por día; si falta cupo en
  cualquiera, el rollback y el reembolso 100 % de siempre. El cupo cuenta las salidas por su
  fecha (`obtener_contexto_cupo`/`_rango`) y **no** cuenta por `Reserva.fecha` a una reserva con
  salidas, para no contarla dos veces. La panga y el capitán se asignan en la reserva (Agenda) y
  valen para todos sus días: la regla "una panga, una salida por día" revisa cada día de mar
  (`Reserva._fechas_de_viaje`). El hospedaje elige cuántas habitaciones hacen falta
  (`habitaciones_necesarias`) y las reasigna el inline de ocupaciones del admin.
  Al crear o reprogramar una reserva pagada desde el admin, `Reserva.save()` toma los
  candados de mar en orden de fecha, revalida el cupo y sincroniza las salidas dentro
  de la misma transacción. La validación de panga y capitán usa las fechas nuevas
  del paquete antes de que se guarden las filas.
- **Marketplace dinámico en el checkout**:
  - Rutas de API operan bajo `/api/<empresa_slug>/...`.
  - El frontend resuelve dinámicamente la empresa del producto (`paquete.empresa_lider_slug` o `servicio.empresa_slug`), de modo que `crear-pago` cobra directo en la cuenta de Stripe de dicha empresa proveedora (`pago.publishable_key`).

## Agenda operativa

`bookings.Agenda`, proxy de `Reserva` (mismo patron que `CheckoutAbandonado`). Es donde
se reparten los viajes vendidos de mar: que panga y que capitan le toca a cada uno.
**En el menu se llama «Asignar pangas»** (antes «Agenda»; su pareja es «Asignar vehiculos»,
antes «Traslados»): cambia solo el titulo y el `verbose_name` de los proxies, no las URLs ni
los codenames de permisos. El jefe que busca «que hay estos dias» va al Calendario (abajo).
No aplica a traslados (los vehículos de transporte terrestre se asignan en la pantalla «Asignar vehículos»).

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
- Dos parametros mas, que arma el Calendario: `?periodo=AAAA-MM-DD_AAAA-MM-DD` (mira ese rango
  en lugar de la ventana de la semana; roto o al reves se ignora) y `?cuando=atrasadas` (las
  `pagada` sin panga de fecha pasada; con `periodo`, solo las de ese rango). `PeriodoAgendaFilter`
  solo registra el parametro; el filtrado esta en `CuandoFilter`.
- **Llegar a cualquier fecha.** `modo_de_la_agenda(request)` es la unica respuesta a "que mira la
  tabla" (`semana` por defecto, `periodo`, `manana`, `atrasadas`, `recientes`, `busqueda`); la usan
  el filtro y la barra de fechas. La barra (en el bloque `filters` de la plantilla, fuera del
  formulario POST de la tabla) tiene flechas Anterior/Siguiente que saltan el largo del rango
  mirado (7 dias desde la vista de siempre), "Esta semana" y un formulario "Desde / Hasta"
  (`?desde=&hasta=`) que `changelist_view` convierte por redireccion en `?periodo=`.
  **El buscador sin rango mira todas las fechas** (antes se intersectaba con la semana en curso y
  no encontraba al cliente del mes siguiente); con un rango, o con `cuando=manana`, se queda dentro.
  El panorama arranca en el primer dia del rango si es futuro (`inicio_del_panorama`; un rango
  pasado o que cruza hoy lo deja en hoy) y `armar_panorama(..., hoy=)` cuenta como atrasado solo
  lo anterior a hoy, no lo anterior al inicio de la cuadricula.
- **Pantalla de asignar** (rama `feat/agenda-asignar`). Reservas es el registro de todo; la
  Agenda es solo para asignar panga:
  - Una linea de resumen arriba ("N atrasados · N sin panga · N sin capitan", o "Todo
    asignado"), de `Panorama.resumen`.
  - El panorama muestra por celda nombre y personas, y en la fila "Sin panga" cada viaje
    pendiente con nombre y grupo. "Pangas ocupadas" cuenta pangas, no personas.
  - La tabla pone primero lo que no tiene panga (luego fecha y hora) y "Aviso" va pegado a
    panga y capitan.
  - Los selectores de panga y capitan **no** usan autocompletado: cada fila ofrece solo las
    pangas libres ese dia y con lugar para su grupo (`ContextoAsignacion`, una consulta por
    dia). Es solo para mostrar: al guardar el formulario conserva todas las opciones para que
    el modelo explique el motivo ("X ya tiene un viaje el ..."). Limite conocido: se
    filtra por `Reserva.fecha`, no por cada dia de un paquete de varias salidas.
  - `static/bookings/panorama.js`: tocar un viaje sin panga marca en verde las pangas
    libres de ese dia cuyo valor exista en el selector de su fila, y tocar una llena el
    selector. No guarda; Guardar sigue siendo el boton de la tabla.

## Calendario (apps/bookings/calendario.py, vistas_calendario.py)

Pantalla de **solo lectura** en `/admin/calendario/` (primera de "Operacion" en el menu), montada en
`config/urls.py` **antes** de `admin/` como las de finanzas. Permiso: `bookings.view_reserva`
(vendedora, jefe y operador). Cada quien ve su empresa; el operador de plataforma elige una (abre en
la primera por nombre) o "Todas". No hay tabla de calendario ni cambia cobro, cupo ni estados: todo
sale de `Reserva`, sus `ReservaSalida` y sus `ViajeTransporte`, con consultas fijas (no una por fila).

- **Estado en la URL**: `vista` (`dia`|`semana`|`mes`, por defecto `semana`), `desde` (cualquier
  fecha ISO del periodo; la semana empieza en lunes), `empresa` (solo operador: slug o `todas`) y
  `canceladas=1`. Un parametro roto cae en su valor por defecto.
- **Qué se ve**: `pagada`, `asignada` y `completada`; la `cancelada` solo con el interruptor; la
  `pendiente_pago` **nunca** (cada checkout abandonado deja una; para eso esta "Checkouts abandonados").
  Pesca y paseos son un evento con hora; hospedaje y paquete de una empresa son una **estancia**
  (barra); cada tramo de `ViajeTransporte` (ida/regreso/unico, sin los `cancelado`) es un evento.
- **Una reserva, una marca por vista.** El paquete es SOLO su barra ("Pérez · 5 noches · 3 al mar")
  en Semana y Mes; sus dias de mar son renglones propios unicamente en la vista Dia ("Al mar"). El
  hallazgo de la linea bajo el titulo cuenta **reservas**, nunca eventos ni tramos, y nunca las
  canceladas aunque se muestren.
- **"Sin panga" y "atrasada"**: pagada sin embarcacion, de fecha de hoy o futura / pasada. Salen del
  mismo criterio que la Agenda (`panorama.sin_lo_que_no_se_reparte`), estrechado: hospedaje, traslados
  y paquetes sin nada de mar nunca piden panga (un paquete con dias de mar sin panga si, como el
  viaje de mar). Color fuerte solo para esas dos marcas; lo asignado va callado.
- **Hallazgo = enlace** a «Asignar pangas» (`?periodo=` y, para las atrasadas, `&cuando=atrasadas`);
  con todo asignado no lleva enlace. Limite: la Agenda filtra por `Reserva.fecha`, asi que un paquete
  cuyo dia de mar cae fuera del periodo cuenta en el hallazgo pero no sale en esa lista.
- **Tira de pangas** ("6 de 10 pangas", Semana y Dia) y "Lleno" (Mes): solo con una empresa elegida
  que tenga pangas. Sale de `obtener_contexto_rango` y `motivo_sin_lugar` (el motor de cupo), no de
  una regla aparte: capacidad = lo menor entre las pangas a flote y el tope del dia.
- **Mes**: el blanco del clic es el dia (toda la celda enlaza a la vista Dia); los renglones no
  son enlaces. El popover (detalle + «Abrir reserva» y «Asignar panga») existe solo en Semana y Dia
  y sin JavaScript cada evento sigue siendo un enlace a su reserva.
- **Estilos**: `static/bookings/calendario.css` (variables CSS, modo oscuro) y `calendario.js`. Unfold
  sirve su Tailwind ya compilado: una clase que no use no existe, asi que la geometria no va en
  clases utilitarias nuevas.

## Cancelacion y reembolso

`Reserva` tiene `motivo_cancelacion`, `cancelada_por` (FK user), `cancelada_en`,
`reembolsada`. La accion de admin "Cancelar por mal clima (reembolso completo)" en
`ReservaAdmin` muestra primero una confirmacion con las reservas y los montos por
moneda; solo el segundo POST marca los 4 campos en una transaccion y deja una
entrada en el History de cada reserva. El reembolso se ejecuta despues en Stripe;
`reembolsada` representa la decision, no la salida de dinero. Mal clima es la unica causa de cancelacion
iniciada por el negocio (ver contexto-negocio.md); la otra la dispara el webhook cuando
el dia se llena mientras el cliente pagaba. Por eso el estado se llama solo "Cancelada
(reembolsada)" y el motivo real vive en `motivo_cancelacion`. No hay flujo de
cancelacion sin reembolso todavia. Auditoria de quien cambio que reserva: el boton
"History" nativo del admin de Django (no se agrego nada custom).
La confirmacion separa los cobros de Stripe, efectivo y transferencia. Los reembolsos
de transferencias se resuelven fuera del sistema y no crean salidas en finanzas.

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

- **`fleet.TransporteTarifa`**: catálogo de precios escalonado por ruta y capacidad (`tipo_traslado`, `zona`, `personas_min`, `personas_max`, `precio` en MXN; el USD se deriva del tipo de cambio de la sede). Tabla protegida por política RLS `tenancy_alcance` bajo `empresa_id`. Admin administrable únicamente por jefes (permisos en `setup_roles`).
- **Estrategia de precio `PorRuta`** (`apps/payments/strategies/por_ruta.py`): resuelve el monto mediante `apps.fleet.tarifa_transporte.resolver_tarifa_transporte(empresa, demanda)` según `tipo_traslado`, `zona` y `numero_personas`. La cotización ocurre siempre en el servidor; `CrearPagoView` congela el `precio_calculado` en `DetalleTransporte`.
- **`bookings.DetalleTransporte`**: detalle operativo asociado `OneToOne` a `Reserva`. Guarda `tipo_traslado`, `punto_encuentro` (FK a `PuntoEncuentro`), `direccion_personalizada`, `zona`, `fecha_regreso` (para `redondo_aeropuerto`), `numero_personas` y `precio_calculado`. Su política RLS de Postgres se aplica vía FK referida a `reserva.empresa_id` y está verificada en el guardarraíl de `apps/tenancy/tests_rls.py`. Visible como `DetalleTransporteInline` en `ReservaAdmin`. La `Agenda` operativa de pangas filtra y omite traslados: los vehículos se asignan por tramo en la pantalla «Asignar vehículos» (`bookings.ViajeTransporte`, ver sección siguiente).
- **Ventana horaria y capacidad por Servicio**: `Servicio.hora_apertura` y `Servicio.hora_cierre` permiten ventanas horarias por servicio (pesca 5:00–7:00am, transporte sin ventana fija). `Servicio.capacidad_maxima` fija el tope de personas (ej. 14 para transporte).
- **Ruta pública `GET /api/<empresa_slug>/traslados/`**: (`apps/fleet/views.py::TrasladosView`), throttled, entrega el catálogo (`servicio`, `tarifas`, `puntos_encuentro`, `publishable_key`) bajo el alcance RLS de la empresa proveedora de transporte.

## Traslados con vehículos (DLS Transporte)

DLS Transporte opera traslados privados (`Servicio.tipo_servicio = 'transporte'`). La venta se mantiene con `estrategia_cupo = 'bajo_demanda'` (vender no se bloquea por falta de flota previa), pero los traslados confirmados se dividen en tramos (`ViajeTransporte`) asignables a vehículos (`Vehiculo`) desde la pantalla operativa «Asignar vehículos».

### Modelos y reglas de validación

- **`fleet.Vehiculo`** (tabla con `empresa_id` y RLS): catálogo de vehículos (`nombre`, `lugares` ≥ 1, `activo`). Restricción `UniqueConstraint(fields=['nombre', 'empresa'])`. Baja lógica con `activo=False` (nunca se borra: `PROTECT` desde viajes), preservando el historial de asignaciones.
- **`fleet.VehiculoNoDisponible`** (RLS por `empresa_id`): bloqueos de flota (`empresa` FK PROTECT, `vehiculo` FK PROTECT, `fecha`, `hora_desde`, `hora_hasta`, `motivo`, `registrado_por`, `creado_en`). Sin horas = día completo. Si se indica una hora deben especificarse ambas y cumplir `hora_desde < hora_hasta`.
  - **Validación inversa en `clean()`**: rechaza el bloqueo si el vehículo ya tiene viajes no cancelados asignados que choquen (`apps.bookings.traslados_reglas::viajes_que_chocan_con_bloqueo`). Un bloqueo de día completo choca con cualquier viaje del día; un bloqueo por rango choca con viajes cuya hora caiga en `[hora_desde, hora_hasta)`; los viajes sin hora no chocan con bloqueos de rango. El vehículo debe pertenecer a la misma empresa.
- **`bookings.ViajeTransporte`** (RLS por `empresa_id`): modela cada tramo operativo del traslado (`empresa` FK PROTECT, `reserva` FK CASCADE, `sentido` con choices `unico`/`ida`/`regreso`, `fecha`, `hora` opcional, `vehiculo` FK fleet.Vehiculo PROTECT nullable, `cancelado` bool). Restricción `UniqueConstraint(fields=['reserva', 'sentido'])`.
  - **Validación en `clean()`**: un viaje `cancelado` no puede tener vehículo asignado; el vehículo debe ser de la misma empresa y estar activo; `reserva.numero_personas <= vehiculo.lugares`; y el vehículo no debe estar bloqueado en esa fecha/hora por ningún `VehiculoNoDisponible` (`bloqueo_cubre_viaje`: viaje sin hora solo choca con bloqueos de día completo; viaje con hora choca con día completo o rangos que la contengan).

### Creación y sincronización de viajes

Lógica centralizada e idempotente en `apps.bookings.traslados::sincronizar_viajes(reserva, detalle=None)`:
- **Tramos deseados según `tipo_traslado`**:
  1. `recepcion_aeropuerto`: 1 viaje (`unico`: `reserva.fecha`, `reserva.hora`).
  2. `redondo_actividad`: 2 viajes (`ida`: `reserva.fecha`, `reserva.hora`; `regreso`: `reserva.fecha`, sin hora inicial).
  3. `redondo_aeropuerto`: 2 viajes (`ida`: `reserva.fecha`, `reserva.hora`; `regreso`: `detalle.fecha_regreso`, sin hora inicial).
- **Ciclo de vida y sincronización**:
  - **Paquete de una empresa con traslado** (sin `DetalleTransporte`): `_tramos_de_paquete` crea `ida` (día del traslado, normalmente el de llegada) y `regreso` (salida del hospedaje; sin hospedaje, el mismo día), los dos **sin hora**: el checkout no pide la hora del vuelo, solo el aeropuerto. «Asignar vehículos» los marca «Falta la hora de vuelo», muestra «Aeropuerto LAP» y deja capturar la hora de los dos tramos; esa hora no se pisa al volver a guardar la reserva. El calendario no los muestra como eventos aparte (el paquete es solo su barra).
  - Reservas que ocupan cupo (`ESTADOS_QUE_OCUPAN_CUPO`): crea los viajes faltantes, actualiza `fecha`/`hora` de los existentes, borra tramos que ya no correspondan (ej. cambio de viaje redondo a recepción), y marca `cancelado=False`. Si la fecha de un viaje cambia, **desasigna el vehículo** (`vehiculo=None`) porque la asignación deja de ser válida; un cambio de hora conserva el vehículo. **Nunca pisa la hora del regreso** si ya fue capturada por la vendedora en la lista.
  - Reservas sin cupo (`pendiente_pago` o `cancelada`): marca `cancelado=True` y desasigna el vehículo (`vehiculo=None`) en los viajes existentes; no crea nuevos viajes.
  - Aplica únicamente si `servicio.tipo_servicio == 'transporte'` y existe `DetalleTransporte` (se protege si `reserva.servicio_id` es nulo o falta el detalle). Utiliza `update_or_create` por `(reserva, sentido)` para prevenir carreras de unicidad.
- **Ganchos automáticos**:
  1. `Reserva._guardar_reserva`: tras `super().save()` cuando `update_fields is None` (mismo punto que `sincronizar_salidas`).
  2. `DetalleTransporte.save()` (pasando `detalle=self` para evitar lecturas de caché desactualizadas) y la señal `post_delete` de `DetalleTransporte` (`borrar_viajes_al_borrar_detalle` en `apps.bookings.signals`), que elimina los viajes asociados al borrar el detalle.
- **Envoltura segura (`sincronizar_viajes_seguro`)**:
  - El webhook de Stripe ejecuta `reserva.save()` dentro de una transacción atómica. Un fallo al crear o sincronizar viajes es un efecto secundario y **no puede tumbar un cobro ni fallar el webhook**.
  - `sincronizar_viajes_seguro` abre su propio savepoint (`with transaction.atomic():`) y atrapa `Exception` (excepción deliberada a la regla general contra `except Exception`), registrando con `logger.exception`. Sin savepoint propio, cualquier error dejaría abortada la transacción principal de PostgreSQL.
- **Herramienta de reparación y migración**:
  - `manage.py sincronizar_viajes_transporte [--dry-run]`: recorre por empresa las reservas de transporte con cupo y detalle, ejecutando `sincronizar_viajes` en cada una.
  - Migración de datos: crea los viajes de reservas históricas con cupo dentro de `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):` para no ser filtradas bajo el rol sin `BYPASSRLS`.

### Pantalla «Asignar vehículos» (admin; antes «Traslados»)

En `/admin/bookings/viajetransporte/` (`ViajeTransporteAdmin`, Unfold, `EmpresaScopedAdminMixin`):
- **Sin creación ni borrado manual**: `has_add_permission=False` y `has_delete_permission=False`. Los viajes los administra exclusivamente el sistema a partir de las reservas.
- **Asignación en lista**: `list_editable = ['hora', 'vehiculo']`. La hora de ida o tramo único viene de la reserva y se muestra deshabilitada en el formulario; la hora del regreso se captura directamente en esta lista porque el checkout no la solicita.
- **Selectores aligerados**: el selector de cada fila ofrece solo vehículos activos que caben y no están bloqueados para ese tramo (más el vehículo asignado actual, que nunca desaparece del selector). Las opciones se cargan en lote por empresa con `ContextoAsignacionVehiculo` (una sola consulta de bloqueos y vehículos) para evitar consultas N+1 en páginas de 50 filas.
- **Resiliencia al guardar (`ViajeTransporteForm`)**: `_post_clean()` omite filas sin cambios (`not self.has_changed()`). Si otro viaje ya asignado quedó inválido con posterioridad (vehículo desactivado, bloqueo ingresado, aumento de pasajeros), no bloquea el guardado de las filas editadas. `_update_errors` reenvía errores de campos ausentes del formulario a `NON_FIELD_ERRORS` evitando errores HTTP 500.
- **Filtros y orden**: filtro "Cuándo" (Hoy, Mañana, Próximos 7 días [por defecto], Todos). Excluye viajes cancelados. Orden: primero viajes sin vehículo asignado, luego por fecha y hora (viajes sin hora al final del día), y pk.
- **Resumen y avisos**:
  - Encabezado: "N sin vehículo" o "Todo asignado".
  - Columna Aviso (alertas informativas en rojo, nunca bloquean el guardado):
    - *"Mismo vehículo a la misma hora que #X"*: aviso de empalme cuando dos viajes coinciden en vehículo, fecha y hora.
    - *"Mismo vehículo con otro traslado a menos de 2 h (#X)"*: aviso cuando el mismo vehículo tiene otro tramo a menos de 2 horas de distancia (un traslado dura).
    - *"Falta la hora"*: tramo de regreso pendiente de hora.
    - *"El vehículo ya no cabe o está bloqueado"*: asignación que quedó inválida por un cambio posterior.

### Permisos y RLS

- **Políticas RLS**: tablas `fleet_vehiculo`, `fleet_vehiculonodisponible` y `bookings_viajetransporte` protegidas por política `tenancy_alcance` en PostgreSQL bajo `empresa_id` (o bypass si `app.operador_plataforma = 'on'`), verificadas por el guardarraíl de `apps/tenancy/tests_rls.py`.
- **Asignación de tenant**: `ViajeTransporte` se crea siempre con `empresa = reserva.empresa`.
- **Configuración de roles (`setup_roles`)**:
  - **Vendedora**: `viajetransporte` (`view`, `change`), `vehiculo` (`view`), `vehiculonodisponible` (`add`, `change`, `delete`, `view`).
  - **Jefe**: permisos de Vendedora + `vehiculo` (`add`, `change`, `delete`).
- **Navegación Unfold (`UNFOLD['SIDEBAR']`)**:
  - Menú Operación: "Calendario", "Asignar pangas", "Asignar vehículos" y "Vehículos no disponibles".
  - Menú Catálogo: "Vehículos".

### Fuera de alcance

- Conductores / choferes (no existe modelo ni asignación de conductores).
- Equipaje o control de volumen de maletas.
- Rutas detalladas, mapas o rastreo satelital/GPS.
- Notificaciones automáticas al cliente al asignar vehículo (a diferencia del correo de asignación de panga/capitán).
- Cuadrícula o panorama de vehículos × días (el tamaño de la flota de DLS hace suficiente el listado tabular).
- Restricción de inventario en la venta: el servicio sigue vendiéndose `bajo_demanda` (vender no se bloquea por falta de vehículo físico).
- Unificación con la `Agenda` de pangas (se mantienen pantallas y modelos operativos separados).

## Roles: Jefes vs Vendedora

- El rol de negocio vive exclusivamente en `MembresiaEmpresa.rol`.
- Los grupos Django `Jefe` y `Vendedora` son únicamente paquetes de permisos de modelo; no deciden reglas de negocio.
- Los grupos `Jefe` y `Vendedora` se derivan y sincronizan solos a partir de las membresías mediante señales en `apps/tenancy/signals.py` y `apps/tenancy/roles.py`. El grupo `OperadorPlataforma` jamás se toca automáticamente (no tiene membresía).
- Los únicos helpers para consultar roles son `apps/tenancy/scope.py`: `scope.es_jefe(...)`, `scope.es_jefe_actual(...)`, `scope.tiene_rol_actual(...)`, `scope.es_vendedora_actual(...)` y `scope.rol_en(...)`.
- **Mismo rol en todas las empresas**: los grupos de Django son globales y no se pueden limitar por empresa, así que una cuenta con roles distintos en dos empresas recibiría la unión de permisos de modelo (p.ej. editar el catálogo donde solo es vendedora). `MembresiaEmpresa.clean()` lo impide (admin de membresías y formularios); `save()`/`create()` directos no validan, y `sincronizar_grupos_de_usuario` sigue calculando bien los grupos de datos antiguos. El alcance RLS y los checks de `scope` aíslan las operaciones por empresa.
- **Jefes** = cuentas `is_staff=True`, `is_superuser=False`, con `MembresiaEmpresa(rol=JEFE)` (y grupo derivado `Jefe`). Ven y operan su propia Empresa, incluyendo la configuracion de catalogo/tarifas y el panel de finanzas (`/admin/finanzas/`).
- **Vendedora** = cuentas `is_staff=True`, `is_superuser=False`, con `MembresiaEmpresa(rol=VENDEDORA)` (y grupo derivado `Vendedora`). Permisos del grupo: `Reserva` (add/change/view, sin delete — se cancela, no se borra), `CupoDiario` (add/change/view), `Embarcacion`/`Capitan` (view only), `Vendedora` (view only, para consultar su codigo de link); y para transporte: `ViajeTransporte` (view/change), `Vehiculo` (view), `VehiculoNoDisponible` (add/change/delete/view). El catálogo financiero de `fleet.Servicio` queda reservado a jefes y operadores (los jefes además tienen `Vehiculo` add/change/delete).
- **Operador de plataforma** = cuenta en grupo Django `OperadorPlataforma`, sin `MembresiaEmpresa`. Acceso global multi-tenant (Sedes, Empresas, Membresias y finanzas consolidadas).
- **Alta de usuario**: acción y formulario unificados "Alta de usuario" en `/admin/auth/user/alta/` (servicio `apps/tenancy/usuarios.py::crear_usuario_con_rol`). El jefe ve el botón "Agregar" y crea vendedoras para su propia empresa (empresa y rol fijos); el operador de plataforma elige empresa y puede crear Jefes o Vendedoras; las vendedoras reciben 403. "Sistema > Usuarios > Agregar" redirige a esta vista. Crea `User` (is_staff=True), `MembresiaEmpresa` (cuya señal asigna automáticamente el grupo Django) y, si es vendedora, `bookings.Vendedora` en una sola transacción respetando RLS.
- En el admin de usuarios (`UserAdmin`), el campo `groups` es de solo lectura para todos los perfiles (operador incluido), impidiendo reemplazos accidentales al guardar.

## Gotchas

- `bookings.Reserva.hora` ya no tiene `validar_ventana_salida` como validador de campo fijo. La ventana horaria se valida en `Reserva.clean()` vía `_validar_ventana_horaria()` gateado por `self.servicio.ventana_horaria()`; servicios como transporte no restringen a 5:00–7:00am. El helper `validar_ventana_salida` se conserva como helper utilitario.
- `embarcacion`/`capitan` en `Reserva` son nullable a proposito: quedan vacios hasta que la
  vendedora asigna manualmente.
- **Reactivación manual CANCELADA -> PAGADA**: `Reserva.save()` reactiva sus `ReservaOcupacion` (`ocupa_cupo=True`) y, desde el admin, `ReservaAdmin.save_model` vuelve a correr `reservar_cupo_al_confirmar` (los componentes se registran con `update_or_create`). `Reserva.clean()` (`_validar_ocupaciones_al_reactivar`) rechaza la reactivación con un error en español si otra venta ya se quedó con una de sus habitaciones: antes era un 500 (EXCLUDE) en Postgres y habitación vendida dos veces en sqlite. Para resolverlo se cambia la habitación en «Ocupaciones del viaje» con la reserva todavía cancelada.
- **Venta manual pagada = misma reserva de cupo que el webhook** (auditoría 2026-10-23). `ReservaAdmin.save_model` llama a `reservar_cupo_al_confirmar` cuando una reserva entra ya pagada (alta con «¿Ya pagó?» ≠ no) o pasa a pagada; si otra venta gana la habitación entre la validación y el guardado, `CupoAgotadoAlGuardar` deshace la transacción del admin y `changeform_view` muestra el aviso (sin 500). **No** pongas este gancho en `Reserva.save()`: muchísimas pruebas crean reservas pagadas y sus `ReservaOcupacion` a mano.
- **Alta de paquete**: la vendedora solo teclea el día de inicio en «Fecha»; `AltaReservaForm` deriva `inicio_paquete`, la fecha de la actividad y la salida del hospedaje con `calendario_paquete` (igual que el checkout) y rechaza una salida tecleada que no coincida.
- **El cupo de una reserva que ya lo ocupa no se revalida si no cambió** (`Reserva._cupo_ya_validado`): bajar/cerrar `CupoDiario` frena ventas nuevas, reprogramaciones y grupos más grandes, pero no impide ponerle panga (ni corregir un dato) a un viaje ya vendido.
- **Hospedaje suelto**: `PorNoche` cobra `precio_base × noches × habitaciones`; las habitaciones salen de `habitaciones_para_precio` (habitaciones activas del servicio, no de lo libre). El hotel real se vende solo dentro de paquetes, así que hoy es latente.
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
- **Precio del paquete**: `Paquete.estrategia_precio` admite `por_grupo` y `por_persona`.
  Por grupo, `precio_ancla` cubre `personas_precio_base` y cada persona adicional suma
  `precio_persona_extra`; por persona, el ancla se multiplica por el grupo cobrado.
  `Paquete.precio_total_en` convierte base y extra desde MXN antes de calcular en USD.
  El grupo cobrado es el MAYOR número entre servicios (`personas_cobradas` en reservas
  y órdenes). Cuando el precio depende de las personas, la actividad (`por_recurso_dia`)
  lleva a todas; hospedaje y traslado pueden llevar menos. En una orden de dos empresas,
  transporte cobra su tarifa según pasajeros y la líder recibe el residuo. La validación
  comprueba que el total cubra cada tamaño de grupo hasta `personas_incluidas` del traslado.
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
Solo `forma_pago=completo`, sin anticipo. El precio base se almacena en MXN en
`Paquete.precio_ancla`; el total depende de `estrategia_precio`,
`personas_precio_base` y `precio_persona_extra`.

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
