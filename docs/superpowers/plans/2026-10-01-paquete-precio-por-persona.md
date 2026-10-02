# Paquete con precio por persona — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un `Paquete` pueda cobrarse por persona (`precio × personas`) en vez de como total fijo, sin cambiar los paquetes existentes.

**Architecture:** Un booleano `Paquete.precio_por_persona` (default `False`) y un único método `Paquete.precio_total_en(moneda, personas)` que reemplaza los tres lugares donde hoy se lee `precio_en(moneda)` como total: la reserva de una empresa (`CrearPagoView`), la orden cruza-empresa (`CrearPagosOrdenView`) y `pricing.precio_paquete_total`. En un paquete por persona todos los servicios van con el mismo número de personas, así que el total es `ancla × numero_personas`.

**Tech Stack:** Django 5 / DRF, tests con `OperadorTestCase`/`TestCase`, SQLite y Postgres (CI con rol `ci_rls`).

**Spec:** `docs/superpowers/specs/2026-10-01-paquetes-por-persona-y-salidas-multidia-design.md` (sección "Cambio 1").

## Global Constraints

- Sin cambios al comportamiento de paquetes existentes: `precio_por_persona` default `False`.
- El servidor calcula siempre el total; el cliente nunca manda un monto.
- Pesos y dólares nunca se suman ni se convierten en código: cada ancla (MXN y USD) se carga a mano.
- Textos de cara al cliente: "retenido" y "retención", nunca "autorizado".
- Un paquete de dos empresas nunca admite anticipo (no cambia).
- Probar en SQLite y en Postgres antes de cerrar (`backend/CLAUDE.md`, "Correr la suite contra Postgres").
- Frontend: por la regla de diseño del proyecto, **no se escribe código de UI hasta que el dueño apruebe la explicación** (Task 6).
- Python del venv: `C:/Users/kkjf/desarrollo/sistema-pescadeportiva/backend/venv/Scripts/python.exe` (el worktree no tiene venv propio). Todos los comandos corren desde `backend/` del worktree.

## File Map

| Archivo | Responsabilidad |
|---|---|
| `backend/apps/fleet/models.py` | Campo `precio_por_persona`, método `precio_total_en`, validación contra transporte por tamaño de grupo |
| `backend/apps/fleet/migrations/0038_paquete_precio_por_persona.py` | Migración del campo |
| `backend/apps/fleet/admin.py` | Mostrar el campo en la lista de paquetes |
| `backend/apps/fleet/serializers.py` | Exponer `precio_por_persona` en el catálogo público |
| `backend/apps/payments/pricing.py` | `precio_paquete_total` usa `precio_total_en` |
| `backend/apps/payments/views.py` | `CrearPagoView` y `CrearPagosOrdenView` cobran `ancla × personas`; `CrearOrdenView` exige mismas personas |
| `backend/apps/bookings/serializers.py` | Una reserva de paquete por persona exige mismas personas en todos los servicios |

<!-- arch-critic: omitido a propósito (cambio aditivo de bajo riesgo; el dueño reserva Opus para el orquestador) -->

---

### Task 1: Campo, método de precio y migración

**Files:**
- Modify: `backend/apps/fleet/models.py` (clase `Paquete`, junto a `precio_ancla_usd`; método junto a `precio_en`)
- Create: `backend/apps/fleet/migrations/0038_paquete_precio_por_persona.py` (la genera `makemigrations`)
- Modify: `backend/apps/fleet/admin.py:166`
- Test: `backend/apps/fleet/tests_paquetes.py` (clase nueva al final del archivo)

**Interfaces:**
- Produces: `Paquete.precio_por_persona: bool`; `Paquete.precio_total_en(moneda: str, personas: int = 1) -> Decimal | None`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Agregar al final de `backend/apps/fleet/tests_paquetes.py` (ya importa `Decimal`, `Paquete`, `PaqueteServicio`, `Servicio`, `Empresa`, `Sede`, `OperadorTestCase`, `ValidationError`); agregar también `TransporteTarifa` al import de `apps.fleet.models`:

```python
class PaquetePrecioPorPersonaTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa PPP', slug='empresa-ppp')

    def _paquete(self, **extra):
        datos = dict(
            sede=self.sede, empresa_lider=self.empresa, nombre='Paquete PPP', slug='paquete-ppp',
            precio_ancla=Decimal('45000.00'), precio_ancla_usd=Decimal('2500.00'),
        )
        datos.update(extra)
        return Paquete.objects.create(**datos)

    def test_por_defecto_el_precio_es_un_total_fijo(self):
        paquete = self._paquete()
        self.assertFalse(paquete.precio_por_persona)
        self.assertEqual(paquete.precio_total_en('MXN', 3), Decimal('45000.00'))

    def test_por_persona_multiplica_en_mxn_y_usd(self):
        paquete = self._paquete(precio_por_persona=True)
        self.assertEqual(paquete.precio_total_en('MXN', 3), Decimal('135000.00'))
        self.assertEqual(paquete.precio_total_en('USD', 2), Decimal('5000.00'))

    def test_sin_precio_en_la_moneda_devuelve_none(self):
        paquete = self._paquete(precio_por_persona=True, precio_ancla_usd=None)
        self.assertIsNone(paquete.precio_total_en('USD', 2))

    def _traslado(self, precio):
        servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Traslado PPP', slug='traslado-ppp', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta', capacidad_maxima=14,
        )
        TransporteTarifa.objects.create(
            empresa=self.empresa, tipo_traslado='redondo_aeropuerto', zona='', personas_min=1,
            personas_max=None, precio=Decimal(precio), precio_usd=Decimal('280.00'),
        )
        return servicio

    def test_validar_configuracion_revisa_cada_tamano_de_grupo(self):
        servicio = self._traslado('5000.00')
        paquete = self._paquete(
            precio_por_persona=True, precio_ancla=Decimal('4000.00'), precio_ancla_usd=Decimal('300.00'),
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, personas_incluidas=2)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertTrue(any('tarifa de transporte' in m for m in ctx.exception.messages))

    def test_validar_configuracion_acepta_un_precio_que_cubre_el_traslado(self):
        servicio = self._traslado('3500.00')
        paquete = self._paquete(precio_por_persona=True)
        PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, personas_incluidas=2)
        paquete.validar_configuracion()
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `PY=C:/Users/kkjf/desarrollo/sistema-pescadeportiva/backend/venv/Scripts/python.exe; $PY manage.py test apps.fleet.tests_paquetes.PaquetePrecioPorPersonaTests`
Expected: FAIL (`TypeError`/`AttributeError`: `precio_por_persona` no existe).

- [ ] **Step 3: Implementar el campo y el método**

En `backend/apps/fleet/models.py`, dentro de `class Paquete`, después de `precio_ancla_usd`:

```python
    precio_por_persona = models.BooleanField(
        default=False,
        help_text='Si está activo, el precio ancla (MXN y USD) es el de UNA persona y el total es '
                  'precio × personas. Apagado, el precio ancla es un total fijo del paquete.',
    )
```

Y después de `precio_en`:

```python
    def precio_total_en(self, moneda, personas=1):
        """Precio base del paquete para `personas` en `moneda`, o None si no está configurado.
        Fijo: el ancla tal cual. Por persona: ancla × personas."""
        ancla = self.precio_en(moneda)
        if ancla is None:
            return None
        if self.precio_por_persona:
            return (Decimal(ancla) * int(personas)).quantize(Decimal('0.01'))
        return Decimal(ancla)
```

En `errores_de_precio_contra_transporte` (mismo archivo), dentro del `for servicio, personas in pares:`, justo después de calcular `tarifas`, agregar la rama por persona y dejar intacta la rama de total fijo:

```python
        if paquete.precio_por_persona:
            errores.update(_errores_por_persona(paquete, tarifas, personas))
            continue
