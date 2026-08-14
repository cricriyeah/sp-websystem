# Riesgo de proveedor — Stripe

Fecha de revisión: 2026-08-13 · Origen: hallazgo F-12 de `docs/audit/AUDIT-2026-08-12.md`
Próxima revisión: 2027-08-13, o antes si cambia la integración

## Qué hace por nosotros

Procesa todos los cobros con tarjeta del checkout web. Cuenta estándar, **no**
Stripe Connect (ver `docs/contexto-negocio.md`). Integración vía
`@stripe/react-stripe-js` (`PaymentElement`) + PaymentIntents del lado servidor.

Criticidad: **alta**. Si Stripe está caído no se puede cobrar en línea; el
checkout responde 503 y lo muestra como `checkout.paymentUnavailable` en vez de
romperse. Las reservas por WhatsApp no dependen de Stripe.

## Qué datos recibe

| Dato | Quién se lo manda |
|---|---|
| Número de tarjeta, CVC, expiración | El navegador del cliente, directo. **Nunca pasa por nuestro backend.** |
| Monto, moneda, `metadata.reserva_id` | Nuestro backend al crear el PaymentIntent |
| Dirección de facturación / correo, si el cliente los captura en Elements | El navegador del cliente, directo |

No le mandamos nombre, teléfono ni el contenido del deslinde: esos se quedan en
nuestra base.

## Qué datos recibimos de vuelta

Vía webhook y `PaymentIntent.retrieve`: id del intent, monto cobrado, moneda,
estado, fecha del cobro, montos reembolsados y eventos de disputa. Se guardan en
`bookings.Reserva` (`stripe_payment_intent_id`, `monto_pagado`, `pagada_en`,
`monto_reembolsado`, `reembolsada_en`, `en_disputa`).

## Postura de cumplimiento

- **PCI DSS Level 1 service provider**, certificado anualmente por un QSA
  independiente. Es el nivel más estricto de la industria.
- Nuestra integración (Elements) mantiene el sistema en **SAQ-A** — ver
  `docs/threat-models/TM-payments.md`, sección "Alcance PCI-DSS".
- Stripe ofrece SAQ prellenados en el Dashboard para integraciones vía Elements /
  Checkout. **Acción pendiente:** completar el SAQ-A en el Dashboard antes de
  operar con dinero real.

## Términos de tratamiento de datos

Contrato: [Data Processing Agreement de Stripe](https://stripe.com/legal/dpa).

**Rol.** Stripe actúa con **doble rol** — es *encargado* (processor) cuando trata
datos por cuenta nuestra para prestar el servicio, y es *responsable*
(controller) por derecho propio para monitoreo de fraude, cumplimiento legal y
mejora del servicio (Sección 2 del DPA). Esto importa: sobre esa segunda parte no
tenemos control ni podemos instruirle qué hacer.

**Notificación de brecha.** Sin demora indebida; para datos personales sujetos a
GDPR / UK GDPR, **no más de 48 horas** (Sección 3.1(f)). La notificación debe
describir el tipo de dato afectado, categorías y número aproximado de personas o
registros, y el estado de la investigación y remediación.

**Nuestra obligación recíproca:** debemos notificar a Stripe *de inmediato* si
detectamos acceso o pérdida no autorizada de datos personales en nuestros
sistemas que hayan sido proporcionados a Stripe o usados con sus servicios.

**Subencargados.** Aviso con **al menos 30 días** de antelación antes de agregar
uno nuevo, con derecho a objetar por motivos legítimos dentro de esos 30 días
(Sección 3.2(a)). Lista y suscripción a avisos:
[Service Providers, Sub-Processors & Affiliates](https://stripe.com/legal/service-providers).
**Acción pendiente:** suscribirse a esas notificaciones con el correo del negocio.

**Retención y borrado.** Al terminar el contrato, Stripe borra o devuelve los
datos personales tratados en relación con el servicio, salvo lo que necesite
conservar para ejercer sus derechos bajo el contrato o por obligación legal
(Sección 3.1(h)). En la práctica los registros de transacciones se conservan por
obligaciones fiscales y antifraude.

## Gestión de llaves

Tres secretos, todos por variable de entorno, sin valores por defecto:
`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`.
En local están vacías a propósito y `crear-pago` responde 503.
En producción se capturan en Render (`render.yaml`, marcadas `sync: false` — nunca
se escriben en el repo).

Rotación: no hay política definida todavía. **Acción pendiente:** rotar la
`STRIPE_SECRET_KEY` si alguna vez aparece en un log, un screenshot o un canal de
chat, y definir una cadencia de rotación al menos anual.

## Plan si Stripe falla

- **Caída temporal:** el checkout muestra pago no disponible; las reservas se
  siguen cerrando por WhatsApp y se registran con `canal_origen='whatsapp'`.
- **Webhook no llega:** `conciliar_pagos` cada hora recupera el estado real
  (`render.yaml`). Es la red de seguridad principal.
- **Cierre de cuenta o cambio de proveedor:** no hay segundo PSP configurado ni
  abstracción para cambiarlo. Migrar exigiría reescribir `apps/payments`. Riesgo
  aceptado al volumen actual.

## Enlaces

- DPA: https://stripe.com/legal/dpa
- Subencargados: https://stripe.com/legal/service-providers
- Aviso de privacidad: https://stripe.com/privacy
- Seguridad: https://docs.stripe.com/security
- Contrato de servicios: https://stripe.com/legal/ssa
