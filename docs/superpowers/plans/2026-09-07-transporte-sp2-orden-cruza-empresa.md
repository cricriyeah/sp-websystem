# SP2 — Órdenes cruza-empresa (paquete Pesca + Traslado) · Tareas ejecutables

> **Para agentic workers:** SUB-SKILL REQUERIDA: `superpowers:subagent-driven-development`
> o `superpowers:executing-plans`, task por task. Pasos con checkbox (`- [ ]`).
>
> **Para el agente que ejecuta (Antigravity):** autosuficiente. Tareas **en orden**,
> cada una con su ciclo (test que falla → código → test verde → commit). **PARA AL
> FINAL DE CADA SECCIÓN**, corre el Gate (sqlite Y Postgres) y reporta. No sigas sin
> luz verde. Decisión de producto no contemplada → **para y pregunta**.
>
> **NO arranques SP2 hasta:** (1) SP1 completado y con luz verde del dueño;
> (2) la Sección 10 del plan de corrección de hallazgos (paquete sin servicios
> removibles) mergeada a esta rama.
>
> **Empieza por la Sección 0** (verificación de prerrequisitos).

**Goal:** vender el paquete "Pesca + Traslado" (componente de la Empresa 1 + componente
de la Empresa 2), cobrando a cada empresa en su propia cuenta Stripe, con una sola
compra percibida por el cliente.

**Architecture:** una `bookings.Orden` agrupa N `Reserva` (una por empresa). `crear-pago`
crea N `PaymentIntent` con `capture_method='manual'` (uno por cuenta Stripe). El
cliente autoriza los N; si todos quedan `requires_capture` se capturan los N; si alguno
falla se hace `cancel` (void) de los autorizados — nunca hubo cobro. `revertir_orden`
centraliza la compensación. `conciliar_pagos` y `revisar_ordenes` son la red de
seguridad.

**Tech Stack:** Python 3.14, Django 6, DRF, psycopg 3, Postgres con RLS,
stripe-python (`StripeClient` por empresa vía `configurar_stripe(empresa)`), Next.js 16,
`@stripe/react-stripe-js`.

**Spec:** `docs/superpowers/specs/2026-09-07-transporte-multi-empresa-design.md`
(§1, §4, §5, §6, §7). Y `docs/superpowers/specs/2026-09-06-ADR-005-paquetes-cruza-empresa.md`
Revisión 2. Léelas si algo no cuadra.

**Rama:** `feat/transporte-multi-empresa`. **No se mergea a `main` hasta que
`fix/expansion-multi-sede-hallazgos` esté integrada.**

---

## Global Constraints

Idénticas a SP1 (`2026-09-07-transporte-sp1-servicio.md` §"Global Constraints").
Además, para SP2:

10. **El webhook es la única fuente de verdad, también para órdenes.** El frontend
    nunca marca una orden como capturada; lo hace el backend tras verificar con Stripe.
11. **Toda operación de Stripe en SP2 lleva `idempotency_key`** derivada de
    `(orden_id, empresa_id, operación)`. Un reintento no debe cobrar, capturar ni
    reembolsar dos veces.
12. **`forma_pago` en órdenes cruza-empresa: solo `completo`.** El checkout de un
    paquete cruza-empresa no ofrece anticipo (decisión del dueño, 2026-09-07).
13. **Reparto:** transporte a su `TransporteTarifa`; el residuo
    (`precio_paquete − monto_transporte`) va a la `empresa_lider` (pesca). Sin campo
    nuevo. Única fuente: `apps/payments/pricing.py::monto_por_empresa`.

---

## Entorno y comandos

Idénticos a SP1. Recordatorio del Gate:

```bash
backend/venv/Scripts/python.exe manage.py test apps config           # sqlite
docker exec psd-pg psql -U postgres -c "DROP DATABASE IF EXISTS test_pescadeportiva_test;"
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test DB_USER=ci_rls \
DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
backend/venv/Scripts/python.exe manage.py test apps config           # postgres
```

Tests de Stripe: se mockea `stripe.StripeClient` (patrón ya usado en
`backend/apps/payments/tests.py`). Los PaymentIntent en modo manual capture tienen
`status` `requires_confirmation` → `requires_capture` (tras confirmar) → `succeeded`
(tras capturar) o `canceled` (tras cancel). El mock debe reflejar esas transiciones.

---

## File Map

| Archivo | Responsabilidad | Sección |
|---|---|---|
| `backend/apps/bookings/models.py` | modelo `Orden` (estados, `checkout_id`, cliente, `empresa_lider`, `sede`); `Reserva.orden` FK; gate de `orden_id` en `_validar_cupo_de_paquete` y `_validar_consistencia_de_empresa` | 1, 3 |
| `backend/apps/bookings/migrations/00XX_*.py` | `Orden` + RLS sede-scoped (con `WITH CHECK` que permite el INSERT público); `Reserva.orden`; función `estado_reservas_de_orden(orden_id)` `SECURITY DEFINER` | 1 |
| `backend/apps/fleet/models.py` | `PaqueteServicio.clean()` acepta componente de otra empresa de la misma sede; `Paquete.clean()` valida `precio_paquete ≥ monto_transporte` | 2 |
| `backend/apps/payments/pricing.py` | `monto_por_empresa(*, precio_paquete, componentes, moneda) -> {empresa_id: Decimal}` (puro, única fuente del reparto). **Sin campo `PaqueteServicio.monto_empresa`.** | 2 |
| `backend/apps/tenancy/` (migración o `scope.py`) | función Postgres `estado_reservas_de_orden(orden_id)` `SECURITY DEFINER` — lectura cruza-empresa acotada a una orden (la usan cierre de orden, `revertir_orden`, notificación, conciliar, admin) | 1 |
| `backend/apps/bookings/cupo/confirmacion.py` | separar Caso B mono-empresa del nuevo "confirmar solo mi componente" para reservas con `orden` | 3 |
| `backend/apps/payments/ordenes.py` (nuevo) | orquestación de la orden: crear N PaymentIntents, `confirmar_captura(orden)`, `revertir_orden(orden, motivo)` | 4, 5 |
| `backend/apps/payments/services.py` | `aplicar_pago_exitoso` evalúa la orden al pagar la última reserva; llama `revertir_orden` en el camino de compensación | 5 |
| `backend/apps/payments/views.py` | `CrearOrdenView`, `CrearPagoOrdenView`, `ConfirmarCapturaOrdenView` | 4 |
| `backend/apps/payments/urls.py` / `config/urls.py` | rutas `<sede_slug>/ordenes/...` | 4 |
| `backend/apps/payments/management/commands/conciliar_pagos.py` | rama orden-aware | 6 |
| `backend/apps/payments/management/commands/revisar_ordenes.py` (nuevo) | lista órdenes atascadas | 6 |
| `backend/apps/notifications/services.py` | `notificar_orden_pagada(orden)` — correo combinado; WhatsApp sigue por empresa | 5 |
| `backend/apps/bookings/admin.py` | `OrdenAdmin` (solo lectura + acción cancelar); enlace orden↔reserva | 7 |
| `backend/apps/bookings/models.py` (deslinde) | `deslinde_version` nueva; el deslinde de la orden se copia a cada reserva | 9 |
| `frontend/src/components/paquete-checkout.tsx` (nuevo o extensión de `checkout-view`) | detecta paquete cruza-empresa → modo orden; N `PaymentElement` **solo tarjeta** en secuencia; reanuda la orden en curso tras recarga | 8 |
| `frontend/src/lib/api.ts` | `crearOrden`, `crearPagoOrden`, `confirmarCapturaOrden`, `getOrden` (para reanudar) | 8 |
| `frontend/src/app/[lang]/deslinde/` + dictionaries | texto del deslinde ampliado a multi-empresa | 9 |
| `backend/apps/*/tests.py` | tests de cada tarea | todas |