```

Y definir arriba de esa función:

```python
def _errores_por_persona(paquete, tarifas, personas):
    """Con precio por persona el total crece con el grupo, igual que la tarifa por rangos:
    se revisa cada tamaño de 1 a `personas`."""
    errores = {}
    for n in range(1, personas + 1):
        for campo, moneda, ancla in (
            ('precio_ancla', 'MXN', paquete.precio_ancla),
            ('precio_ancla_usd', 'USD', paquete.precio_ancla_usd),
        ):
            peor = peor_tarifa(tarifas, personas=n, moneda=moneda)
            if campo not in errores and peor is not None and ancla is not None and ancla * n < peor:
                errores[campo] = (
                    f'El precio por persona ({ancla}) para {n} persona(s) es menor que la '
                    f'tarifa de transporte ({peor}).'
                )
    return errores
```

En `backend/apps/fleet/admin.py:166`, agregar `'precio_por_persona'` a `list_display` después de `'precio_ancla_usd'`.

- [ ] **Step 4: Generar la migración**

Run: `$PY manage.py makemigrations fleet -n paquete_precio_por_persona`
Expected: crea `0038_paquete_precio_por_persona.py` con un solo `AddField`. Revisar que no incluya otros cambios.

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

Run: `$PY manage.py test apps.fleet.tests_paquetes`
Expected: PASS (las nuevas y las existentes de paquetes).

- [ ] **Step 6: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/admin.py backend/apps/fleet/migrations/0038_paquete_precio_por_persona.py backend/apps/fleet/tests_paquetes.py
git commit -m "feat(fleet): precio por persona en el paquete"
```

---

### Task 2: `precio_paquete_total` y catálogo público

**Files:**
- Modify: `backend/apps/payments/pricing.py:129-144`
- Modify: `backend/apps/fleet/serializers.py:87`
- Test: `backend/apps/payments/tests_pricing_paquete.py` (clase `CalcularPrecioPaqueteIntegrationTests`)

**Interfaces:**
- Consumes: `Paquete.precio_total_en(moneda, personas)` (Task 1).
- Produces: `precio_paquete_total(paquete, *, personas=1, moneda='MXN', ...)` ahora respeta `precio_por_persona`; el catálogo público devuelve `precio_por_persona`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En la clase `CalcularPrecioPaqueteIntegrationTests` de `backend/apps/payments/tests_pricing_paquete.py` (su `self.paquete` es 6500 MXN / 380 USD):

```python
    def test_por_persona_multiplica_el_ancla_por_las_personas(self):
        Paquete.objects.filter(pk=self.paquete.pk).update(precio_por_persona=True)
        self.paquete.refresh_from_db()
        self.assertEqual(precio_paquete_total(self.paquete, personas=3, moneda='MXN'), Decimal('19500.00'))
        self.assertEqual(precio_paquete_total(self.paquete, personas=2, moneda='USD'), Decimal('760.00'))

    def test_paquete_fijo_ignora_las_personas(self):
        self.assertEqual(precio_paquete_total(self.paquete, personas=4, moneda='MXN'), Decimal('6500.00'))
```

Y un test del serializador en `backend/apps/fleet/tests_paquetes.py` dentro de `PaquetePrecioPorPersonaTests`:

```python
    def test_el_catalogo_publico_expone_precio_por_persona(self):
        from apps.fleet.serializers import PaqueteSerializer
        paquete = self._paquete(precio_por_persona=True)
        self.assertTrue(PaqueteSerializer(paquete).data['precio_por_persona'])
```


- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.payments.tests_pricing_paquete apps.fleet.tests_paquetes.PaquetePrecioPorPersonaTests`
Expected: FAIL en `test_por_persona_multiplica...` (devuelve 6500) y en el serializador (`KeyError`).

- [ ] **Step 3: Implementar**

En `backend/apps/payments/pricing.py`, reemplazar:

```python
    precio_ancla = paquete.precio_en(moneda)
    if precio_ancla is None:
        return None
