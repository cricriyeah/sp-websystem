# Riesgo de proveedor — Supabase

Fecha de revisión: 2026-08-13 · Origen: hallazgo F-12 de `docs/audit/AUDIT-2026-08-12.md`
Próxima revisión: 2027-08-13, o antes si cambia el plan contratado

## Qué hace por nosotros

Aloja la base de datos Postgres de producción. Se usa **solo como Postgres
gestionado**: no usamos Supabase Auth, Storage, Realtime ni Edge Functions. El
backend se conecta con `psycopg` desde Django (`config/settings/production.py`),
igual que a cualquier Postgres.

Eso es una ventaja de riesgo que conviene no perder: cambiar de proveedor de
Postgres es un cambio de credenciales, no una reescritura.

Criticidad: **alta**. Si la base está caída, el sistema entero está caído.

## Qué datos guarda

Toda la base de la aplicación. PII de clientes en `bookings_reserva`:

| Campo | Tipo de dato |
|---|---|
| `nombre_cliente` | Identificación |
| `telefono_cliente` | Contacto |
| `correo_cliente` | Contacto |
| `deslinde_nombre`, `deslinde_ip`, `deslinde_aceptado_en` | Constancia legal |

Además: cuentas de usuario del backoffice (`auth_user`) con contraseñas hasheadas
por Django, y referencias a pagos (`stripe_payment_intent_id`, montos, fechas).

**No guarda ningún dato de tarjeta.** Ver `docs/threat-models/TM-payments.md`.

## Postura de cumplimiento

- **SOC 2 Type 2**, evaluado anualmente (seguridad, disponibilidad, integridad de
  procesamiento, confidencialidad y privacidad).
- Reporte SOC 2 disponible bajo solicitud en https://forms.supabase.com/soc2.
  **Acción pendiente:** solicitarlo y archivarlo junto a este documento.

## Términos de tratamiento de datos