<!-- arch-critic: REVISIÓN REQUERIDA (inline, 2026-09-07) → CORREGIDA. Hallazgos aplicados:
(C-12) Contexto RLS: `CrearOrdenView` (AllowAny) escribe N reservas en N empresas — itera `scope.con_empresa(componente.empresa)` por escritura (Tarea 4.1); la política RLS de `Orden` lleva `WITH CHECK` que permite el INSERT público acotado por `sede` (Tarea 1.2).
(C-13) Lectura cruza-empresa: el webhook de una empresa NO ve las reservas hermanas de otras empresas (RLS las filtra) → "¿todas pagadas?" daría True tras el primer webhook. Se resuelve con la función Postgres `estado_reservas_de_orden(orden_id)` SECURITY DEFINER (Tarea 1.3), acotada a una orden. La usan cierre de orden, `revertir_orden`, `notificar_orden_pagada`, `conciliar_pagos`, `OrdenAdmin`.
(S-14) `notificar_orden_pagada` usa esa misma función (Tarea 5.4).
Verificado además:
(1) Sin ciclo: `services → ordenes`; `conciliar_pagos → {services, ordenes}`; `confirmacion.py` NO importa `ordenes` (lanza `SinCupoError`, `services.py` lo captura y llama `revertir_orden`).
(2) Sección 3 (rework `confirmacion.py` + gate `_validar_cupo_de_paquete`) va ANTES de la Sección 5.
(3) `monto_por_empresa` puro en `pricing.py`; el caller resuelve la `TransporteTarifa` y pasa el número — `pricing.py` no importa `fleet`.
(4) `revertir_orden` idempotente, único emisor de void/refund de orden.
(5) Capture parcial: reintento acotado inline en `confirmar_captura` (Tarea 4.3/5.3); `conciliar_pagos` NUNCA captura (Tarea 6.1).
(6) Solo tarjeta en el checkout de orden (`payment_method_types=['card']`, Tarea 4.2). -->

---

## SECCIÓN 0 — Prerrequisitos

### Tarea 0.1 — Verificar que el terreno está listo

- [ ] **Paso 1:** `git log --oneline | grep -i "servicios removibles\|SP1 completado"` — confirmar que SP1 está mergeado en esta rama y que la sección de "paquete sin servicios removibles" también.
- [ ] **Paso 2:** `grep -rn "servicios_removidos\|removible\|ajuste_precio\|ReservaPaqueteServicioRemovido" backend/ frontend/src/` → **cero** (salvo migraciones históricas).
- [ ] **Paso 3:** `grep -rn "ReservaTransporte\|cargo_por_transporte" backend/` → **cero**. `DetalleTransporte` y `TransporteTarifa` existen.
- [ ] **Paso 4:** Gate completo (sqlite + Postgres) → verde antes de tocar nada.
- [ ] **Paso 5:** si algo falta, **para y reporta**. No arranques SP2 sobre terreno incompleto.

*(Sin commit — es una verificación.)*

---

## SECCIÓN 1 — Modelo `Orden`

### Tarea 1.1 — `bookings.Orden` + `Reserva.orden`

**Files:**
- Modify: `backend/apps/bookings/models.py`:
  ```python
  class Orden(models.Model):
      class Estado(models.TextChoices):
          ARMANDO = 'armando', 'Armando (reservas creadas)'
          AUTORIZANDO = 'autorizando', 'Autorizando (esperando confirmaciones del cliente)'
          AUTORIZADA = 'autorizada', 'Autorizada (lista para capturar)'
          CAPTURADA = 'capturada', 'Capturada (pagada)'
          CANCELADA = 'cancelada', 'Cancelada'

      sede = models.ForeignKey('tenancy.Sede', on_delete=models.PROTECT, related_name='ordenes')
      empresa_lider = models.ForeignKey('tenancy.Empresa', on_delete=models.PROTECT, related_name='ordenes_lideradas')
      paquete = models.ForeignKey('fleet.Paquete', on_delete=models.PROTECT, related_name='ordenes')
      checkout_id = models.UUIDField(null=True, blank=True, db_index=True)

      nombre_cliente = models.CharField(max_length=150, validators=[validar_nombre_persona])
      telefono_cliente = models.CharField(max_length=20, validators=[validar_telefono])
      correo_cliente = models.EmailField()

      moneda = models.CharField(max_length=3, choices=Reserva.Moneda.choices, default=Reserva.Moneda.MXN)
      forma_pago = models.CharField(max_length=10, choices=Reserva.FormaPago.choices, default=Reserva.FormaPago.COMPLETO)

      estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ARMANDO)
      creado_en = models.DateTimeField(auto_now_add=True)
      actualizado_en = models.DateTimeField(auto_now=True)

      # notificación combinada: se manda una sola vez
      notificada_en = models.DateTimeField(null=True, blank=True)

      class Meta:
          ordering = ['-creado_en']
          verbose_name = 'orden'
          verbose_name_plural = 'órdenes'

      TRANSICIONES = {
          'armando': {'autorizando', 'cancelada'},
          # 'autorizando' → 'capturada' directo también: un webhook puede llegar
          # antes de que confirmar_captura alcance a marcar 'autorizada'.
          'autorizando': {'autorizada', 'capturada', 'cancelada'},
          'autorizada': {'capturada', 'cancelada'},
          'capturada': set(),
          'cancelada': set(),
      }

      def clean(self):
          if self.forma_pago != Reserva.FormaPago.COMPLETO:
              raise ValidationError({'forma_pago': 'Las órdenes cruza-empresa solo admiten pago completo.'})
          if self.paquete_id and self.empresa_lider_id and self.paquete.empresa_lider_id != self.empresa_lider_id:
              raise ValidationError({'empresa_lider': 'Debe coincidir con la empresa líder del paquete.'})

      def transicionar(self, nuevo_estado):
          if nuevo_estado not in self.TRANSICIONES.get(self.estado, set()):
              raise ValidationError(f'Transición inválida: {self.estado} → {nuevo_estado}.')
          self.estado = nuevo_estado
  ```
  Y en `Reserva`:
  ```python
  orden = models.ForeignKey('bookings.Orden', on_delete=models.SET_NULL, null=True, blank=True, related_name='reservas')
  ```