```

por:

```python
    base = paquete.precio_total_en(moneda, personas)
    if base is None:
        return None
```

y `total = Decimal(precio_ancla)` por `total = base`. Actualizar el docstring: "el ancla" pasa a "el ancla (× personas si `precio_por_persona`)".

En `backend/apps/fleet/serializers.py:87`, agregar `'precio_por_persona'` a la tupla de campos junto a `'precio_ancla_usd'`.

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.payments.tests_pricing_paquete apps.fleet`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/payments/pricing.py backend/apps/fleet/serializers.py backend/apps/payments/tests_pricing_paquete.py backend/apps/fleet/tests_paquetes.py
git commit -m "feat(payments): precio_paquete_total y catalogo respetan precio por persona"
```

---

### Task 3: Reserva de una empresa (`CrearPagoView` y serializador)

**Files:**
- Modify: `backend/apps/payments/views.py:74`
- Modify: `backend/apps/bookings/serializers.py` (`_derivar_de_paquete`, después de la validación de `set(personas) != set(esperadas)`)
- Test: `backend/apps/payments/tests.py` (después de `test_crear_pago_paquete_sin_anticipo_cobra_pago_completo`) y `backend/apps/bookings/tests_paquete_estancia.py` (clase `SerializadorPaqueteTests`)

**Interfaces:**
- Consumes: `Paquete.precio_total_en` (Task 1).
- Produces: `crear-pago` de una reserva de paquete cobra `ancla × numero_personas`; una reserva de paquete por persona exige el mismo número de personas en todos sus servicios.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `backend/apps/payments/tests.py`, mismo estilo que `test_crear_pago_paquete_sin_anticipo_cobra_pago_completo`:

```python
    @mock.patch.object(StripeClient, 'payment_intents')
    def test_crear_pago_paquete_por_persona_cobra_ancla_por_personas(self, payment_intents):
        payment_intents.create.return_value = intent_falso()
        paquete = Paquete.objects.create(
            sede=self.empresa.sede, empresa_lider=self.empresa, nombre='Paquete Por Persona',
            slug='paquete-por-persona', precio_ancla=Decimal('45000.00'),
            precio_por_persona=True, permite_anticipo=False,
        )
        reserva_paquete = Reserva.objects.create(
            empresa=self.empresa, paquete=paquete, fecha=date(2026, 10, 1), hora=time(7, 0),
            numero_personas=3, nombre_cliente='Ana Gomez', telefono_cliente='1234567890',
            correo_cliente='ana@test.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
            checkout_id=uuid.uuid4(),
        )
        url = reverse('crear-pago', kwargs={'empresa_slug': self.empresa.slug, 'pk': reserva_paquete.pk})
        resp = self.client.post(url, {
            'forma_pago': 'completo', 'checkout_id': str(reserva_paquete.checkout_id),
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['monto_a_cobrar'], '135000.00')
        reserva_paquete.refresh_from_db()
        self.assertEqual(reserva_paquete.precio_total, Decimal('135000.00'))
```

Para el serializador, en la clase `SerializadorPaqueteTests` de `backend/apps/bookings/tests_paquete_estancia.py` (su fixture `FixturePaqueteEstancia` deja `self.paquete`, `self.pesca` con 3 lugares incluidos y `self.hotel` con 2; agregar `Paquete` al import de `apps.fleet.models` si falta):

```python
    def test_paquete_por_persona_exige_las_mismas_personas_en_todos_los_servicios(self):
        Paquete.objects.filter(pk=self.paquete.pk).update(precio_por_persona=True)
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 2})
        self.assertFalse(valido)
        self.assertIn('mismo número de personas', str(serializador.errors['personas_por_servicio']))

    def test_paquete_por_persona_acepta_las_mismas_personas(self):
        Paquete.objects.filter(pk=self.paquete.pk).update(precio_por_persona=True)
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 2, str(self.hotel.pk): 2})
        self.assertTrue(valido, serializador.errors)
        self.assertEqual(serializador.validated_data['numero_personas'], 2)
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.payments.tests apps.bookings.tests_paquete_estancia`
Expected: FAIL (`monto_a_cobrar` = `45000.00`; el serializador acepta personas distintas).

- [ ] **Step 3: Implementar**

`backend/apps/payments/views.py:74`:

```python
            precio_base_servicio = reserva.paquete.precio_total_en(reserva.moneda, reserva.numero_personas)
