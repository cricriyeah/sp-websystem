# Contexto de negocio — Sistema de Gestión Operativa (Tours de Pesca Deportiva)

> Este archivo resume todas las decisiones de producto y arquitectura tomadas antes de escribir código.
> Plazo: 1 mes. Equipo: 2 programadores.

## 1. Qué es el sistema

Negocio de tours privados de pesca deportiva, con una flota de embarcaciones operadas por capitanes.
El sistema tiene tres piezas conectadas por una misma base de datos:

1. **Backoffice (Django Admin)** — para los jefes: catálogo de embarcaciones, capitanes, servicios.
2. **Panel de la coordinadora/vendedora (bilingüe)** — gestiona la operación diaria: revisa reservas,
   asigna embarcación y capitán a cada una, habla con clientes por WhatsApp.
3. **Web pública (es/en)** — reserva y pago en línea para clientes que llegan por publicidad,
   recomendación o de forma orgánica.

**Los capitanes NO tienen usuario ni login en el sistema.** Los jefes son también capitanes y coordinan
sustituciones directamente con su gremio de capitanes, por fuera del sistema. Cuando saben que van a
andar cortos de embarcaciones, son ellos o la vendedora quienes cierran/reducen manualmente el cupo de
ese día en el sistema.

## 2. Stack técnico

| Componente | Tecnología | Hosting |
|---|---|---|
| Backend / backoffice | Django (Python) | Render |
| Base de datos | PostgreSQL (Supabase) | Supabase |
| Web pública | Next.js | Vercel |
| Pagos | Stripe — **cuenta estándar, NO Stripe Connect** | — |
| Notificaciones | WhatsApp Business API + Resend (email) | — |

**Por qué no Stripe Connect:** los jefes gestionan el pago a cada capitán de forma separada, fuera del
sistema. El sistema recibe el 100% del pago a la cuenta de los jefes y solo registra qué capitán/embarcación
atendió cada reserva, para estadística. No hay reparto automático de dinero.

Estructura de repo (monorepo):

```
tours-pesca/
├── backend/    → Django (Render)
│   └── apps/
│       ├── fleet/          # Embarcacion, Capitan (catálogo, sin login)
│       ├── bookings/       # Reserva, validación de cupo, asignación manual
│       ├── payments/       # Stripe (cuenta estándar)
│       └── notifications/  # WhatsApp + email
├── frontend/   → Next.js (Vercel)
└── docs/
```

## 3. Reglas del negocio (confirmadas)

### Servicio
- Único servicio: pesca deportiva. Modalidad privada (una reserva = toda la embarcación, nunca se comparte).
- Duración: 6 a 8 horas.
- Ventana de salida: 5:00 a 7:00 am. **El cliente elige la hora exacta dentro de esa ventana al reservar.**
- Opera los 365 días del año (la pesca varía por temporada, la operación no se detiene).
- **Sin restricción de edad y sin mínimo de personas** — un viaje puede salir con una sola persona.
- Incluye: equipo de pesca, hielera con hielo. No incluye: carnada, licencia de pesca, alimentos, bebidas.
- Punto de encuentro: Marina La Costa (Rangel y Navarro / Restaurant Marina La Costa). El cliente llega por su cuenta.
- **No se piden datos adicionales de seguridad** (ni peso, ni si sabe nadar) — solo nombre, teléfono, correo.

### Embarcaciones
- 2 clases: chica (máx. 3 personas) y grande (máx. 6 personas). Precio fijo, no varía por clase.
- Capacidad operativa actual de la flota: **8 a 10 viajes por día en total.**

### Pagos
- El cliente elige libremente: 100% en línea, o 30% de anticipo en línea + 70% restante en efectivo.
- Confirmación automática por correo al recibir el pago. Monedas: pesos y dólares.

### Cancelaciones y cambios
- Única causa de cancelación con reembolso: mal clima (reembolso completo).
  - La decisión de que hay mal clima la puede originar el capitán o la vendedora — pero como el capitán
    no tiene acceso al sistema, **quien ejecuta la cancelación/reembolso en el sistema es la vendedora o
    los jefes**, a partir del aviso del capitán.
- Cambio de fecha permitido con mínimo 48 horas de anticipación; se reasigna al espacio/fecha más próximos.