- Create: migración `CreateModel('Orden')` + `AddField('Reserva', 'orden')`.
- Test: `backend/apps/bookings/tests.py::OrdenModelTest` — `forma_pago='anticipo'` → `ValidationError`; `transicionar` acepta `armando→autorizando` y `autorizando→capturada`, rechaza `armando→capturada` y cualquier salida de `capturada`/`cancelada`; `empresa_lider` distinta al paquete → error.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** modelos + migración.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `feat(bookings): modelo Orden (agrupa N reservas cruza-empresa)`.

### Tarea 1.2 — RLS de `Orden` (sede-scoped, con INSERT público)

**Files:**
- Create: migración RLS. `Orden` **no tiene `empresa_id`** — cruza empresas. Política:
  - **SELECT/UPDATE:** operador de plataforma ve todo (mismo escape que las demás
    políticas). Jefe/vendedora ve las órdenes de su `sede`
    (`sede_id = (SELECT sede_id FROM tenancy_empresa WHERE id = current_setting('app.current_empresa_id', true)::int)`).
  - **INSERT (`WITH CHECK`):** `CrearOrdenView` es `AllowAny` y no fija contexto de
    empresa. El `WITH CHECK` permite el INSERT cuando el `sede_id` de la fila existe
    (`EXISTS (SELECT 1 FROM tenancy_sede WHERE id = NEW.sede_id)`) — igual de laxo que
    lo que ya permite el INSERT público de `Reserva`, acotado aquí por la `sede` del
    slug. La `Orden` recién creada no se puede volver a leer desde esa misma request
    sin contexto (no hace falta: la respuesta se arma con los ids que ya tienes).
  - `Reserva.orden` no necesita política nueva.
- Modify: `backend/apps/tenancy/tests_rls.py` — **excepción documentada**:
  `bookings_orden` no lleva política `empresa_id` sino `sede`; añadir a la whitelist
  con comentario (igual que `tenancy_sede` / `tenancy_empresa`).
- Test: `# postgres-only` — dos sedes, una orden en cada una; el jefe de una empresa
  de la sede A ve la orden de A, no la de B; el operador ve las dos; un INSERT sin
  contexto de empresa (request pública) con `sede_id` válido **pasa**.

- [ ] **Paso 1: test que falla** (postgres).
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** migración RLS sede-scoped con `WITH CHECK` para el INSERT público.
- [ ] **Paso 4:** correr → verde; el guardarraíl de RLS pasa con la excepción.
- [ ] **Paso 5:** commit `feat(bookings): política RLS sede-scoped para Orden (INSERT público permitido)`.

### Tarea 1.3 — Función `estado_reservas_de_orden(orden_id)` (`SECURITY DEFINER`)

Una orden cruza N contextos RLS. El webhook de una empresa, bajo el RLS de esa
empresa, **no ve** las reservas hermanas de otras empresas — así que "¿ya se pagaron
todas?" daría `True` tras el primer webhook. Se resuelve con una función Postgres
`SECURITY DEFINER` acotada a **una** orden (no es un barrido — es el patrón del escape
explícito del panel de finanzas consolidado).

**Files:**
- Create: migración en `backend/apps/bookings/migrations/` (o `tenancy/`) con:
  ```sql
  CREATE OR REPLACE FUNCTION estado_reservas_de_orden(p_orden_id int)
  RETURNS TABLE (
    reserva_id int, empresa_id int, servicio_id int, estado text,
    monto_pagado numeric, monto_reembolsado numeric,
    stripe_payment_intent_id text, correo_cliente text
  )
  LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    SELECT id, empresa_id, servicio_id, estado, monto_pagado, monto_reembolsado,
           stripe_payment_intent_id, correo_cliente
    FROM bookings_reserva
    WHERE orden_id = p_orden_id
  $$;
  REVOKE ALL ON FUNCTION estado_reservas_de_orden(int) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION estado_reservas_de_orden(int) TO <rol de la app>;
  ```
  (El `<rol de la app>` es el mismo que usan las demás funciones `SECURITY DEFINER`
  del proyecto — revisar `fleet/migrations/*` de la expansión.)
- Create: `backend/apps/bookings/orden_lectura.py` — wrapper Python
  `reservas_de_orden(orden_id) -> list[RowDict]` que hace
  `connection.cursor().execute('SELECT * FROM estado_reservas_de_orden(%s)', [orden_id])`.
- Modify: `backend/apps/tenancy/tests_rls.py` — la función está en la whitelist de
  escapes explícitos permitidos.
- Test: `# postgres-only` — orden con reservas de 2 empresas; bajo el contexto de la
  Empresa 1, `orden.reservas.all()` ve 1 fila pero `reservas_de_orden(orden_id)` ve 2.

- [ ] **Paso 1: test que falla** (postgres — hoy la función no existe).
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** migración + wrapper.
- [ ] **Paso 4:** correr → verde.
- [ ] **Paso 5:** commit `feat(bookings): estado_reservas_de_orden (lectura cruza-empresa acotada a una orden)`.

### Gate Sección 1

- [ ] Suite verde sqlite + Postgres.
- [ ] Guardarraíl RLS verde (con la excepción de `Orden` documentada).
- [ ] Commit `docs(plan): SP2 Sección 1 cerrada`. **PARA y reporta.**

---

## SECCIÓN 2 — Paquete cruza-empresa y reparto

### Tarea 2.1 — `PaqueteServicio.clean()` acepta componentes de otra empresa de la misma sede

**Files:**
- Modify: `backend/apps/fleet/models.py::PaqueteServicio.clean()`:
  ```python
  def clean(self):
      super().clean()
      if self.paquete_id and self.servicio_id:
          if self.servicio.empresa.sede_id != self.paquete.sede_id:
              raise ValidationError({'servicio': 'El servicio debe pertenecer a una empresa de la misma sede que el paquete.'})
      # (ADR-005 Revisión 2: se elimina la regla de "misma empresa_lider").
  ```
- Modify: `docs/superpowers/specs/2026-09-06-ADR-005-...md` — marcar la parte de "bloqueado por `PaqueteServicio.clean`" como levantada (si no lo hizo ya la Revisión 2; verificar).
- Test: `backend/apps/fleet/tests.py` — paquete de la sede La Paz con `empresa_lider`=Empresa 1 acepta un componente de la Empresa 2 (misma sede); rechaza un componente de una empresa de otra sede.

- [ ] **Paso 1: test que falla** (hoy `clean()` rechaza el componente de otra empresa).
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** cambiar la regla.
- [ ] **Paso 4:** correr → verde. Confirmar que un paquete mono-empresa sigue siendo válido.
- [ ] **Paso 5:** commit `feat(fleet): paquetes cruza-empresa dentro de una sede (cierra ADR-005)`.

### Tarea 2.2 — `monto_por_empresa` (reparto puro)