```

`backend/apps/bookings/serializers.py`, en `_derivar_de_paquete`, justo después del bloque `if set(personas) != set(esperadas): raise ...`:

```python
        if componentes and componentes[0].paquete.precio_por_persona and len(set(personas.values())) > 1:
            raise serializers.ValidationError({
                'personas_por_servicio': 'En este paquete todos los servicios van con el mismo número de personas.',
            })
```

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.payments.tests apps.bookings`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/payments/views.py backend/apps/bookings/serializers.py backend/apps/payments/tests.py backend/apps/bookings/tests_paquete_estancia.py
git commit -m "feat(payments): reserva de paquete por persona cobra ancla por personas"
```

---

### Task 4: Orden cruza-empresa

**Files:**
- Modify: `backend/apps/payments/views.py` (`CrearOrdenView` ~línea 620-660; `CrearPagosOrdenView` ~línea 769-810)
- Test: `backend/apps/payments/tests_orden_paquete.py` (clases `CrearOrdenPaqueteTests` y `CrearPagoOrdenTests`)

**Interfaces:**
- Consumes: `Paquete.precio_total_en` (Task 1).
- Produces: una orden de un paquete por persona exige mismas personas en todos los componentes; `crear-pago` reparte `ancla × personas` (residuo para la líder, tarifa fija para transporte).

- [ ] **Step 1: Escribir las pruebas que fallan**

En `CrearOrdenPaqueteTests`:

```python
    def test_paquete_por_persona_exige_las_mismas_personas_en_todos_los_servicios(self):
        with scope.como_operador_plataforma():
            Paquete.objects.filter(pk=self.paquete.pk).update(precio_por_persona=True)
        respuesta = self.crear()  # pesca con 2 personas, traslado con 3
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('mismo número de personas', str(respuesta.json()))
        with scope.como_operador_plataforma():
            self.assertFalse(Orden.objects.exists())
```

En `CrearPagoOrdenTests`:

```python
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_paquete_por_persona_reparte_ancla_por_personas(self, configurar):
        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        with scope.como_operador_plataforma():
            Paquete.objects.filter(pk=self.paquete.pk).update(precio_por_persona=True)
        datos = self.payload()
        datos['componentes'][0]['numero_personas'] = 3
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        pago = self._pago(respuesta.json()['orden_id'])
        self.assertEqual(pago.status_code, 200, pago.content)
        montos = {p['empresa_slug']: p['monto'] for p in pago.json()}
        # 7500 × 3 = 22500; transporte 1500 + silla 150; la líder recibe el residuo 21000 + brunch 400.
        self.assertEqual(montos, {'pesca-op': '21400.00', 'transp-op': '1650.00'})
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.payments.tests_orden_paquete`
Expected: FAIL (la primera devuelve 201; la segunda reparte `6400.00`).

- [ ] **Step 3: Implementar**

En `CrearOrdenView`, antes del `for servicio in servicios:` agregar `personas_pedido = []`; dentro del ciclo, justo después de la comprobación `if personas > ps['personas_incluidas']`, agregar `personas_pedido.append(personas)`; y al terminar el ciclo (todavía dentro del `transaction.atomic()`):

```python
                if paquete.precio_por_persona and len(set(personas_pedido)) > 1:
                    raise DjangoValidationError({
                        'numero_personas': 'En este paquete todos los servicios van con el mismo número de personas.',
                    })
```

En `CrearPagosOrdenView.post`, reemplazar:

```python
        with scope.con_empresa(orden.empresa_lider):
            precio_paquete = orden.paquete.precio_en(orden.moneda)
        if precio_paquete is None:
```

por:

```python
        with scope.con_empresa(orden.empresa_lider):
            paquete = orden.paquete
            ancla = paquete.precio_en(orden.moneda)
        if ancla is None:
```

Dentro del ciclo `for fila in reservas_de_orden(orden.id):`, junto a donde se arma `reserva`, guardar las personas de la líder (`if es_lider: personas_paquete = reserva.numero_personas`), con `personas_paquete = 1` inicializado antes del ciclo. Después del ciclo y antes de `try:`:

```python
        precio_paquete = paquete.precio_total_en(orden.moneda, personas_paquete)
```

El resto (`monto_por_empresa(precio_paquete=precio_paquete, ...)`) no cambia.

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.payments`
Expected: PASS (incluidas las pruebas de orden existentes, que no usan precio por persona).

- [ ] **Step 5: Commit**

```bash
git add backend/apps/payments/views.py backend/apps/payments/tests_orden_paquete.py
git commit -m "feat(payments): orden cruza-empresa reparte ancla por personas"
```

---

### Task 5: Compuerta de backend (SQLite y Postgres) y documentación

**Files:**
- Modify: `backend/CLAUDE.md` (sección "Checkout unificado de paquetes", viñeta "Anticipo")
- Test: toda la suite

- [ ] **Step 1: Documentar**

En `backend/CLAUDE.md`, sección "Checkout unificado de paquetes", agregar una viñeta:

```markdown
- **Precio por persona**: `Paquete.precio_por_persona` (default `False`). Apagado, `precio_ancla`
  es un total fijo. Encendido, `precio_ancla` y `precio_ancla_usd` son los de UNA persona y el
  total es `ancla × numero_personas` (`Paquete.precio_total_en`). Todos los servicios de un
  paquete por persona van con el mismo número de personas (lo exigen `_derivar_de_paquete` y
  `CrearOrdenView`). En una orden cruza-empresa el transporte cobra su tarifa y la líder el
  residuo de `ancla × personas`. `validar_configuracion` revisa el ancla contra la tarifa de
  transporte para cada grupo de 1 a `personas_incluidas`.
```

- [ ] **Step 2: Suite completa en SQLite**

Run: `$PY manage.py test apps config`
Expected: PASS, sin fallos nuevos.

- [ ] **Step 3: Suite completa en Postgres**

Seguir "Correr la suite contra Postgres en local" de `backend/CLAUDE.md` (contenedor `psd-pg` en el puerto 5433, rol `ci_rls`) y correr `manage.py test apps config` con `DJANGO_SETTINGS_MODULE=config.settings.ci`.
Expected: PASS. Si Docker no está disponible, **decirlo** y no declarar el gate cerrado.

- [ ] **Step 4: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): precio por persona en paquetes"
```

---

### Task 6: Frontend — **bloqueada hasta luz verde del dueño**

Por la regla de diseño del proyecto, esta tarea no se codifica hasta que el dueño apruebe una explicación. Alcance previsto, para esa explicación:

- `frontend/src/lib/api.ts`: el tipo `PaqueteCatalogo` gana `precio_por_persona: boolean`.
- `frontend/src/lib/pedido-paquete.ts` (vista previa del total): con `precio_por_persona`, `total = ancla × personas`. Esa función ya existe y tiene su suite en `tests/`; se amplía con vectores de prueba (45,000 × 2 = 90,000; USD 2,500 × 3 = 7,500).
- `frontend/src/components/pedido/pedido-paquete.tsx` y `grupo-servicio.tsx`: en un paquete por persona hay **un solo selector de personas** para todo el pedido (hoy hay uno por servicio) y el precio se muestra como "$X por persona" más el total.
- `AvisoCargos` (desglose por empresa): suma `ancla × personas`.
- Dos paquetes de La Ventana ($45,000 y $52,500) como caso de verificación visual.

Antes de escribir código: explicar al dueño estos cambios con el proceso `perception-first-design` y esperar su aprobación explícita.