Contrato: [Data Processing Addendum de Supabase](https://supabase.com/legal/dpa).

**Notificación de brecha.** Por escrito, sin demora indebida y **donde sea
factible dentro de 48 horas** de tener conocimiento del incidente, al correo
asociado a la cuenta. Supabase se obliga además a contener, investigar y mitigar,
e informar la naturaleza del incidente, las medidas tomadas y el estado de la
investigación.

**Implicación operativa:** ese aviso llega al correo de la cuenta de Supabase. Si
esa cuenta está a nombre de una sola persona y esa persona no lo revisa, el
mecanismo de notificación no sirve. **Acción pendiente:** confirmar a qué correo
llega y que lo lea más de una persona.

**Subencargados.** Supabase firma acuerdos con cada subencargado imponiendo
obligaciones no menos protectoras que las suyas, y responde por su cumplimiento.
Aviso con **al menos 30 días** antes de cualquier cambio, con opción de
suscribirse a esas notificaciones. **Acción pendiente:** suscribirse.

## Respaldos y recuperación

Esta era una de las preguntas abiertas de la auditoría: *"¿hay política de
respaldo/PITR, o dependemos de los valores por defecto?"*.

**Decidido 2026-08-14: plan de pago, no Free.** El tier gratuito queda descartado
explícitamente porque no garantiza respaldos, y este sistema guarda dinero
cobrado y constancia legal.

| Plan | Respaldos diarios automáticos | PITR |
|---|---|---|
| ~~Free~~ | ~~No garantizados~~ | ~~No~~ — descartado |
| Pro | Últimos 7 días | Add-on de pago |
| Team | Últimos 14 días | Add-on de pago |
| Enterprise | Hasta 30 días | Add-on de pago |

**Point-in-Time Recovery** permite restaurar a un punto elegido con granularidad
de segundos, en vez de perder hasta 24 horas. Es un add-on de pago y requiere al
menos el compute add-on *Small*.

### Sub-decisión abierta: activar PITR o aceptar la ventana de 24 horas

Con respaldo diario únicamente, la pérdida máxima es de hasta 24 horas. Lo que se
pierde en ese escenario no es uniforme, y esa es la parte que decide:

| Dato | ¿Se recupera? | Cómo |
|---|---|---|
| Que un cliente pagó, cuánto y cuándo | **Sí** | `conciliar_pagos` lo reconstruye desde Stripe |
| Quién es, su teléfono y su correo | **No** | Solo vive en nuestra base |
| Fecha y hora de salida que reservó | **No** | Solo vive en nuestra base |
| Constancia del deslinde (nombre, IP, momento) | **No** | Solo vive en nuestra base — es evidencia legal |

El escenario concreto de una restauración desde respaldo diario: sabes que entró
dinero, pero no sabes quién se presenta mañana a las 6:00 en el muelle, ni tienes
cómo contactarlo, ni la constancia de que firmó el deslinde.

### Decidido 2026-08-14: sin PITR por ahora — riesgo aceptado

PITR cuesta ~$100 USD/mes por 7 días de retención ($0.137/hora; se factura por
hora y el precio mensual es esa tarifa por ~730 horas). Desproporcionado para el
volumen actual del negocio.

**Se acepta explícitamente una ventana de pérdida de hasta 24 horas**, con estas
consideraciones:

- Los respaldos diarios del plan Pro (7 días de historial) **sí** cubren el
  escenario de falla de plataforma o de hardware. Eso es riesgo de Supabase y ya
  está mitigado.
- Lo que queda descubierto es el **error humano propio**: una migración mala, un
  `UPDATE` sin `WHERE`, un bug nuevo escribiendo basura. Ese riesgo se reduce
  porque la vendedora opera vía el admin de Django, que no le da SQL crudo y no
  le permite borrar reservas.

**Mitigación implementada (2026-08-14):** copia oculta de cada confirmación de
pago a una dirección del negocio (`RESEND_BCC`). No es un respaldo — es un rastro
fuera de la base. Tras una restauración permite identificar y contactar a los
clientes de las reservas perdidas: nombre, correo, fecha, hora de salida, número
de personas y estado del pago. **No** recupera el teléfono ni la constancia del
deslinde.

**Mitigación recomendada y aún no implementada:** un cron de `pg_dump` cada 6
horas hacia almacenamiento externo (Cloudflare R2 / Backblaze B2), ~$2 USD/mes.
Reduciría la ventana de 24 a 6 horas. La infraestructura de cron ya existe en
`render.yaml`.

**Disciplina obligatoria mientras no haya PITR:** tomar un respaldo manual antes
de correr cualquier migración. Es el momento de mayor riesgo y es predecible.

**Cuándo reevaluar:** cuando perder medio día de reservas cueste más de $1,200
USD al año en valor esperado. Para entonces habrá números reales de temporada en
vez de estimaciones.

**Lo que sigue sin cubrir en cualquier caso:** la constancia del deslinde (nombre
firmado, IP, momento) solo vive en la base. Si se restaura un respaldo, la de las
reservas perdidas no se recupera de ningún lado. Es el argumento más fuerte a
favor de PITR el día que se reevalúe.

## Credenciales

`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, todas por variable de
entorno sin valores por defecto — `production.py` falla explícito si falta alguna.
En Render se capturan en el env group `pescadeportiva-secrets` (`render.yaml`,
`sync: false`), compartido por el servicio web y los dos cron.

Rotación: sin política definida. **Acción pendiente:** rotar la contraseña de la
base si aparece en un log o screenshot, y definir cadencia al menos anual.

## Plan si Supabase falla

- **Caída temporal:** el sistema entero queda fuera. No hay réplica ni modo de
  solo lectura. Las reservas se toman por teléfono/WhatsApp y se capturan después.
- **Pérdida de datos:** ver la sección de respaldos. La reconstrucción parcial es
  posible cruzando contra Stripe (`conciliar_pagos` recupera pagos), pero los
  datos de contacto del cliente y la constancia del deslinde **no** están en
  Stripe y se perderían.
- **Cambio de proveedor:** relativamente barato, porque solo usamos Postgres
  estándar. Un `pg_dump` y un cambio de variables de entorno.

## Enlaces

- DPA: https://supabase.com/legal/dpa
- Seguridad: https://supabase.com/security
- SOC 2: https://supabase.com/docs/guides/security/soc-2-compliance
- Respaldos: https://supabase.com/docs/guides/platform/backups
- PITR: https://supabase.com/docs/guides/platform/manage-your-usage/point-in-time-recovery
- Aviso de privacidad: https://supabase.com/privacy