**Files:**
- Modify: `backend/apps/payments/pricing.py`:
  ```python
  def monto_por_empresa(*, precio_paquete, componentes, moneda):
      """Reparte el precio fijo del paquete entre las cuentas de cada empresa.
      Regla (decisión del dueño 2026-09-07): cada componente de tipo conocido
      (transporte) va a su tarifa; la empresa líder (pesca) absorbe el residuo.

      `componentes`: lista de dicts
        {'empresa_id': int, 'es_lider': bool, 'monto_fijo': Decimal | None}
      donde `monto_fijo` es el precio de TransporteTarifa ya resuelto para los
      componentes de transporte, y None para el/los que absorben el residuo.
      Devuelve {empresa_id: Decimal}. Lanza ValueError si el residuo es negativo
      o si no hay exactamente un componente con monto_fijo=None (el líder)."""
      fijos = {c['empresa_id']: Decimal(c['monto_fijo']) for c in componentes if c['monto_fijo'] is not None}
      lideres = [c for c in componentes if c['monto_fijo'] is None]
      if len(lideres) != 1:
          raise ValueError('Debe haber exactamente un componente que absorba el residuo (la empresa líder).')
      residuo = Decimal(precio_paquete) - sum(fijos.values(), Decimal('0'))
      if residuo < 0:
          raise ValueError(f'El precio del paquete ({precio_paquete}) es menor que la suma de los montos fijos ({sum(fijos.values())}).')
      reparto = dict(fijos)
      reparto[lideres[0]['empresa_id']] = residuo.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
      return reparto
  ```
- Modify: `backend/apps/fleet/models.py::Paquete.clean()` — para un paquete cruza-empresa, validar `precio_en(moneda) ≥ (tarifa de transporte del componente en esa moneda)` en cada moneda configurada. (Necesita resolver la `TransporteTarifa`; si eso complica `clean()`, mover la validación a un `full_clean` del admin o a `PaqueteServicio.clean` con acceso al paquete.)
- Test: `backend/apps/payments/tests.py::MontoPorEmpresaTest` — paquete $5000, transporte $2700 → `{empresa1: 2300, empresa2: 2700}`; precio $2000 < transporte $2700 → `ValueError`; dos componentes sin `monto_fijo` → `ValueError`.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(payments): monto_por_empresa (reparto transporte-a-tarifa, pesca-el-resto)`.

### Gate Sección 2

- [ ] Suite verde sqlite + Postgres.
- [ ] Commit `docs(plan): SP2 Sección 2 cerrada`. **PARA y reporta.**

---

## SECCIÓN 3 — Confirmación de cupo por componente

### Tarea 3.1 — Separar "confirmar todo el paquete" de "confirmar mi componente"

**Files:**
- Modify: `backend/apps/bookings/cupo/confirmacion.py::reservar_cupo_al_confirmar`:
  - **Caso B (paquete mono-empresa):** solo si `reserva.paquete_id and reserva.orden_id is None`. Sigue iterando todos los componentes (como hoy, pero sin el filtro de "removidos" que ya se quitó).
  - **Caso D (nuevo — componente de una orden):** si `reserva.orden_id is not None`:
    ```python
    # Esta reserva es UN componente de una orden cruza-empresa. Reserva SOLO
    # su propio servicio, bajo su propia empresa. Los demás componentes los
    # confirman los webhooks de sus empresas.
    servicio = reserva.servicio
    estrategia = servicio.estrategia_cupo
    if estrategia == 'por_recurso_dia':
        bloquear_cupo(reserva.empresa_id, reserva.fecha, servicio_id=servicio.pk)
        motivo = evaluar_cupo(reserva.fecha, reserva.numero_personas, reserva.empresa,
                              excluir_pk=reserva.pk, estrategia_cupo='por_recurso_dia', servicio_id=servicio.pk)
        if motivo:
            raise SinCupoError(f'No hay cupo para {servicio.nombre} ({motivo}).')
    elif estrategia == 'por_noche':
        _asignar_cupo_hospedaje(reserva, servicio, es_componente=True)
    # bajo_demanda (transporte): nada que reservar
    ReservaPaqueteComponente.objects.create(
        reserva=reserva, servicio=servicio, empresa=reserva.empresa,
        estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
    )
    return
    ```
- Test: `backend/apps/bookings/tests.py::ConfirmacionComponenteOrdenTest` — reserva de pesca con `orden` reserva solo su cupo de pesca y crea un `ReservaPaqueteComponente`; reserva de transporte con `orden` no toca inventario y crea el componente; si el cupo de pesca está lleno → `SinCupoError`.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir Caso D; ajustar el gate del Caso B.
- [ ] **Paso 4:** correr → verde. **Correr toda la suite de bookings** — Caso B no debe cambiar de comportamiento para paquetes mono-empresa.
- [ ] **Paso 5:** commit `feat(bookings): confirmar cupo por componente para reservas de una orden`.

### Tarea 3.2 — Gate de `orden_id` en `Reserva.clean()`

La reserva **líder** de una orden lleva `paquete` seteado. Sin gate, `Reserva.clean()`
correría `_validar_cupo_de_paquete` (itera todos los componentes, incluido el de otra
empresa → validación de cupo cruza-empresa bajo el RLS de la líder). Mismo problema que
la Tarea 3.1 pero en `clean()`, no en `reservar_cupo_al_confirmar`.

**Files:**
- Modify: `backend/apps/bookings/models.py::Reserva.clean()` (~línea 683):
  ```python
  if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
      if self.orden_id:
          # Componente de una orden cruza-empresa: valida SOLO su servicio.
          # El paquete entero lo cubren los webhooks de cada empresa.
          if self.servicio_id:
              estrategia = self.servicio.estrategia_cupo
              if estrategia != 'bajo_demanda':
                  validar_cupo_diario(
                      self.fecha, self.numero_personas, self.empresa,
                      excluir_pk=self.pk, estrategia_cupo=estrategia, servicio_id=self.servicio_id,
                  )
      elif self.paquete_id:
          _validar_cupo_de_paquete(self)
      elif self.servicio_id and self.servicio.estrategia_cupo == 'por_noche':
          _validar_cupo_hospedaje(self)
      else:
          ... (rama actual sin cambios)
  ```
- Modify: `backend/apps/bookings/models.py::Reserva._validar_consistencia_de_empresa`
  — el bucle actual ya no incluye `paquete` para las reservas no-líder (solo la líder
  lo lleva). Confirmar que para la reserva líder (paquete de la sede, empresa_lider ==
  su empresa) sigue pasando; para las demás, `paquete_id` es None y la validación de
  paquete se salta sola. **No hace falta relajar nada** si solo la líder lleva
  `paquete` (ver Tarea 4.1).
- Test: `backend/apps/bookings/tests.py` — la reserva líder de una orden (con `paquete`
  **y** `orden`) valida solo su cupo de pesca; una reserva de transporte de la orden
  (solo `orden`, `bajo_demanda`) no valida cupo; ninguna dispara
  `_validar_cupo_de_paquete`.

- [ ] **Paso 1: test que falla** (hoy la líder dispara `_validar_cupo_de_paquete`).
- [ ] **Paso 2:** correr → falla.
- [ ] **Paso 3:** añadir el gate de `orden_id` en `clean()`.
- [ ] **Paso 4:** correr toda la suite de bookings → verde (paquetes mono-empresa intactos).
- [ ] **Paso 5:** commit `fix(bookings): la reserva de una orden valida solo su cupo, no el del paquete`.

### Gate Sección 3

- [ ] Suite verde sqlite + Postgres.
- [ ] Commit `docs(plan): SP2 Sección 3 cerrada`. **PARA y reporta.**

---

## SECCIÓN 4 — API de órdenes

### Tarea 4.1 — `POST /api/<sede_slug>/ordenes/` (crear orden + reservas)

**Files:**
- Modify: `backend/apps/payments/views.py` — `CrearOrdenView(APIView)` (`AllowAny`). Body: `checkout_id`, `paquete` (slug), datos del cliente, `moneda`, `deslinde_aceptado`, `deslinde_nombre`, `ref` (opcional), y por cada componente los datos que necesite (para el de transporte: `tipo_traslado`, `punto_encuentro`|`direccion_personalizada`, `fecha`, `hora`, `fecha_regreso`; para pesca: `fecha`, `hora`, `numero_personas`).
  - Valida que el paquete sea cruza-empresa (si es mono-empresa, va por el flujo de `Reserva` normal, no por órdenes → 400 con mensaje claro).
  - `forma_pago` forzado a `completo`.
  - Dentro de **una** `transaction.atomic`:
    - Crea la `Orden` (`armando`). El INSERT de `Orden` no tiene contexto de empresa
      (vista `AllowAny`); lo permite el `WITH CHECK` sede-scoped de la Tarea 1.2.
    - Por cada componente, una `Reserva` (`pendiente_pago`, `orden=<orden>`,
      `empresa=<empresa del componente>`, `servicio=<componente>`, `canal_origen='web'`),
      **iterando `scope.con_empresa(componente.empresa)` para cada escritura** — la
      Constraint 3 prohíbe depender del filtro del ORM. **Solo la reserva de la
      `empresa_lider` lleva `paquete` seteado** (ponerlo en otra dispara
      `_validar_consistencia_de_empresa`); las demás llevan solo `orden` + `servicio`.
      Deslinde copiado a cada una. Para el componente de transporte, crea también su
      `DetalleTransporte` bajo `scope.con_empresa(empresa_2)`.
    - `full_clean()` en cada reserva antes de `save()`. **No** ocupa cupo.
    - `ref` solo a la `Reserva` de la `empresa_lider` (§9 del spec).
  - Reusa la orden por `checkout_id` si ya existe en `armando`/`autorizando`; una
    `capturada`/`cancelada` con ese `checkout_id` se ignora (orden nueva).
  - Devuelve `{orden_id, checkout_id, estado, reservas: [{empresa_slug, servicio, ...}]}`.
- Modify: `backend/apps/payments/urls.py` + `config/urls.py` — ruta `<slug:sede_slug>/ordenes/`. (`tenancy.Sede.slug` existe, `unique`.)
- Modify: `frontend/src/lib/api.ts` — `crearOrden(sedeSlug, payload)`.
- Test: `backend/apps/payments/tests.py::CrearOrdenTest` — crea orden + 2 reservas con sus empresas (postgres: verifica que las 2 escrituras pasan RLS vía `scope.con_empresa`); solo la líder lleva `paquete`; paquete mono-empresa → 400; deslinde faltante → 400; reutiliza por `checkout_id` en `armando`, ignora uno `capturada`.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(payments): POST /api/<sede>/ordenes/`.