### Legal
- Deslinde de responsabilidad requerido: casilla de aceptación + nombre, fecha/hora, IP capturados al reservar
  (confirmar con abogado si es legalmente suficiente).
- No se requiere factura fiscal (CFDI). Las embarcaciones ya cuentan con seguro.

### Idioma
- Web pública disponible en español e inglés.

## 4. Lógica de reservas — flujo exacto

1. **Cómo llega el cliente:** orgánico (redes, Google, recomendación) → paga directo en la web.
   O por WhatsApp → lo atiende la vendedora, quien lo dirige a pagar en esa misma web.
   No existe canal de pago independiente por capitán (no hay links de cobro individuales).
2. **Al pagar:** el sistema valida que ese día no haya llegado al tope operativo (8–10 viajes). Si está lleno,
   no permite completar la reserva para esa fecha. En este paso *aún no* asigna embarcación ni capitán.
3. **Asignación:** la vendedora asigna manualmente cada reserva pagada a una embarcación y capitán específicos
   desde su panel — incluidas las que el cliente pagó solo, sin hablar con ella. No hay algoritmo automático
   de reparto; ella usa su propio criterio (carga de trabajo, disponibilidad real).
4. El cliente recibe confirmación de fecha/hora/pago de inmediato. El capitán y la embarcación se comunican
   después, una vez asignados — y es la vendedora quien le informa la hora acordada al capitán (él no ve el sistema).

## 5. Roles y permisos

| Rol | Ve | Edita |
|---|---|---|
| Jefes | Todo, incluido el panel financiero | Todo |
| Coordinadora/vendedora | Vista operativa (calendario, reservas) sin la foto global del dinero | Cualquier reserva; asigna embarcación/capitán; crea reservas manuales; marca qué ventas son suyas |

### Comisión de la vendedora

La vendedora cobra comisión por los viajes **que ella vende** (no por los que
administra: asignar embarcación o capitán a una reserva que llegó sola no la hace suya).

**El cálculo y el pago de la comisión ocurren fuera del sistema.** El sistema no guarda
porcentajes, montos ni saldos acumulados: lo único que lleva es el registro de a quién
le corresponde cada venta, para que ese cálculo externo tenga de dónde partir.

Cómo se atribuye una venta, dos vías que conviven:

1. **Link propio.** Cada vendedora tiene un código y le pasa a sus clientes un link con
   él (`.../reservar?ref=<codigo>`). Quien reserve y pague desde ahí queda atribuido
   solo. El código vale 30 días desde que el cliente entra por el link.
2. **Marcado manual.** Para lo que se cerró por WhatsApp o por teléfono, la vendedora
   marca la reserva como venta suya desde su panel. Solo puede atribuírsela a sí misma.

Hoy hay una sola vendedora, pero el modelo soporta varias sin cambios: cada una es una
cuenta con su código.

### Panel financiero (solo jefes)

Una pantalla con todo el dinero centralizado:

- Entradas por tarjeta (pagos de la web) y entradas en efectivo (lo que se cobra el día
  del viaje), por separado.
- Salidas: únicamente cancelaciones y reembolsos. **No se registran** pagos a capitanes,
  gastos de operación, pago de comisiones ni retiros — eso se maneja fuera del sistema.
- Balance del día, del mes y del año, más el histórico día por día.
- Lo que debería haber en la cuenta de Stripe y lo que debería haber en efectivo.

Pesos y dólares se llevan por separado y nunca se suman: son dos precios de lista que el
negocio fija a mano, el sistema no aplica ningún tipo de cambio.

Notas de implementación:
- Toda reserva creada manualmente por la vendedora debe pasar por el mismo motor de validación de cupo
  que usa el flujo automático de la web, para evitar dobles reservas.
- Se recomienda registro de auditoría (quién cambió qué reserva y cuándo), ya que la vendedora puede
  modificar reservas que no creó ella.

## 6. Estado de las decisiones

No quedan preguntas de negocio pendientes de confirmar — todas las dudas abiertas durante el diseño
(clima, datos del cliente, mínimo de personas, forma de pago, hora de salida, sustitución de capitanes)
ya están resueltas y reflejadas arriba.
