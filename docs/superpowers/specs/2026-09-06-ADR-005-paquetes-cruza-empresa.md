# ADR-005: Paquetes Cruza-Empresa

- **Fecha:** 2026-09-06 · **Revisión 2:** 2026-09-07
- **Estado:** ACEPTADO (Revisión 2) — se implementa como Sub-proyecto 2 de
  `docs/superpowers/specs/2026-09-07-transporte-multi-empresa-design.md`
- **Estado previo (Revisión 1, 2026-09-06):** PROPUESTO, bloqueado en v1 vía
  `PaqueteServicio.clean`
- **Decisión (Revisión 2):** Opción A refinada — "modelo B": N PaymentIntents en
  `capture_method='manual'`, autorizar todos y luego capturar; `void` si alguno falla.

---

## 0. Revisión 2 (2026-09-07) — se retoma y se decide

El dueño decidió que **juntar pesca (Empresa 1) + transporte (Empresa 2) es un
paquete**, y que el transporte deja de ser una personalización dentro de la reserva
de pesca. Eso hace que el primer paquete real de producción ("Pesca + Traslado", La
Paz) sea cruza-empresa, así que este ADR deja de estar diferido.

**Decisión:** se implementa la **Opción A refinada** (abajo llamada "modelo B" en el
diseño de SP2):

- El checkout de un paquete cruza-empresa crea una `bookings.Orden` que agrupa N
  `Reserva`, una por empresa proveedora.
- `crear-pago` de la orden crea N `PaymentIntent` con `capture_method='manual'`, uno
  en la cuenta Stripe de cada empresa, por el monto que le toca a esa empresa
  (`PaqueteServicio.monto_empresa`).
- El cliente **autoriza** los N (N confirmaciones en el frontend). Si **todas** quedan
  `requires_capture` → se **capturan** las N. Si alguna falla o el cliente abandona →
  `PaymentIntent.cancel` (void) de las autorizadas; **nunca hubo cobro**.
- `revertir_orden(orden, motivo)` centraliza la compensación (void de autorizaciones,
  refund de capturas) con `idempotency_key` y tolerante a reintentos.
- `conciliar_pagos` y `manage.py revisar_ordenes` son la red de seguridad; el timeout
  de una orden incompleta (`ORDEN_TIMEOUT_AUTORIZACION`, 24 h) es ≪ 7 días (expiración
  de autorización de Stripe).

**Por qué no Opción B (enlaces de pago diferidos):** el dueño quiere que el cliente
pague todo en el checkout. Opción B mete pago en dos momentos y trabajo manual de la
vendedora en cada reserva. Sigue siendo un repliegue válido si el volumen resulta muy
bajo.

**Por qué no Opción C (Stripe Connect):** decisión de negocio/fiscal ya tomada — la
plataforma no intermedia fondos (ver §1). No se reabre sin asesoría fiscal.

**Alcance v1:** solo "un componente base de una empresa + un componente de traslado
de otra empresa" (orden de 2 cobros). No carrito general de N empresas. `forma_pago`
restringido a `completo` (sin anticipo) en órdenes cruza-empresa.

El detalle de modelos, API, webhook, tenancy y pruebas está en el diseño de SP2.

---

---

## 1. Contexto

En el diseño del sistema multi-empresa, cada empresa proveedora registrada posee su propia cuenta bancaria y su propia cuenta de Stripe independiente. La empresa administradora/marketing (operador de plataforma) **no posee cuenta central a propósito**, con el fin explícito de no intermediar fondos ni asumir la carga tributaria o fiscal derivada del volumen total de transacciones de terceros.

Por diseño arquitectónico y de negocio, la plataforma no utiliza Stripe Connect en su versión inicial. Todos los cobros se procesan de forma directa en la cuenta de Stripe de la empresa proveedora que presta el servicio.

---

## 2. Problema

Un paquete turístico de experiencias cruza-empresa (por ejemplo, un tour de pesca provisto por la Empresa A combinado con dos noches de hospedaje en un hotel provisto por la Empresa B) requiere que los fondos cobrados se depositen en las cuentas bancarias de las respectivas empresas proveedoras independientes: N servicios hacia N cuentas distintas.

En la infraestructura de Stripe estándar (sin Stripe Connect), no es posible montar un único `PaymentElement` o sesión de pago que confirme atómicamente múltiples `PaymentIntent` pertenecientes a diferentes cuentas comerciales como si fuera una sola transacción percibida por el cliente final. Si un cliente paga online, una sola tarjeta no puede debitarse simultáneamente hacia dos cuentas de Stripe independientes sin generar cobros separados y visibles.

---

## 3. Estado en v1 (Levantado en SP2 — Revisión 2)

En la versión v1 del sistema, los paquetes cruza-empresa quedaban **explícitamente bloqueados**:

- Todo `Paquete` pertenece a una única empresa proveedora (`empresa_lider`), asociada a una localidad (`sede`).
- La validación previa en el modelo `PaqueteServicio.clean()` rechazaba cualquier intento de asociar a un paquete un componente o servicio que no pertenezca a la misma `empresa_lider` del paquete.
- **Levantado en SP2:** `PaqueteServicio.clean()` ahora valida que el componente pertenezca a una empresa de la **misma sede** que el paquete (`self.servicio.empresa.sede_id == self.paquete.sede_id`), permitiendo componentes cruza-empresa dentro de la misma sede.

---

## 4. Lo que ya quedó preparado en la arquitectura

Aunque los paquetes cruza-empresa no están habilitados en v1, la arquitectura de datos y dominio fue diseñada para facilitar su habilitación en fases posteriores sin rediseños destructivos:

1. **Jerarquía en Catálogo:** El modelo `Paquete` pertenece a una `sede` y cuenta con un campo explícito `empresa_lider`.
2. **Componentes con Tenancy:** El modelo `ReservaPaqueteComponente` posee una clave foránea `empresa` por cada componente reservado, permitiendo que en el futuro los componentes pertenezcan a diferentes empresas sin alterar el esquema de base de datos.
3. **Catálogo Multi-Sede:** El catálogo de sedes (`paquetes_de_sede`) itera de forma aislada a través del contexto RLS de cada empresa proveedora de la localidad.

---

## 5. Opciones a Evaluar cuando se retome

Cuando se decida habilitar la venta de paquetes cruza-empresa, se deberán evaluar las siguientes alternativas (sin recomendación cerrada por el momento):

- **Opción A — Múltiples PaymentIntents secuenciales en el checkout:** El cliente autoriza los cobros secuencialmente en el flujo de checkout hacia cada cuenta de Stripe. Requiere lógica robusta de compensación y reembolsos parciales automáticos en caso de que alguno de los cobros o cupos falle a mitad del proceso.
- **Opción B — Cobro online de empresa líder + enlaces de pago diferidos:** La `empresa_lider` cobra su parte online al momento de la reserva en el sitio web, y las empresas colaboradoras envían enlaces de pago adicionales coordinados por la vendedora antes de la fecha de llegada.
- **Opción C — Stripe Connect con Direct Charges:** Evaluar la implementación de Stripe Connect utilizando cargos directos (`direct charges`), donde el cargo se genera directamente en la cuenta conectada del proveedor y los fondos nunca tocan la cuenta de la plataforma, evaluando previamente con asesores fiscales si esto evita responsabilidades tributarias para la plataforma.