### Tarea 4.2 — `apps/payments/ordenes.py` — crear N PaymentIntents

**Files:**
- Create: `backend/apps/payments/ordenes.py`:
  ```python
  """Orquestación de una Orden cruza-empresa: crear N PaymentIntents en modo
  manual capture (uno por empresa), capturarlos todos, o revertir todo.
  El dinero se calcula en pricing.monto_por_empresa; aquí solo se mueve."""

  CAPTURA_REINTENTOS = 3

  def crear_pagos_orden(orden, reparto: dict) -> list[dict]:
      """Idempotente. `reparto` = {empresa_id: Decimal} de pricing.monto_por_empresa.
      Crea (o reutiliza) un PaymentIntent por cada Reserva de la orden, en la
      cuenta Stripe de su empresa, por su monto del reparto, con
      capture_method='manual' y payment_method_types=['card'] (SOLO tarjeta —
      OXXO/SPEI no soportan auth/capture). metadata {orden_id, reserva_id,
      empresa_id}. idempotency_key = f'orden-{orden.id}-{empresa_id}-crear'.
      Devuelve [{empresa_slug, monto, client_secret, publishable_key}].
      Fallo parcial (creó el de la empresa 1, la llamada de la empresa 2
      revienta): deja los creados, propaga el error; un reintento crea los que
      faltan y reutiliza los existentes. 409 si la orden ya está
      capturada/cancelada."""
      ...

  def confirmar_captura(orden) -> None:
      """Lee los N PaymentIntents (por estado_reservas_de_orden → stripe_payment_intent_id).
      Si alguno NO está 'requires_capture' → revertir_orden(orden, 'una autorización
      no se completó'). Si todos → captura los N; si la captura de alguno falla,
      reintenta ESA hasta CAPTURA_REINTENTOS con espera corta; si agota →
      revertir_orden(orden, 'no se pudo capturar <empresa>'). Idempotente a nivel
      operación: un PI ya 'succeeded' se salta (traga PaymentIntentUnexpectedState),
      no se re-captura. NO marca orden.capturada — eso lo hace el webhook al
      recibir cada payment_intent.succeeded."""
      ...

  def revertir_orden(orden, motivo: str) -> None:
      """Compensación idempotente. Por cada PaymentIntent de la orden
      (vía estado_reservas_de_orden):
        - 'requires_capture'/'requires_confirmation'/'requires_action' → cancel (void)
        - 'succeeded' → refund total (idempotency_key = f'orden-{orden.id}-{empresa_id}-refund')
        - 'canceled'/'refunded'/ya reembolsada → nada
      Marca las reservas afectadas (reembolsada / motivo_cancelacion / estado
      cancelada) y orden.transicionar('cancelada'). Segura para reintentos."""
      ...
  ```
  Usa `configurar_stripe(empresa)` por empresa. Lee las reservas hermanas con
  `estado_reservas_de_orden(orden_id)` (Tarea 1.3) — nunca `orden.reservas.all()` bajo
  el RLS de una empresa.
- Test: `backend/apps/payments/tests.py::OrdenesModuloTest` (Stripe mockeado) —
  `crear_pagos_orden` crea 2 intents `capture_method=manual` + `card` en 2 cuentas por
  los montos del reparto; segunda llamada no crea nuevos; fallo en la 2ª cuenta deja la
  1ª y propaga; `revertir_orden` hace void de `requires_capture` y refund de `succeeded`,
  idempotente en segunda llamada; `confirmar_captura` con un PI ya `succeeded` no
  revienta.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(payments): módulo de orquestación de órdenes (crear/capturar/revertir)`.

### Tarea 4.3 — `POST /api/<sede_slug>/ordenes/<id>/crear-pago/` y `.../confirmar-captura/`

**Files:**
- Modify: `backend/apps/payments/views.py`:
  - `CrearPagoOrdenView` — resuelve el reparto: para cada componente de transporte,
    resuelve su fila de `TransporteTarifa` (`resolver_tarifa_transporte`, de SP1) →
    `monto_fijo`; para la líder, `monto_fijo=None`. Llama
    `pricing.monto_por_empresa(precio_paquete=..., componentes=..., moneda=...)`, luego
    `ordenes.crear_pagos_orden(orden, reparto)`, `orden.transicionar('autorizando')`,
    devuelve la lista de pagos. Idempotente. 409 si `capturada`.
  - `ConfirmarCapturaOrdenView` — llama `ordenes.confirmar_captura(orden)`. Devuelve
    `{estado}` (el estado real lo pone el webhook; este endpoint puede devolver
    `autorizada` mientras llega el `succeeded`, o `cancelada` si se revirtió). Si
    `cancelada`, incluye el motivo.
  - `GetOrdenView` (`GET /api/<sede_slug>/ordenes/<id>/` o `?checkout_id=`) — para que
    el frontend **reanude** tras recarga: devuelve `{estado, reservas: [{empresa_slug,
    servicio, pago: {estado_pi, client_secret, publishable_key, monto}}]}` para que el
    checkout arranque desde el primer pago que no esté `requires_capture`. Lee con
    `estado_reservas_de_orden`.
- Modify: `frontend/src/lib/api.ts` — `crearPagoOrden`, `confirmarCapturaOrden`, `getOrden`.
- Test: `backend/apps/payments/tests.py` — flujo feliz (crear-pago → 2 client_secrets →
  confirmar-captura con ambos `requires_capture` → 2 webhooks → `capturada`, 2 reservas
  `pagada`); flujo fallo (uno `requires_confirmation` → `revertir_orden`, void del otro,
  `cancelada`, 0 reservas pagadas); `getOrden` tras autorizar solo el 1º devuelve el
  cursor en el 2º pago.

- [ ] **Paso 1: test que falla.**
- [ ] **Paso 2 → 5:** ciclo. Commit `feat(payments): endpoints crear-pago y confirmar-captura de una orden`.

### Gate Sección 4

- [ ] Suite verde sqlite + Postgres.
- [ ] `check --deploy` verde.
- [ ] Prueba manual (runserver + curl, Stripe en modo test si hay llaves; si no, los tests con mock bastan).
- [ ] Commit `docs(plan): SP2 Sección 4 cerrada`. **PARA y reporta.**

---

## SECCIÓN 5 — Webhook orden-aware, compensación y notificación

### Tarea 5.1 — El webhook de cada empresa marca su reserva y evalúa la orden

**Files:**
- Modify: `backend/apps/payments/services.py::aplicar_pago_exitoso` — tras marcar `reserva.pagada` y correr `reservar_cupo_al_confirmar` (Caso D para reservas con `orden`):
  ```python
  if reserva.orden_id:
      orden = Orden.objects.select_for_update().get(pk=reserva.orden_id)
      # NO orden.reservas.all() — bajo el RLS de esta empresa solo vería su
      # propia reserva. estado_reservas_de_orden salta RLS, acotado a esta orden.
      filas = reservas_de_orden(orden.pk)  # wrapper de la función SECURITY DEFINER
      todas_pagadas = all(f['estado'] in ('pagada', 'asignada') for f in filas)
      if todas_pagadas:
          if orden.estado != Orden.Estado.CAPTURADA:
              orden.transicionar('capturada'); orden.save()
          if orden.notificada_en is None:
              notificar_orden_pagada(orden)   # nunca lanza
              orden.notificada_en = timezone.now(); orden.save(update_fields=['notificada_en'])
  ```
  Corre dentro de `transaction.atomic` + `select_for_update` sobre la `Orden` (para que
  dos webhooks simultáneos no dupliquen el cierre/notificación).
- Test: `backend/apps/payments/tests.py` (postgres — la función `SECURITY DEFINER`
  necesita Postgres) — dos webhooks bajo el RLS de cada empresa → tras el **segundo**
  (no el primero), `Orden.capturada` + `notificada_en`; un tercer webhook duplicado no
  re-notifica.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(payments): el webhook cierra la orden al pagarse su última reserva`.

### Tarea 5.2 — Camino de compensación: cupo lleno mientras el cliente pagaba

**Files:**
- Modify: `backend/apps/payments/services.py` — cuando `reservar_cupo_al_confirmar` lanza `SinCupoError` para una reserva **con `orden`**: en vez del reembolso simple de hoy, reembolsar **su** cargo y llamar `ordenes.revertir_orden(orden, 'sin cupo en <servicio>')` (que hace void/refund del resto). La reserva queda `cancelada` + `reembolsada`; la orden `cancelada`.
- Test: `backend/apps/payments/tests.py::CompensacionOrdenTest` — 2 auths OK, capture de ambas; al confirmar cupo de pesca falla → refund de las 2, orden `cancelada`, las 2 reservas `cancelada`+`reembolsada`.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(payments): compensación de orden cuando un componente se queda sin cupo`.

### Tarea 5.3 — Captura parcial (una captura falla tras la otra)

**Files:**
- Modify: `backend/apps/payments/ordenes.py::confirmar_captura` — si al capturar la empresa k falla (`CardError` u otro) tras haber capturado 1..k-1: reintentar la captura de k hasta `CAPTURA_REINTENTOS` (p.ej. 3, con espera corta). Si agota → `revertir_orden` (que ahora hace refund de las ya capturadas) + alerta a la vendedora (log de error claro + la orden queda `cancelada` visible en `revisar_ordenes`).
- Test: `backend/apps/payments/tests.py` — mock: captura 1 OK, captura 2 falla 3 veces → refund de 1, orden `cancelada`.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(payments): reintento acotado de captura y refund si agota`.

### Tarea 5.4 — `notificar_orden_pagada` (correo combinado)

**Files:**
- Modify: `backend/apps/notifications/services.py` — `notificar_orden_pagada(orden)`:
  - Lee los componentes con `reservas_de_orden(orden.pk)` (función `SECURITY DEFINER`)
    — desde `aplicar_pago_exitoso` el contexto RLS es de una sola empresa y
    `orden.reservas` no vería todo.
  - **Correo:** uno solo al `orden.correo_cliente`, que menciona los N componentes
    (pesca: fecha/hora; traslado: tipo/punto de encuentro). Plantilla nueva de correo
    (HTML/text), no de Meta.
  - **WhatsApp:** por cada reserva de la orden, el mismo `notificar_reserva_pagada` de
    hoy (plantilla de Meta ya aprobada por empresa). Para leer los datos de cada
    reserva individual, resolverla bajo `scope.con_empresa(fila['empresa_id'])`.
  - **Nunca lanza** (el cobro ya ocurrió; una notificación caída no puede hacer que
    Stripe reintente).
- Test: `backend/apps/notifications/tests.py` (postgres) — un correo combinado con los
  2 componentes; 2 llamadas a WhatsApp (una por empresa); si el correo falla, no propaga.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(notifications): correo combinado de orden + WhatsApp por empresa`.

### Gate Sección 5

- [ ] Suite verde sqlite + Postgres.
- [ ] Repaso: cada rama de la tabla de errores del spec §6 tiene test.
- [ ] Commit `docs(plan): SP2 Sección 5 cerrada`. **PARA y reporta.**

---

## SECCIÓN 6 — Red de seguridad

### Tarea 6.1 — `conciliar_pagos` orden-aware

**Files:**
- Modify: `backend/apps/payments/management/commands/conciliar_pagos.py` — para reservas `pendiente_pago` con `orden`:
  - Resolver a nivel orden: consultar los N PaymentIntents.
  - Si los N `succeeded` → aplicar los N (idempotente, como el webhook).
  - Si unos `succeeded` y otros no, y pasó `ORDEN_TIMEOUT_AUTORIZACION` (24 h desde `orden.actualizado_en`) → `revertir_orden(orden, 'timeout de autorización')`.
  - Si los N `requires_capture`/`requires_confirmation` y pasó el timeout → `revertir_orden`. **`conciliar_pagos` NUNCA captura** — capturar es acción del cliente en `confirmar-captura`; conciliar solo aplica lo ya `succeeded` o revierte.
  - Lee las reservas hermanas con `reservas_de_orden(orden.pk)` (Tarea 1.3), no con `orden.reservas` (conciliar corre con `scope.como_operador_plataforma()` en un comando, pero la función `SECURITY DEFINER` es el patrón consistente con el webhook).
- Test: `backend/apps/payments/tests.py::ConciliarOrdenesTest` — webhook perdido de ambas (ambas `succeeded` en Stripe) → conciliar aplica las 2, orden `capturada`; una `succeeded` una `requires_confirmation` + timeout → `revertir_orden`; idempotente en segunda vuelta.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(payments): conciliar_pagos entiende órdenes`.

### Tarea 6.2 — `manage.py revisar_ordenes`

**Files:**
- Create: `backend/apps/payments/management/commands/revisar_ordenes.py` — lista órdenes en `armando`/`autorizando`/`autorizada` más viejas que N horas (default 2), con el estado de cada PaymentIntent, para que la vendedora las vea. `--dry-run` por defecto informativo; sin flags no cambia nada (solo `conciliar_pagos` actúa).
- Test: `backend/apps/payments/tests.py` — lista una orden atascada, no toca una `capturada`.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(payments): comando revisar_ordenes`.

### Gate Sección 6

- [ ] Suite verde sqlite + Postgres.
- [ ] Commit `docs(plan): SP2 Sección 6 cerrada`. **PARA y reporta.**

---

## SECCIÓN 7 — Admin de órdenes

### Tarea 7.1 — `OrdenAdmin`

**Files:**
- Modify: `backend/apps/bookings/admin.py` — `OrdenAdmin`:
  - Solo lectura para la vendedora (sin add/change/delete). `list_display`: cliente, paquete, sede, estado, creado, total.
  - Inline (readonly) de las `Reserva` de la orden, con enlace a cada una y su estado + su cargo (leído de Stripe o del campo `stripe_payment_intent_id` + una columna calculada).
  - Acción "Cancelar orden (revertir pagos pendientes)" — para jefe/operador; llama `ordenes.revertir_orden(orden, 'cancelada desde el admin')`.
  - `SIDEBAR` de Unfold — alta del modelo (cuidado con el string, tumba el admin).
- Modify: `backend/apps/bookings/admin.py::ReservaAdmin` — columna/enlace a `orden` cuando la reserva tiene una.
- Modify: `backend/apps/bookings/setup_roles.py` — `Orden` view-only para `Vendedora`.
- Test: `backend/apps/bookings/tests.py` — la vendedora ve la lista de órdenes (solo lectura); la acción "cancelar" no está para la vendedora; el jefe puede cancelar.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(bookings): admin de Orden (solo lectura + cancelar)`.

### Gate Sección 7

- [ ] Suite verde sqlite + Postgres.
- [ ] `/admin/` abre sin romperse (revisión del agente).
- [ ] Commit `docs(plan): SP2 Sección 7 cerrada`. **PARA y reporta.**

---

## SECCIÓN 8 — Frontend del checkout de orden

### Tarea 8.1 — Detección de paquete cruza-empresa y modo orden

**Files:**
- Modify: `frontend/src/lib/api.ts` — el fetch del paquete ya trae sus componentes; añadir un flag `es_cruza_empresa` (o derivarlo de que los componentes tengan >1 `empresa_slug`).
- Modify: `frontend/src/components/paquete-card.tsx` / `checkout-view.tsx` — si el paquete es cruza-empresa, el "Reservar" lleva al checkout de orden (`paquete-checkout.tsx`), no al de reserva normal.
- Test: `tsc` · `lint` · `build`.

- [ ] **Paso 1 → 3:** ciclo. Commit `feat(frontend): detecta paquete cruza-empresa`.

### Tarea 8.2 — `paquete-checkout.tsx` — un formulario, N pagos en secuencia

**Files:**
- Create: `frontend/src/components/paquete-checkout.tsx` — client component:
  1. **Un solo** formulario: datos del cliente + los datos de cada componente (fecha/hora de pesca; tipo de traslado + hospedaje + fechas) + **un** deslinde.
  2. Al enviar: `crearOrden(sedeSlug, payload)` → guarda `checkout_id` + `ordenId` en `sessionStorage` → `crearPagoOrden(ordenId)` → recibe `[{empresa_slug, monto, client_secret, publishable_key}]`.
  3. Monta **un `<Elements>`/`<PaymentElement>` a la vez** (no los N juntos), cada uno con su `publishable_key` (`loadStripe(pk)` — se cachea por key) y su `client_secret`. **Solo tarjeta**: el PaymentIntent ya viene con `payment_method_types=['card']`, así que el Element solo muestra tarjeta. Encabezado: *"Paso 1 de 2 — Pesca (Empresa 1): $X"*, *"Paso 2 de 2 — Traslado (Empresa 2): $Y"*. Cada `stripe.confirmPayment({..., redirect: 'if_required'})` con el PaymentIntent en modo manual deja el intent en `requires_capture` (no cobra aún). Al pasar de un paso al siguiente, desmontar el `<Elements>` anterior.
  4. Tras el último paso: `confirmarCapturaOrden(ordenId)`. Pantalla de éxito (con el resumen de los N componentes) o de fallo (*"No se pudo completar el pago del traslado. No se te cobró nada."*).
  5. **Reanudar tras recarga/cierre y reapertura:** al montar, si hay `ordenId` en `sessionStorage`, `getOrden(sedeSlug, ordenId)` → si `capturada`/`cancelada`, mostrar esa pantalla; si `autorizando`, saltar el formulario y arrancar la secuencia de pagos desde el primer paso cuyo `pago.estado_pi` no sea `requires_capture`. Los pasos ya autorizados no se repiten.
  6. Si el cliente nunca vuelve: la orden queda `autorizando` y `conciliar_pagos`/`revisar_ordenes` la limpia tras el timeout.
- Reutiliza el bloque de datos del cliente, el deslinde y el `PaymentElement` de `checkout-view.tsx` (extraer a compartidos si están inline).
- Modify: dictionaries — bloque `paqueteCheckout.*` (pasos, textos de éxito/fallo/reanudar).
- Test: `tsc` · `lint` · `build`.

- [ ] **Paso 1 → 3:** ciclo. Commit `feat(frontend): checkout de paquete cruza-empresa (tarjeta, N pagos en secuencia, reanudable)`.

### Gate Sección 8

- [ ] Frontend `lint` · `tsc --noEmit` · `build` verdes.
- [ ] El agente arranca dev + backend con llaves de Stripe test y hace **una** compra completa del paquete Pesca + Traslado de prueba (2 confirmaciones → captura → éxito). Si no hay llaves test, deja documentado el paso para que el dueño lo pruebe.
- [ ] Commit `docs(plan): SP2 Sección 8 cerrada`. **PARA y reporta.**

---

## SECCIÓN 9 — Deslinde ampliado

### Tarea 9.1 — Un solo deslinde ampara a todas las empresas

**Files:**
- Modify: `frontend/src/app/[lang]/deslinde/` (texto) + `dictionaries/{es,en}.json` — ampliar el texto del deslinde para cubrir **cualquier actividad y cualquier empresa** de la sede (pesca, traslado, y a futuro los servicios de La Ventana), no solo "pesca deportiva". Mantener la cláusula 8(d) (registro del texto aceptado).
- Modify: `backend/apps/bookings/models.py` — `deslinde_version` sube a la versión nueva (constante). Al crear las reservas de una orden, el mismo `deslinde_*` (aceptado, nombre, fecha, ip, version) se copia a **cada** `Reserva` — cada empresa tiene su constancia con el mismo texto.
- Test: `backend/apps/bookings/tests.py` — una orden crea N reservas todas con el mismo `deslinde_version` y los mismos campos de deslinde; `full_clean` de cada una pasa.
- **Texto final pendiente de visto bueno del dueño / abogado** — dejar el texto redactado y marcado en el PR para que el dueño lo apruebe antes de lanzar. La estructura (una casilla, copia a N reservas) no espera.

- [ ] **Paso 1 → 5:** ciclo. Commit `feat(deslinde): un solo deslinde ampara a todas las empresas de la sede`.

### Gate Sección 9

- [ ] Suite verde sqlite + Postgres.
- [ ] Frontend verde.
- [ ] Commit `docs(plan): SP2 Sección 9 cerrada`. **PARA y reporta.**

---

## SECCIÓN 10 — Cierre SP2

- [ ] **10.1** `manage.py test apps config` verde en sqlite Y Postgres (drop antes).
- [ ] **10.2** `check --deploy --fail-level WARNING` (production settings + env relleno).
- [ ] **10.3** Frontend `lint` · `tsc --noEmit` · `build` verdes.
- [ ] **10.4** Repaso de diffs: reparto solo en `pricing.monto_por_empresa`; void/refund de orden solo en `ordenes.revertir_orden`; el webhook es la única fuente de verdad; `Orden` con RLS sede-scoped + excepción documentada en el guardarraíl; idempotency_key en toda operación de Stripe de SP2.
- [ ] **10.5** Prueba end-to-end manual (llaves Stripe test): compra del paquete Pesca + Traslado con éxito; compra donde el 2º pago se rechaza (tarjeta `4000000000000002`) → void del 1º, nada cobrado; webhook perdido → `conciliar_pagos` cierra la orden.
- [ ] **10.6** Actualizar `backend/CLAUDE.md` — sección nueva "Órdenes cruza-empresa": `Orden`, modelo B de cobro, `ordenes.py`, `revertir_orden`, `conciliar_pagos`/`revisar_ordenes` orden-aware, notificación combinada, `forma_pago=completo`. Actualizar `frontend/CLAUDE.md` — checkout de paquete cruza-empresa.
- [ ] **10.7** Actualizar `docs/superpowers/specs/2026-09-06-ADR-005-...md` — Estado: IMPLEMENTADO, con la fecha y las desviaciones.
- [ ] **10.8** Sembrar en local el paquete "Pesca + Traslado" (Empresa 1 líder + componente de la Empresa 2) con su `precio_paquete`. Añadir a `seed_local_demo`.
- [ ] **10.9** Memoria: `plan-transporte-multi-empresa` → SP1 y SP2 hechos; mover a `pendientes-manuales-produccion` los pasos de producción:
  - **Cada empresa** registra su webhook endpoint en SU dashboard de Stripe apuntando a `/api/<empresa_slug>/stripe/webhook/` y guarda el signing secret en `Empresa.stripe_webhook_secret`. Sin esto, el cierre de orden depende solo de `conciliar_pagos` (con retraso).
  - Crear el `Paquete` "Pesca + Traslado" real (líder Empresa 1 + componente Empresa 2) y su `precio_paquete`; verificar `precio_paquete ≥` tarifa de transporte.
  - Texto final del deslinde ampliado aprobado por el dueño / abogado.
- [ ] **10.10** Resumen para el dueño: migraciones y orden; qué se carga a mano; qué quedó pendiente (texto del deslinde, plantilla de correo combinado si quiere ajustarla, decisión de si `redondo_actividad` lleva tramo por tamaño).
- [ ] **10.11** Commit `docs(plan): SP2 completado`. **PARA.** Integración de la rama (PR a `main` una vez `fix/expansion-multi-sede-hallazgos` esté dentro) la decide el dueño.

---

## Autorrevisión (al terminar cada sección)

1. **¿El test falla ANTES de implementar?**
2. **¿Postgres, no solo sqlite?** RLS de `Orden`, locks de cupo, constraints reales.
3. **¿Dropeaste `test_pescadeportiva_test` antes del run de Postgres?**
4. **¿El commit tiene SOLO los archivos de esa tarea?**
5. **¿Rompiste algún test existente?** Secciones 3 (confirmacion.py) y 5 (services.py) son las de mayor riesgo de regresión sobre el flujo de pago mono-empresa.
6. **¿Alguna operación de Stripe sin `idempotency_key`?** En SP2 todas la llevan.
7. **¿Algún cálculo de dinero fuera de `apps/payments/pricing.py`?**
8. **El camino de compensación (`revertir_orden`) — ¿es idempotente de verdad?** Llámalo dos veces en el test y verifica que no reembolsa dos veces.
