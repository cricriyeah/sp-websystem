# Checkout unificado — Plan de implementación (backend)

> **Para agentes:** SUB-SKILL REQUERIDO: usar superpowers:subagent-driven-development (recomendado) o superpowers:executing-plans para ejecutar este plan tarea por tarea. Los pasos usan casillas `- [ ]`. Modo del proyecto: TDD estricto, **un commit por tarea**, **STOP DURO al cerrar cada sección** (reportar al dueño antes de seguir). Sin push, sin merge.

**Meta:** que el servidor aplique las reglas del checkout unificado de paquetes: anticipo explícito, noches / día / personas definidos por el paquete, extras por servicio cobrados a la empresa dueña, USD en órdenes de dos empresas, y (Sección 6) el estado de "Continuar reservación" para cualquier servicio o paquete.

**Arquitectura:** dos módulos puros nuevos en `apps/fleet` (reglas de paquete y calendario del paquete) son la única fuente de estas reglas y los usan el modelo, el admin, el serializer y las vistas. No hay tablas nuevas (evita RLS nuevo): solo columnas y un `JSONField`. El dinero sigue calculándose únicamente en `apps/payments` (nuevo `extras.py` para cotizar extras, usado por las dos vistas de cobro).

**Stack:** Django + DRF, Stripe (mockeado en tests), SQLite en local y PostgreSQL con RLS en CI.

**Spec:** `docs/superpowers/specs/2026-09-21-checkout-unificado-design.md`. Léelo completo antes de empezar: contiene el vector de prueba (§7) y las reglas de paquete (§5).

**Plan hermano:** `2026-09-21-checkout-unificado-frontend.md` consume el contrato de API de la §6 del spec. No empieces el frontend antes de cerrar la Sección 2 de este plan (necesita el catálogo).

## Restricciones globales

- Todo dinero se calcula en `apps/payments/` (`pricing.py`, `extras.py`). El cliente nunca manda un total.
- Toda escritura a una tabla con tenant se hace dentro de `scope.con_empresa(empresa)`; las pruebas de modelo usan `OperadorTestCase` (o `ApiTestCase` si hacen peticiones HTTP). Ver `apps/testing.py`.
- Migraciones de datos sobre tablas con RLS: envolver en `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):`.
- Sin tablas nuevas. Cualquier columna nueva va en una tabla existente.
- `full_clean()` antes de `save()` en cualquier flujo que cree o edite una `Reserva`.
- Escrituras Stripe con `idempotency_key` (no se añade ninguna nueva en este plan; no las quites).
- Mensajes de error para el cliente en español, tono neutro.
- Sin datos hardcodeados de precios en código; los valores de los tests son fixtures.
- Los commits terminan con el trailer `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (indicación de la sesión).
- Comandos: dentro de `backend/` del worktree nuevo, con `PY=../../transporte-multi-empresa/backend/venv/Scripts/python.exe` (ver Tarea 0.1).
- Gate por sección: `$PY manage.py test apps.fleet apps.bookings apps.payments` en verde (SQLite). Gate final (Sección 5): suite completa SQLite **y** PostgreSQL con `ci_rls`.

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/fleet/paquete_reglas.py` | crear | Reglas de coherencia de un paquete, función pura sobre datos simples |
| `backend/apps/fleet/calendario_paquete.py` | crear | Aritmética de fechas del paquete, función pura |
| `backend/apps/fleet/tarifa_transporte.py` | modificar | añade `peor_tarifa` (tarifa más alta aplicable) |
| `backend/apps/fleet/models.py` | modificar | campos de anticipo, campos de `PaqueteServicio` (incluida la copia `empresa`), `Paquete.es_cruza_empresa/noches/validar_configuracion`, `componente_desde/componente_de` |
| `backend/apps/fleet/admin.py` | modificar | formset de `PaqueteServicio` con validación conjunta; campos nuevos visibles |
| `backend/apps/fleet/serializers.py` | modificar | catálogo con anticipo y estancia |
| `backend/apps/fleet/catalogo.py` | modificar | catálogo de paquetes con componentes de otras empresas bajo RLS (Tarea 2.7) |
| `backend/apps/fleet/views.py` | modificar | `TrasladosView` expone `permite_anticipo` |
| `backend/apps/bookings/models.py` | modificar | `Reserva.personas_por_servicio`, `personas_de`, `fecha_inicio_paquete`; cupo del paquete por componente |
| `backend/apps/bookings/cupo/confirmacion.py` | modificar | personas y fechas por componente al confirmar el pago |
| `backend/apps/bookings/serializers.py` | modificar | deriva fechas y personas del paquete; usa el helper de personalizaciones |
| `backend/apps/bookings/personalizaciones.py` | crear | validar y sincronizar la selección de extras de una reserva (compartido) |
| `backend/apps/payments/extras.py` | crear | cotizar y congelar extras de una reserva (compartido por los dos cobros) |
| `backend/apps/payments/pricing.py` | modificar | extras por persona con las personas del componente |
| `backend/apps/payments/views.py` | modificar | anticipo permitido, órdenes con calendario/personas/extras/USD |
| `backend/apps/fleet/management/commands/seed_local_demo.py` | modificar | datos demo con los campos nuevos |
| `backend/CLAUDE.md` | modificar | documentar las reglas nuevas |
| `backend/apps/payments/situacion.py` | crear | `situacion`/`requiere_atencion` de una Reserva u Orden (Sección 6, spec §10.1) |
| `backend/apps/payments/views.py` | modificar (Sección 6) | `ResumenReservaView`, `ResumenOrdenView`, `CancelarOrdenPublicaView` |
| `backend/apps/bookings/admin.py` | modificar (Sección 6) | "requiere atención" en `ReservaAdmin`/`OrdenAdmin` |
| tests nuevos | crear | uno por módulo/tarea, listados en cada tarea |

<!-- arch-critic: APPROVED (revisión adversarial hecha inline por política del proyecto, sin subagente; hallazgos abajo) -->

**Revisión de arquitectura (adversarial, inline).** Hallazgos y cómo quedaron resueltos en el mapa:
1. *Acoplamiento fleet↔bookings:* los módulos puros nuevos viven en `fleet` y no importan `bookings`; `bookings` importa de `fleet` (dirección ya existente). `payments/extras.py` importa de `bookings` y `fleet` (ya existente); nadie importa `payments` desde ellos.
2. *Falsos errores del admin:* validar reglas multi-fila en `PaqueteServicio.clean` da errores falsos cuando se editan varias filas a la vez (cada fila ve la BD vieja de sus hermanas). Por eso el modelo solo hace comprobaciones locales; la validación conjunta vive en el `formset.clean()` del admin (autoritativa, ve el estado nuevo) y en `Paquete.validar_configuracion()` (para seed/scripts/tests). `Paquete.clean` solo comprueba anticipo × cruza-empresa.
3. *Dinero duplicado:* la cotización de extras existía como método de una vista; se extrae a `payments/extras.py` **antes** de usarla en la orden (Tarea 4.3 antes de la 4.4) para que haya una sola implementación.
4. *Semántica de `Reserva.fecha`:* el motor de cupo, la agenda y la regla de una salida por día leen `Reserva.fecha`; se define como el día de la actividad operativa y el inicio del hospedaje se deriva (`fecha_inicio_paquete`), en vez de tocar el motor de cupo.
5. *Suposición latente de `crear_pagos_orden`:* reparte por empresa y asume una reserva por empresa; la regla 2 de `paquete_reglas` la hace explícita.
6. *RLS:* `personas_por_servicio` es `JSONField` (sin tabla nueva); las filas `ReservaPersonalizacion` de una orden se escriben dentro de `scope.con_empresa(empresa_de_la_reserva)`.
7. *N+1 en el catálogo:* `es_cruza_empresa` hace una consulta por paquete; aceptado (listas cortas), anotado en la Tarea 1.3.

**Revisión externa (2026-09-21, otro agente) — correcciones ya aplicadas a este plan:** (1) la migración de anticipo reactivaba las filas que acababa de desactivar (1.1); (2) lectura de componentes bajo RLS: nuevas Tareas 2.6 y 2.7 y lecturas reescritas en 4.3/4.4; (3) el reemplazo de `CrearPagoOrdenView` no compilaba: método completo en 4.4; (4) el inicio del paquete se guarda (`inicio_paquete`) y no se deriva de las noches del catálogo (3.1); (5) las actividades de un paquete de una empresa comparten número de personas y el tope global de 5 no aplica a reservas de paquete (3.2/3.3); (6) el modelo ya no valida entre filas y `validar_configuracion()` corre antes de vender (2.3, 3.2, 4.3); (7) zona efectiva en el reparto de traslados (4.4); (8) inventario ampliado de pruebas a ajustar (1.2, 3.2, 4.3, 5.1); (9) correo, admin y recuperación de reserva leen `fecha_inicio_paquete` (3.5); (10) la rama base debe contener todo lo que el plan usa (0.1).

---

## Sección 0 — Preparación

### Tarea 0.1: Rama de trabajo y línea base

**Files:** ninguno del proyecto.

- [x] **Paso 1: Crear el worktree nuevo** desde la raíz del repo (`C:/Users/kkjf/desarrollo/sistema-pescadeportiva`). Se parte de los commits de `feat/transporte-multi-empresa`; los cambios sin commitear de la ronda del hub (catálogo, diccionarios) se quedan en el worktree viejo y no se mezclan.

```bash
git worktree add .claude/worktrees/checkout-unificado -b feat/checkout-unificado feat/transporte-multi-empresa
cd .claude/worktrees/checkout-unificado/backend
export PY=../../transporte-multi-empresa/backend/venv/Scripts/python.exe
$PY --version
```
Esperado: `Python 3.x` (reusa el venv del worktree viejo; no se crea uno nuevo).

- [x] **Paso 2: Línea base verde.**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
```
Esperado: `OK`. Anota el número de tests: es la referencia para todo el plan. Si falla algo, detente y repórtalo; no se empieza sobre rojo.

**Línea base verificada (2026-09-23):** HEAD inicial `69b285453889d532e95846aba612e8a7a39d445b` (`feat/transporte-multi-empresa`); Python `3.14.3`; `apps.fleet apps.bookings apps.payments`: **776 tests descubiertos**, ejecución SQLite terminada con código 0 (`OK`).

- [x] **Paso 3: Llevar los documentos al worktree nuevo.** El spec y los dos planes se escribieron en el worktree viejo (`.claude/worktrees/transporte-multi-empresa/docs/superpowers/`) sin commitear; un worktree nuevo no ve archivos sin commitear. Desde la raíz del worktree nuevo:

```bash
mkdir -p docs/superpowers/specs docs/superpowers/plans
cp ../transporte-multi-empresa/docs/superpowers/specs/2026-09-21-checkout-unificado-design.md docs/superpowers/specs/
cp ../transporte-multi-empresa/docs/superpowers/plans/2026-09-21-checkout-unificado-*.md docs/superpowers/plans/
git add docs/superpowers
git commit -m "docs: spec y planes del checkout unificado de paquetes"
```
(Antes anota en este plan la línea base: HEAD y nº de tests del Paso 2.)

- [x] **Paso 4: Comprobar que la rama base contiene todo lo que este plan usa.** Los planes se escribieron leyendo un árbol con cambios sin commitear de la ronda del hub. En el worktree nuevo verifica que existen los símbolos que se van a modificar:

```bash
git grep -n "def zona_efectiva" backend/apps/bookings/models.py
git grep -n "def _buscar_servicios_de_paquete" backend/apps/payments/views.py
git grep -n "class OperadorTestCase" backend/apps/testing.py
git grep -n "export function hrefPaquete" frontend/src/lib/booking-href.ts
```
Cualquier símbolo que falte se define dentro de la tarea que lo necesita; **no** se traen cambios del hub.

**STOP:** no hay commit de código en esta tarea.

---

## Sección 1 — Reglas de anticipo

### Tarea 1.1: `permite_anticipo` y porcentaje validado en Servicio y Paquete

**Files:**
- Modify: `backend/apps/fleet/models.py` (`Servicio.porcentaje_anticipo` ≈ L264; `Paquete.porcentaje_anticipo` ≈ L505)
- Create: migración `apps/fleet/migrations/00NN_anticipo_explicito.py` (la genera `makemigrations`)
- Test: `backend/apps/fleet/tests_anticipo.py`

**Interfaces:**
- Produces: `Servicio.permite_anticipo: bool` (default `True`), `Paquete.permite_anticipo: bool` (default `True`); ambos `porcentaje_anticipo` con validadores 1..99.

- [ ] **Paso 1: Escribir la prueba que falla** — `backend/apps/fleet/tests_anticipo.py`:

```python
"""Reglas de anticipo de Servicio y Paquete."""
import importlib
import pkgutil
from decimal import Decimal
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.db import connection

from apps.fleet.models import Paquete, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


def _modulo_migracion():
    import apps.fleet.migrations as paquete_migraciones

    nombre = next(
        n for _, n, _ in pkgutil.iter_modules(paquete_migraciones.__path__)
        if n.endswith('_anticipo_explicito')
    )
    return importlib.import_module(f'apps.fleet.migrations.{nombre}')


class AnticipoServicioPaqueteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Pesca Anticipo', slug='pesca-anticipo')

    def _servicio(self, slug='pesca-a', **extra):
        return Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug=slug, tipo_servicio='pesca',
            precio_base=Decimal('4000.00'), **extra,
        )

    def test_por_defecto_permite_anticipo_del_30(self):
        servicio = self._servicio()
        self.assertTrue(servicio.permite_anticipo)
        self.assertEqual(servicio.porcentaje_anticipo, 30)

    def test_porcentaje_fuera_de_1_a_99_no_es_valido_en_servicio_ni_paquete(self):
        for pct in (0, 100, 150):
            with self.subTest(pct=pct):
                servicio = self._servicio(slug=f's-{pct}', porcentaje_anticipo=pct)
                with self.assertRaises(ValidationError) as ctx:
                    servicio.full_clean()
                self.assertIn('porcentaje_anticipo', ctx.exception.message_dict)
                paquete = Paquete(
                    sede=self.sede, empresa_lider=self.empresa, nombre='P', slug=f'p-{pct}',
                    precio_ancla=Decimal('5000.00'), porcentaje_anticipo=pct,
                )
                with self.assertRaises(ValidationError) as ctx:
                    paquete.full_clean()
                self.assertIn('porcentaje_anticipo', ctx.exception.message_dict)

    def test_migracion_de_datos_marca_permite_segun_el_porcentaje_viejo(self):
        viejo_completo = self._servicio(slug='viejo-100', porcentaje_anticipo=100)
        viejo_anticipo = self._servicio(slug='viejo-30', porcentaje_anticipo=30)
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='P', slug='p-viejo',
            precio_ancla=Decimal('5000.00'), porcentaje_anticipo=100,
        )

        _modulo_migracion().marcar_permite_anticipo(django_apps, SimpleNamespace(connection=connection))

        for fila in (viejo_completo, viejo_anticipo, paquete):
            fila.refresh_from_db()
        self.assertFalse(viejo_completo.permite_anticipo)
        self.assertEqual(viejo_completo.porcentaje_anticipo, 30)
        self.assertTrue(viejo_anticipo.permite_anticipo)
        self.assertEqual(viejo_anticipo.porcentaje_anticipo, 30)
        self.assertFalse(paquete.permite_anticipo)
        self.assertEqual(paquete.porcentaje_anticipo, 30)
```

- [ ] **Paso 2: Verlo fallar**

```bash
$PY manage.py test apps.fleet.tests_anticipo -v 2
```
Esperado: FAIL/ERROR (`permite_anticipo` no existe, no hay migración `_anticipo_explicito`).

- [ ] **Paso 3: Implementar el modelo.** En `apps/fleet/models.py` asegura el import `from django.core.validators import MaxValueValidator, MinValueValidator` y reemplaza en `Servicio`:

```python
    permite_anticipo = models.BooleanField(
        default=True,
        help_text='Si está activo, el cliente puede elegir pagar solo el anticipo.',
    )
    porcentaje_anticipo = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text='% del total que se cobra en línea si el cliente elige anticipo (1 a 99). '
                  'Solo aplica si "permite anticipo" está activo.',
    )
```
y en `Paquete` (en lugar de `porcentaje_anticipo = models.PositiveSmallIntegerField(default=30)`):

```python
    permite_anticipo = models.BooleanField(
        default=True,
        help_text='Si está activo, el cliente puede elegir pagar solo el anticipo. '
                  'Un paquete con servicios de dos empresas nunca admite anticipo.',
    )
    porcentaje_anticipo = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        help_text='% del total que se cobra en línea si el cliente elige anticipo (1 a 99). '
                  'Sustituye al anticipo de los servicios individuales del paquete.',
    )
```

- [ ] **Paso 4: Generar la migración y añadir la migración de datos.**

```bash
$PY manage.py makemigrations fleet -n anticipo_explicito
```
Abre el archivo generado. Deben aparecer `AddField` (×2, `permite_anticipo`) y `AlterField` (×2, `porcentaje_anticipo`). Añade arriba las funciones y al final de `operations` el `RunPython`:

```python
from django.db import migrations

from apps.tenancy.rls import alcance_operador_migracion


def marcar_permite_anticipo(apps, schema_editor):
    """Antes "sin anticipo" se codificaba con porcentaje 100. Ahora es un interruptor."""
    with alcance_operador_migracion(schema_editor.connection):
        for nombre in ('Servicio', 'Paquete'):
            modelo = apps.get_model('fleet', nombre)
            # Solo las filas que eran "sin anticipo" (100). Las demás ya quedan en True por el
            # default del AddField; NO se vuelve a activar nada después (reactivaría estas mismas
            # filas, que acaban de quedar con porcentaje 30).
            modelo.objects.filter(porcentaje_anticipo__gte=100).update(
                permite_anticipo=False, porcentaje_anticipo=30,
            )


def revertir_permite_anticipo(apps, schema_editor):
    with alcance_operador_migracion(schema_editor.connection):
        for nombre in ('Servicio', 'Paquete'):
            modelo = apps.get_model('fleet', nombre)
            modelo.objects.filter(permite_anticipo=False).update(porcentaje_anticipo=100)
```
y `migrations.RunPython(marcar_permite_anticipo, revertir_permite_anticipo),` como última operación.

- [ ] **Paso 5: Verlo pasar y revisar regresiones.**

```bash
$PY manage.py test apps.fleet.tests_anticipo -v 2
$PY manage.py test apps.fleet apps.bookings apps.payments
```
Esperado: la primera en verde. En la segunda pueden fallar pruebas que usaban `porcentaje_anticipo=100` como "sin anticipo": esas se corrigen en la Tarea 1.2 (anótalas, no las toques todavía).

- [ ] **Paso 6: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/migrations backend/apps/fleet/tests_anticipo.py
git commit -m "feat(fleet): permite_anticipo explicito en Servicio y Paquete, porcentaje 1-99"
```

### Tarea 1.2: `anticipo_disponible` y rechazo en `crear-pago`

**Files:**
- Modify: `backend/apps/fleet/models.py` (`Servicio`, `Paquete`)
- Modify: `backend/apps/payments/views.py` (`CrearPagoView.post`, ≈ L66-L125)
- Modify: `backend/apps/payments/tests.py` (`TrasladoPagoFixture` ≈ L2204 y `test_congela_detalle_y_anticipo_cobra_cien_por_ciento` ≈ L2279)
- Test: `backend/apps/payments/tests_anticipo.py`, ampliar `backend/apps/fleet/tests_anticipo.py`

**Interfaces:**
- Produces: `Servicio.anticipo_disponible -> bool`, `Paquete.es_cruza_empresa -> bool` (la Tarea 2.6 lo reemplaza por una versión que funciona bajo RLS), `Paquete.anticipo_disponible -> bool`.
- Consumes: `permite_anticipo` de la Tarea 1.1.

- [ ] **Paso 1: Pruebas que fallan.** Añade al final de `apps/fleet/tests_anticipo.py`:

```python
class AnticipoDisponibleTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca AD', slug='pesca-ad')
        self.transporte = Empresa.objects.create(sede=self.sede, nombre='Transp AD', slug='transp-ad')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-ad-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transporte, nombre='Traslado', slug='traslado-ad-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )

    def _paquete(self, slug, servicios, **extra):
        from apps.fleet.models import PaqueteServicio

        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre=slug, slug=slug,
            precio_ancla=Decimal('9000.00'), **extra,
        )
        for orden, servicio in enumerate(servicios, start=1):
            PaqueteServicio.objects.create(paquete=paquete, servicio=servicio, orden=orden)
        return paquete

    def test_servicio_sigue_su_interruptor(self):
        self.assertTrue(self.s_pesca.anticipo_disponible)
        self.s_pesca.permite_anticipo = False
        self.assertFalse(self.s_pesca.anticipo_disponible)

    def test_paquete_de_una_empresa_admite_anticipo_si_lo_permite(self):
        paquete = self._paquete('mono-ad', [self.s_pesca])
        self.assertFalse(paquete.es_cruza_empresa)
        self.assertTrue(paquete.anticipo_disponible)
        paquete.permite_anticipo = False
        self.assertFalse(paquete.anticipo_disponible)

    def test_paquete_de_dos_empresas_nunca_admite_anticipo(self):
        paquete = self._paquete('cruza-ad', [self.s_pesca, self.s_transp], permite_anticipo=True)
        self.assertTrue(paquete.es_cruza_empresa)
        self.assertFalse(paquete.anticipo_disponible)
```
Y crea `apps/payments/tests_anticipo.py`:

```python
"""El servidor rechaza el pago de anticipo cuando el producto no lo admite."""
from apps.payments.tests import TrasladoPagoFixture
from apps.testing import ApiTestCase


class AnticipoNoPermitidoTest(TrasladoPagoFixture, ApiTestCase):
    def test_servicio_sin_anticipo_rechaza_forma_pago_anticipo(self):
        self.servicio.permite_anticipo = False
        self.servicio.save(update_fields=['permite_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='anticipo')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('anticipo', respuesta.json()['detail'].lower())

    def test_servicio_sin_anticipo_acepta_pago_completo(self):
        self.servicio.permite_anticipo = False
        self.servicio.save(update_fields=['permite_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='completo')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['monto_a_cobrar'], '4500.00')

    def test_servicio_con_anticipo_cobra_solo_el_porcentaje(self):
        self.servicio.permite_anticipo = True
        self.servicio.porcentaje_anticipo = 30
        self.servicio.save(update_fields=['permite_anticipo', 'porcentaje_anticipo'])
        respuesta = self.post(self.reserva(), forma_pago='anticipo')
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['monto_a_cobrar'], '1350.00')
```

- [ ] **Paso 2: Verlos fallar**

```bash
$PY manage.py test apps.fleet.tests_anticipo apps.payments.tests_anticipo -v 2
```
Esperado: FAIL (`anticipo_disponible` no existe; el servicio sin anticipo hoy sí acepta `anticipo`).

- [ ] **Paso 3: Propiedades del modelo.** En `Servicio` (junto a `precio_en`):

```python
    @property
    def anticipo_disponible(self):
        """El cliente puede elegir pagar solo el anticipo de este servicio."""
        return self.permite_anticipo
```
En `Paquete` (junto a `precio_en`):

```python
    @property
    def es_cruza_empresa(self):
        """Sus servicios pertenecen a más de una empresa."""
        return self.servicios_asociados.values('servicio__empresa_id').distinct().count() > 1

    @property
    def anticipo_disponible(self):
        """Un paquete de dos empresas nunca admite anticipo, diga lo que diga el campo."""
        return self.permite_anticipo and not self.es_cruza_empresa
```

- [ ] **Paso 4: Rechazo en el servidor.** En `CrearPagoView.post`: en la rama `if reserva.paquete_id:` añade tras `porcentaje = reserva.paquete.porcentaje_anticipo`:

```python
            anticipo_disponible = reserva.paquete.anticipo_disponible
```
y en la rama `elif reserva.servicio_id:` tras `porcentaje = reserva.servicio.porcentaje_anticipo`:

```python
            anticipo_disponible = reserva.servicio.anticipo_disponible
```
Justo después de validar `forma_pago in Reserva.FormaPago.values` añade:

```python
        if forma_pago == 'anticipo' and not anticipo_disponible:
            return Response({'detail': 'Este producto no admite pago de anticipo.'}, status=400)
```

- [ ] **Paso 5: Ajustar las pruebas viejas que codificaban "sin anticipo" con 100.**

```bash
grep -rn "porcentaje_anticipo=100\|'porcentaje_anticipo': 100" apps
```
- `apps/payments/tests.py` (`TrasladoPagoFixture.setUp`): cambia `porcentaje_anticipo=100` por `permite_anticipo=False`.
- Mismo archivo, `test_congela_detalle_y_anticipo_cobra_cien_por_ciento`: renómbralo `test_congela_detalle_y_pago_completo` y cambia `self.post(reserva, forma_pago='anticipo')` por `self.post(reserva)`; en el assert final de `forma_pago` espera `'completo'`.
- `apps/fleet/tests.py` (≈ L712 y L730): reemplaza `porcentaje_anticipo=100` / `'porcentaje_anticipo': 100` por `permite_anticipo=False` / `'permite_anticipo': False` y ajusta el assert que lea `porcentaje_anticipo` si lo hay.
- `apps/payments/tests.py` ≈ L368 y ≈ L1228: más `porcentaje_anticipo=100` que codificaban "sin anticipo"; usa `permite_anticipo=False` (y en los tests que luego piden `forma_pago='anticipo'` espera 400, o pídeles `completo`).
- Búsqueda de seguridad: `grep -rn "porcentaje_anticipo" apps --include=*.py | grep -v migrations` y revisa cada aparición en tests y en `apps/fleet/management/commands/seed_local_demo.py` (Servicio de hospedaje ≈ L175 y de transporte ≈ L205). No conserves fixtures "inválidos": `objects.create` omite los validadores 1..99.

- [ ] **Paso 6: Verlo pasar**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
```
Esperado: `OK` con el mismo número de tests de la línea base más los nuevos.

- [ ] **Paso 7: Commit**

```bash
git add backend/apps/fleet backend/apps/payments
git commit -m "feat(payments): el servidor rechaza anticipo si el producto no lo admite"
```

### Tarea 1.3: Admin y catálogo exponen el anticipo

**Files:**
- Modify: `backend/apps/fleet/admin.py` (`ServicioAdmin` ≈ L99, `PaqueteAdmin` ≈ L135)
- Modify: `backend/apps/fleet/serializers.py` (`ServicioSerializer`, `PaqueteSerializer`)
- Modify: `backend/apps/fleet/views.py` (`TrasladosView`, ≈ L143)
- Test: `backend/apps/fleet/tests_catalogo_anticipo.py`

**Interfaces:**
- Produces (JSON): `servicio.permite_anticipo`, `servicio.porcentaje_anticipo`; `paquete.permite_anticipo` (**efectivo**), `paquete.porcentaje_anticipo`, `paquete.es_cruza_empresa`; `traslados.servicio.permite_anticipo`.

- [ ] **Paso 1: Prueba que falla** — `backend/apps/fleet/tests_catalogo_anticipo.py`:

```python
"""El catálogo público expone el anticipo efectivo de servicios y paquetes."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class CatalogoAnticipoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede CA', slug='sede-ca-test')
            self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CA', slug='pesca-ca')
            self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CA', slug='transp-ca')
            s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-ca-s', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'), porcentaje_anticipo=40,
            )
            s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-ca-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            mono = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Mono', slug='mono-ca',
                precio_ancla=Decimal('5000.00'), porcentaje_anticipo=50,
            )
            PaqueteServicio.objects.create(paquete=mono, servicio=s_pesca, orden=1)
            cruza = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cruza', slug='cruza-ca',
                precio_ancla=Decimal('9000.00'), permite_anticipo=True,
            )
            PaqueteServicio.objects.create(paquete=cruza, servicio=s_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=cruza, servicio=s_transp, orden=2)

    def _paquete(self, slug):
        respuesta = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/{slug}/')
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return respuesta.json()

    def test_paquete_de_una_empresa_expone_su_anticipo(self):
        datos = self._paquete('mono-ca')
        self.assertTrue(datos['permite_anticipo'])
        self.assertEqual(datos['porcentaje_anticipo'], 50)
        self.assertFalse(datos['es_cruza_empresa'])
        self.assertEqual(datos['servicios_asociados'][0]['servicio']['porcentaje_anticipo'], 40)

    def test_paquete_de_dos_empresas_nunca_dice_que_permite_anticipo(self):
        datos = self._paquete('cruza-ca')
        self.assertFalse(datos['permite_anticipo'])
        self.assertTrue(datos['es_cruza_empresa'])
```

- [ ] **Paso 2: Verlo fallar**

```bash
$PY manage.py test apps.fleet.tests_catalogo_anticipo -v 2
```
Esperado: FAIL (`KeyError: 'permite_anticipo'`).

- [ ] **Paso 3: Serializers.** En `ServicioSerializer.Meta.fields` añade `'permite_anticipo', 'porcentaje_anticipo'`. En `PaqueteSerializer` añade:

```python
    permite_anticipo = serializers.SerializerMethodField()
    es_cruza_empresa = serializers.SerializerMethodField()

    def get_permite_anticipo(self, obj):
        return obj.anticipo_disponible

    def get_es_cruza_empresa(self, obj):
        # Una consulta por paquete; aceptable para las listas cortas del catálogo.
        return obj.es_cruza_empresa
```
y en `Meta.fields` añade `'permite_anticipo', 'porcentaje_anticipo', 'es_cruza_empresa'`.

- [ ] **Paso 4: `TrasladosView`.** En `apps/fleet/views.py` junto a `'porcentaje_anticipo': servicio.porcentaje_anticipo,` (≈ L143) añade `'permite_anticipo': servicio.permite_anticipo,`.

- [ ] **Paso 5: Admin.** En `ServicioAdmin.list_display` añade `'permite_anticipo', 'porcentaje_anticipo'` y en `list_filter` `'permite_anticipo'`. En `PaqueteAdmin.list_display` añade `'permite_anticipo', 'porcentaje_anticipo'`. Los campos ya salen en el formulario porque el admin usa todos los campos del modelo; verifica en el shell que `ServicioAdmin(Servicio, admin.site).get_form(None)().fields` contiene `permite_anticipo`.

- [ ] **Paso 6: Verlo pasar y commit**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/fleet
git commit -m "feat(fleet): catalogo y admin exponen anticipo efectivo de servicio y paquete"
```

**STOP DURO — Cierre de la Sección 1.** Reportar al dueño: reglas de anticipo aplicadas (servidor + catálogo + admin), pruebas verdes.

---

## Sección 2 — Configuración del paquete (noches, día, personas)

### Tarea 2.1: Campos de estancia y personas en `PaqueteServicio`

**Files:**
- Modify: `backend/apps/fleet/models.py` (`PaqueteServicio` ≈ L551)
- Create: migración `apps/fleet/migrations/00NN_paqueteservicio_estancia_personas.py`
- Test: `backend/apps/fleet/tests_paquete_reglas.py` (se amplía en la 2.2)

**Interfaces:**
- Produces: `PaqueteServicio.dia_estancia: int` (default 1), `.noches: int | None`, `.personas_incluidas: int` (default 2).

- [ ] **Paso 1: Prueba que falla** — `backend/apps/fleet/tests_paquete_reglas.py`:

```python
"""Campos y reglas de configuración de un paquete."""
from decimal import Decimal

from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class CamposDePaqueteServicioTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa CP', slug='empresa-cp')
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-cp', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='P', slug='p-cp',
            precio_ancla=Decimal('5000.00'),
        )

    def test_defaults_de_estancia_y_personas(self):
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.servicio, orden=1)
        self.assertEqual(ps.dia_estancia, 1)
        self.assertIsNone(ps.noches)
        self.assertEqual(ps.personas_incluidas, 2)
```

- [ ] **Paso 2: Verlo fallar** — `$PY manage.py test apps.fleet.tests_paquete_reglas -v 2` → FAIL (`dia_estancia` no existe).

- [ ] **Paso 3: Implementar.** En `PaqueteServicio`, tras `orden`:

```python
    dia_estancia = models.PositiveSmallIntegerField(
        default=1,
        help_text='Día del paquete en que ocurre este servicio (1 = día de llegada).',
    )
    noches = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Solo hospedaje: noches que incluye el paquete. El cliente no las elige.',
    )
    personas_incluidas = models.PositiveSmallIntegerField(
        default=2,
        help_text='Lugares de este servicio que incluye el paquete. El cliente puede usar menos '
                  'sin que cambie el precio.',
    )
```

- [ ] **Paso 4: Migración y verificación**

```bash
$PY manage.py makemigrations fleet -n paqueteservicio_estancia_personas
```
Añade al archivo generado una migración de datos: los hospedajes que ya estaban en un paquete quedan con `noches=1` (antes no existía el dato; el dueño ajusta el valor real en el admin). Sin esto, un paquete existente con hospedaje fallaría la regla "el hospedaje exige noches":

```python
from apps.tenancy.rls import alcance_operador_migracion


def noches_por_omision(apps, schema_editor):
    with alcance_operador_migracion(schema_editor.connection):
        modelo = apps.get_model('fleet', 'PaqueteServicio')
        modelo.objects.filter(
            servicio__estrategia_cupo='por_noche', noches__isnull=True,
        ).update(noches=1)
```
y `migrations.RunPython(noches_por_omision, migrations.RunPython.noop),` como última operación.

```bash
$PY manage.py test apps.fleet.tests_paquete_reglas -v 2
```
Esperado: `OK`.

- [ ] **Paso 5: Commit**

```bash
git add backend/apps/fleet
git commit -m "feat(fleet): dia_estancia, noches y personas_incluidas en PaqueteServicio"
```

### Tarea 2.2: Reglas de paquete como función pura

**Files:**
- Create: `backend/apps/fleet/paquete_reglas.py`
- Test: `backend/apps/fleet/tests_paquete_reglas.py` (se amplía)

**Interfaces:**
- Produces:
  - `Componente(servicio_nombre: str, empresa_id: int, estrategia_cupo: str, noches: int | None, dia_estancia: int, personas_incluidas: int, tope_personas: int | None)` (dataclass frozen).
  - `errores_de_paquete(*, permite_anticipo: bool, componentes: list[Componente]) -> list[str]`.
  - `hay_conflicto_anticipo(*, permite_anticipo: bool, empresas_ids: set[int]) -> bool`.

- [ ] **Paso 1: Pruebas que fallan.** Añade a `apps/fleet/tests_paquete_reglas.py` (imports arriba: `from django.test import SimpleTestCase` y `from apps.fleet.paquete_reglas import Componente, errores_de_paquete, hay_conflicto_anticipo`):

```python
def _c(nombre='S', empresa=1, estrategia='por_recurso_dia', noches=None, dia=1, personas=2, tope=5):
    return Componente(
        servicio_nombre=nombre, empresa_id=empresa, estrategia_cupo=estrategia,
        noches=noches, dia_estancia=dia, personas_incluidas=personas, tope_personas=tope,
    )


class ReglasDePaqueteTests(SimpleTestCase):
    def errores(self, componentes, permite_anticipo=False):
        return errores_de_paquete(permite_anticipo=permite_anticipo, componentes=componentes)

    def test_paquete_valido_de_una_empresa_con_hospedaje(self):
        componentes = [
            _c('Pesca', dia=2),
            _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None),
        ]
        self.assertEqual(self.errores(componentes, permite_anticipo=True), [])

    def test_cruza_empresa_no_admite_anticipo(self):
        errores = self.errores([_c(empresa=1), _c('Traslado', empresa=2, estrategia='bajo_demanda')], permite_anticipo=True)
        self.assertTrue(any('anticipo' in e for e in errores))
        self.assertTrue(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1, 2}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=True, empresas_ids={1}))
        self.assertFalse(hay_conflicto_anticipo(permite_anticipo=False, empresas_ids={1, 2}))

    def test_cruza_empresa_solo_un_servicio_por_empresa(self):
        errores = self.errores([_c('A', empresa=1), _c('B', empresa=1), _c('T', empresa=2, estrategia='bajo_demanda')])
        self.assertTrue(any('un servicio por empresa' in e for e in errores))

    def test_solo_un_hospedaje(self):
        errores = self.errores([
            _c('H1', estrategia='por_noche', noches=2, tope=None),
            _c('H2', estrategia='por_noche', noches=2, tope=None),
        ])
        self.assertTrue(any('un hospedaje' in e for e in errores))

    def test_hospedaje_exige_noches_y_los_demas_no_las_admiten(self):
        self.assertTrue(any('noches' in e for e in self.errores([_c('H', estrategia='por_noche', noches=None, tope=None)])))
        self.assertTrue(any('noches' in e for e in self.errores([_c('Pesca', noches=2)])))

    def test_dia_de_estancia(self):
        # Sin hospedaje todo cae el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=2)])))
        # Con hospedaje de 2 noches el día 3 (salida) no vale; el 2 sí.
        hotel = _c('Hotel', estrategia='por_noche', noches=2, dia=1, tope=None)
        self.assertTrue(any('día' in e for e in self.errores([_c(dia=3), hotel])))
        self.assertEqual(self.errores([_c(dia=2), hotel]), [])
        # El hospedaje empieza el día 1.
        self.assertTrue(any('día' in e for e in self.errores([_c('Hotel', estrategia='por_noche', noches=2, dia=2, tope=None)])))

    def test_las_actividades_comparten_dia(self):
        hotel = _c('Hotel', estrategia='por_noche', noches=3, dia=1, tope=None)
        errores = self.errores([_c('A', dia=1), _c('B', dia=2), hotel])
        self.assertTrue(any('mismo día' in e for e in errores))

    def test_personas_incluidas_dentro_del_tope(self):
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=0)])))
        self.assertTrue(any('personas' in e for e in self.errores([_c(personas=6, tope=5)])))
        self.assertEqual(self.errores([_c(personas=14, tope=None)]), [])
```

- [ ] **Paso 2: Verlas fallar** — `$PY manage.py test apps.fleet.tests_paquete_reglas -v 2` → ERROR (`ModuleNotFoundError: apps.fleet.paquete_reglas`).

- [ ] **Paso 3: Implementar** — `backend/apps/fleet/paquete_reglas.py`:

```python
"""Reglas de coherencia de un Paquete, en función pura.

Una sola función valida un paquete completo a partir de datos simples, para que la
usen igual el formset del admin, `Paquete.validar_configuracion()` y las pruebas.
No toca la base de datos ni importa modelos."""
from dataclasses import dataclass

POR_NOCHE = 'por_noche'
POR_RECURSO_DIA = 'por_recurso_dia'


@dataclass(frozen=True)
class Componente:
    servicio_nombre: str
    empresa_id: int
    estrategia_cupo: str
    noches: int | None
    dia_estancia: int
    personas_incluidas: int
    # None = no se valida aquí (el hospedaje depende de las habitaciones reales).
    tope_personas: int | None


def hay_conflicto_anticipo(*, permite_anticipo: bool, empresas_ids: set[int]) -> bool:
    """Un paquete con servicios de dos empresas no puede tener anticipo."""
    return bool(permite_anticipo) and len(empresas_ids) > 1


def errores_de_paquete(*, permite_anticipo: bool, componentes: list[Componente]) -> list[str]:
    errores: list[str] = []
    empresas = {c.empresa_id for c in componentes}

    if hay_conflicto_anticipo(permite_anticipo=permite_anticipo, empresas_ids=empresas):
        errores.append(
            'Un paquete con servicios de dos empresas no admite anticipo: desactiva "permite anticipo".'
        )
    if len(empresas) > 1 and len(empresas) != len(componentes):
        errores.append('En un paquete de dos empresas solo puede haber un servicio por empresa.')

    hospedajes = [c for c in componentes if c.estrategia_cupo == POR_NOCHE]
    if len(hospedajes) > 1:
        errores.append('Un paquete solo puede incluir un hospedaje.')

    for c in componentes:
        if c.estrategia_cupo == POR_NOCHE:
            if not c.noches or c.noches < 1:
                errores.append(f'"{c.servicio_nombre}": indica cuántas noches incluye el paquete.')
            if c.dia_estancia != 1:
                errores.append(f'"{c.servicio_nombre}": el hospedaje empieza el día 1 del paquete.')
        elif c.noches is not None:
            errores.append(f'"{c.servicio_nombre}": las noches solo aplican al hospedaje.')

        if c.dia_estancia < 1:
            errores.append(f'"{c.servicio_nombre}": el día del paquete debe ser 1 o mayor.')

        if c.personas_incluidas < 1:
            errores.append(f'"{c.servicio_nombre}": las personas incluidas deben ser al menos 1.')
        elif c.tope_personas is not None and c.personas_incluidas > c.tope_personas:
            errores.append(
                f'"{c.servicio_nombre}": las personas incluidas ({c.personas_incluidas}) '
                f'superan el máximo del servicio ({c.tope_personas}).'
            )

    noches_paquete = hospedajes[0].noches if hospedajes and hospedajes[0].noches else None
    for c in componentes:
        if c.estrategia_cupo == POR_NOCHE or c.dia_estancia < 1:
            continue
        if noches_paquete is None and c.dia_estancia != 1:
            errores.append(
                f'"{c.servicio_nombre}": sin hospedaje el paquete dura un día; el servicio debe caer el día 1.'
            )
        elif noches_paquete is not None and c.dia_estancia > noches_paquete:
            errores.append(
                f'"{c.servicio_nombre}": el día {c.dia_estancia} cae fuera de la estancia '
                f'({noches_paquete} noche(s); el último día válido es el {noches_paquete}).'
            )

    dias_actividad = {c.dia_estancia for c in componentes if c.estrategia_cupo == POR_RECURSO_DIA}
    if len(dias_actividad) > 1:
        errores.append('Las actividades del paquete deben ocurrir el mismo día de la estancia.')

    return errores
```

- [ ] **Paso 4: Verlas pasar y commit**

```bash
$PY manage.py test apps.fleet.tests_paquete_reglas -v 2
git add backend/apps/fleet/paquete_reglas.py backend/apps/fleet/tests_paquete_reglas.py
git commit -m "feat(fleet): reglas de coherencia de paquete como funcion pura"
```

### Tarea 2.3: Reglas de paquete en el admin y en la venta; tarifa de transporte por peor caso

> **Diseño (corrección tras la revisión externa):** `PaqueteServicio.clean` y `Paquete.clean` leen la BD *vieja* de las filas hermanas; validar ahí reglas entre filas o precio-contra-tarifa da falsos errores cuando el admin cambia varias filas a la vez (p. ej. quitar el traslado y activar el anticipo en el mismo envío). Por eso: **el modelo solo hace comprobaciones locales**; la validación conjunta vive en (a) el `formset.clean()` del admin, que ve el estado nuevo, y (b) `Paquete.validar_configuracion()`, que **se ejecuta antes de vender** (Tareas 3.2 y 4.3), no solo en scripts.

**Files:**
- Modify: `backend/apps/fleet/tarifa_transporte.py` (añade `peor_tarifa`)
- Modify: `backend/apps/fleet/models.py` (`componente_desde`, `componente_de`, `errores_de_precio_contra_transporte`, `Paquete.clean`, `Paquete.validar_configuracion`, `PaqueteServicio.clean`)
- Modify: `backend/apps/fleet/admin.py` (`PaqueteServicioFormSet`, `PaqueteServicioInline`)
- Test: `backend/apps/fleet/tests_paquete_reglas.py`

**Interfaces:**
- Consumes: `errores_de_paquete`, `Componente` (2.2).
- Produces:
  - `peor_tarifa(tarifas, *, personas, moneda) -> Decimal | None`.
  - `componente_desde(servicio, *, noches, dia_estancia, personas_incluidas) -> Componente` (sirve a quien ya tiene el `Servicio` y la fila de configuración por separado, p. ej. `CrearOrdenView`).
  - `componente_de(ps: PaqueteServicio) -> Componente`.
  - `errores_de_precio_contra_transporte(paquete, pares: list[tuple[Servicio, int]]) -> dict[str, str]`.
  - `Paquete.validar_configuracion(componentes: list[Componente] | None = None)` (lanza `ValidationError`). Con `componentes=None` lee la BD (admin, shell, tests, y peticiones bajo el alcance de la empresa dueña); con `componentes` valida solo la estructura sobre lo que el llamador ya leyó bajo RLS.
  - `PaqueteServicioFormSet` (admin).

- [ ] **Paso 1: Pruebas que fallan.** Añade a `tests_paquete_reglas.py`:

```python
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from apps.fleet.admin import PaqueteServicioFormSet
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import TransporteTarifa
from apps.fleet.tarifa_transporte import peor_tarifa


class ConfiguracionDePaqueteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CM', slug='pesca-cm')
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CM', slug='transp-cm')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-cm-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transp, nombre='Traslado', slug='traslado-cm-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )

    def _paquete_cruza(self, slug, precio='9000.00', **extra):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre=slug, slug=slug,
            precio_ancla=Decimal(precio), **extra,
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_pesca, orden=1)
        PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_transp, orden=2)
        return paquete

    def test_peor_tarifa_toma_la_mas_alta_aplicable_al_grupo(self):
        for tipo, minimo, maximo, precio in (
            (TipoTraslado.REDONDO_AEROPUERTO, 1, 4, '4500.00'),
            (TipoTraslado.REDONDO_AEROPUERTO, 5, None, '6000.00'),
            (TipoTraslado.RECEPCION_AEROPUERTO, 1, None, '2700.00'),
        ):
            TransporteTarifa.objects.create(
                empresa=self.transp, tipo_traslado=tipo, personas_min=minimo, personas_max=maximo, precio=precio,
            )
        tarifas = list(self.transp.tarifas_transporte.filter(activo=True))
        self.assertEqual(peor_tarifa(tarifas, personas=2, moneda='MXN'), Decimal('4500.00'))
        self.assertEqual(peor_tarifa(tarifas, personas=8, moneda='MXN'), Decimal('6000.00'))
        self.assertIsNone(peor_tarifa(tarifas, personas=2, moneda='USD'))

    def test_validar_configuracion_exige_que_el_precio_cubra_la_peor_tarifa(self):
        TransporteTarifa.objects.create(
            empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1, personas_max=None, precio=Decimal('4500.00'),
        )
        paquete = self._paquete_cruza('c-cm', precio='4000.00', permite_anticipo=False)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertIn('tarifa de transporte', str(ctx.exception))

    def test_validar_configuracion_rechaza_anticipo_en_paquete_de_dos_empresas(self):
        paquete = self._paquete_cruza('d-cm', permite_anticipo=True)
        with self.assertRaises(ValidationError) as ctx:
            paquete.validar_configuracion()
        self.assertIn('anticipo', str(ctx.exception))

    def test_validar_configuracion_con_componentes_leidos_por_el_llamador_solo_valida_estructura(self):
        paquete = self._paquete_cruza('e-cm', permite_anticipo=True)
        from apps.fleet.models import componente_desde

        componentes = [
            componente_desde(self.s_pesca, noches=None, dia_estancia=1, personas_incluidas=2),
            componente_desde(self.s_transp, noches=None, dia_estancia=1, personas_incluidas=2),
        ]
        with self.assertRaises(ValidationError):
            paquete.validar_configuracion(componentes)

    def test_clean_del_modelo_no_lee_filas_viejas(self):
        # Activar el anticipo sobre un paquete de dos empresas NO falla en Paquete.clean:
        # lo atrapa el formset del admin (estado nuevo) y validar_configuracion (venta).
        paquete = self._paquete_cruza('f-cm', permite_anticipo=False)
        paquete.permite_anticipo = True
        paquete.full_clean()

    def _formset(self, paquete, filas):
        FormSet = inlineformset_factory(
            Paquete, PaqueteServicio, formset=PaqueteServicioFormSet,
            fields=['servicio', 'orden', 'dia_estancia', 'noches', 'personas_incluidas'], extra=0,
        )
        datos = {
            'servicios_asociados-TOTAL_FORMS': str(len(filas)), 'servicios_asociados-INITIAL_FORMS': '0',
            'servicios_asociados-MIN_NUM_FORMS': '0', 'servicios_asociados-MAX_NUM_FORMS': '1000',
        }
        for i, servicio in enumerate(filas):
            datos.update({
                f'servicios_asociados-{i}-servicio': str(servicio.pk),
                f'servicios_asociados-{i}-orden': str(i + 1),
                f'servicios_asociados-{i}-dia_estancia': '1',
                f'servicios_asociados-{i}-personas_incluidas': '2',
            })
        return FormSet(datos, instance=paquete)

    def test_formset_rechaza_anticipo_con_dos_empresas(self):
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='g', slug='g-cm',
            precio_ancla=Decimal('9000.00'), permite_anticipo=True,
        )
        formset = self._formset(paquete, [self.s_pesca, self.s_transp])
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('anticipo' in e for e in formset.non_form_errors()))

    def test_formset_acepta_quitar_el_traslado_y_dejar_anticipo_en_el_mismo_envio(self):
        paquete = self._paquete_cruza('h-cm', permite_anticipo=False)
        paquete.permite_anticipo = True  # el usuario lo activa en el mismo envío en que quita el traslado
        formset = self._formset(paquete, [self.s_pesca])
        self.assertTrue(formset.is_valid(), formset.non_form_errors())

    def test_formset_valida_el_precio_contra_la_peor_tarifa(self):
        TransporteTarifa.objects.create(
            empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO,
            personas_min=1, personas_max=None, precio=Decimal('4500.00'),
        )
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='i', slug='i-cm',
            precio_ancla=Decimal('4000.00'), permite_anticipo=False,
        )
        formset = self._formset(paquete, [self.s_pesca, self.s_transp])
        self.assertFalse(formset.is_valid())
        self.assertTrue(any('tarifa de transporte' in e for e in formset.non_form_errors()))
```

- [ ] **Paso 2: Verlas fallar** — `$PY manage.py test apps.fleet.tests_paquete_reglas -v 2` → ERROR (imports inexistentes: `PaqueteServicioFormSet`, `peor_tarifa`, `componente_desde`).

- [ ] **Paso 3: `peor_tarifa`.** Añade a `backend/apps/fleet/tarifa_transporte.py`:

```python
def peor_tarifa(tarifas, *, personas, moneda):
    """La tarifa más alta que puede tocarle a un grupo de `personas` (cualquier tipo
    y zona), en `moneda`, o None si ninguna aplica o no tiene precio en esa moneda.

    El precio de un paquete debe cubrirla: el cliente elige el tipo de traslado al
    reservar, así que hay que asumir el más caro."""
    precios = []
    for t in tarifas:
        if personas < t.personas_min:
            continue
        if t.personas_max is not None and personas > t.personas_max:
            continue
        precio = t.precio if (moneda or 'MXN').upper() == 'MXN' else t.precio_usd
        if precio is not None:
            precios.append(precio)
    return max(precios) if precios else None
```

- [ ] **Paso 4: Modelo.** En `apps/fleet/models.py` (imports: `from apps.fleet.paquete_reglas import Componente, errores_de_paquete` y `from apps.fleet.tarifa_transporte import peor_tarifa`) añade, a nivel de módulo antes de `class Paquete`:

```python
TOPE_PERSONAS_ACTIVIDAD = 5  # mismo valor que bookings.MAX_PERSONAS; fleet no importa bookings


def componente_desde(servicio, *, noches, dia_estancia, personas_incluidas):
    """Vista de un servicio + su configuración en el paquete para `paquete_reglas`."""
    if servicio.estrategia_cupo == 'por_noche':
        tope = None  # el hospedaje depende de las habitaciones reales
    else:
        tope = servicio.capacidad_maxima or (
            TOPE_PERSONAS_ACTIVIDAD if servicio.estrategia_cupo == 'por_recurso_dia' else None
        )
    return Componente(
        servicio_nombre=servicio.nombre, empresa_id=servicio.empresa_id,
        estrategia_cupo=servicio.estrategia_cupo, noches=noches, dia_estancia=dia_estancia,
        personas_incluidas=personas_incluidas, tope_personas=tope,
    )


def componente_de(ps):
    return componente_desde(
        ps.servicio, noches=ps.noches, dia_estancia=ps.dia_estancia, personas_incluidas=ps.personas_incluidas,
    )


def errores_de_precio_contra_transporte(paquete, pares):
    """El precio del paquete debe cubrir la peor tarifa de cada traslado incluido.
    `pares`: lista de `(servicio, personas_incluidas)`."""
    errores = {}
    for servicio, personas in pares:
        if servicio.tipo_servicio != 'transporte':
            continue
        tarifas = list(servicio.empresa.tarifas_transporte.filter(activo=True))
        peor_mxn = peor_tarifa(tarifas, personas=personas, moneda='MXN')
        if peor_mxn is not None and paquete.precio_ancla is not None and paquete.precio_ancla < peor_mxn:
            errores['precio_ancla'] = (
                f'El precio del paquete ({paquete.precio_ancla}) no puede ser menor que la '
                f'tarifa de transporte ({peor_mxn}).'
            )
        peor_usd = peor_tarifa(tarifas, personas=personas, moneda='USD')
        if peor_usd is not None and paquete.precio_ancla_usd is not None and paquete.precio_ancla_usd < peor_usd:
            errores['precio_ancla_usd'] = (
                f'El precio en USD del paquete ({paquete.precio_ancla_usd}) no puede ser menor '
                f'que la tarifa de transporte en USD ({peor_usd}).'
            )
    return errores
```
En `Paquete.clean` **borra por completo** el bloque `if self.pk:` (el que recorría `servicios_asociados` con `min(...)`): queda solo la comprobación de sede. En `PaqueteServicio.clean` **borra** el bloque `if self.servicio.tipo_servicio == 'transporte': ...` (el de `min(t.precio ...)`): queda solo la comprobación de sede. Añade a `Paquete`:

```python
    def validar_configuracion(self, componentes=None):
        """Reglas completas del paquete. Lanza ValidationError con todos los mensajes.

        Sin `componentes` lee la BD (admin, shell, pruebas, o una petición bajo el alcance
        de la empresa dueña cuando todos los servicios son suyos) e incluye el precio contra
        la peor tarifa de transporte. Con `componentes` (lectura ya hecha bajo RLS por el
        llamador, p. ej. una orden de dos empresas) valida solo la estructura: el precio
        contra la tarifa lo sigue protegiendo `monto_por_empresa` al cobrar."""
        precio = {}
        if componentes is None:
            filas = list(self.servicios_asociados.select_related('servicio', 'servicio__empresa'))
            componentes = [componente_de(ps) for ps in filas]
            precio = errores_de_precio_contra_transporte(
                self, [(ps.servicio, ps.personas_incluidas) for ps in filas],
            )
        errores = errores_de_paquete(permite_anticipo=self.permite_anticipo, componentes=componentes)
        errores += list(precio.values())
        if errores:
            raise ValidationError(errores)
```

- [ ] **Paso 5: Admin.** En `apps/fleet/admin.py` (imports: `from django.core.exceptions import ValidationError`, `from django.forms import BaseInlineFormSet`, `from .models import componente_de, errores_de_precio_contra_transporte` y `from .paquete_reglas import errores_de_paquete`):

```python
class PaqueteServicioFormSet(BaseInlineFormSet):
    """Valida el paquete completo con lo que el usuario acaba de escribir, no con la BD vieja."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filas = [
            form.instance for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        errores = errores_de_paquete(
            permite_anticipo=self.instance.permite_anticipo,
            componentes=[componente_de(ps) for ps in filas],
        )
        errores += list(errores_de_precio_contra_transporte(
            self.instance, [(ps.servicio, ps.personas_incluidas) for ps in filas],
        ).values())
        if errores:
            raise ValidationError(errores)


class PaqueteServicioInline(TabularInline):
    model = PaqueteServicio
    formset = PaqueteServicioFormSet
    extra = 1
    fields = ['servicio', 'orden', 'dia_estancia', 'noches', 'personas_incluidas']
    autocomplete_fields = ['servicio']
```
(reemplaza la definición existente de `PaqueteServicioInline`).

- [ ] **Paso 6: Verlas pasar y regresiones**

```bash
$PY manage.py test apps.fleet -v 1
grep -rn "tarifa de transporte\|no puede ser menor" apps --include=tests*.py
```
Esperado: `OK`. El `grep` lista las pruebas viejas que verificaban el error de tarifa mediante `full_clean()` del modelo (p. ej. en `apps/fleet/tests_paquetes.py`): cámbialas para llamar `paquete.validar_configuracion()` en lugar de `full_clean()`, sin cambiar lo que comprueban (la frase "no puede ser menor que la tarifa de transporte" se conserva). Después: `$PY manage.py test apps.fleet apps.bookings apps.payments`.

- [ ] **Paso 7: Commit**

```bash
git add backend/apps/fleet
git commit -m "feat(fleet): reglas de paquete en el admin y antes de vender; precio cubre la peor tarifa"
```

### Tarea 2.4: Calendario del paquete (módulo puro)

**Files:**
- Create: `backend/apps/fleet/calendario_paquete.py`
- Test: `backend/apps/fleet/tests_calendario_paquete.py`

**Interfaces:**
- Produces:
  - `ComponenteCalendario(dia_estancia: int, estrategia_cupo: str, noches: int | None)` (dataclass frozen).
  - `noches_del_paquete(componentes) -> int | None`
  - `fecha_de_componente(inicio: date, dia_estancia: int) -> date`
  - `fecha_salida(inicio: date, componentes) -> date | None`
  - `fecha_ancla(inicio: date, componentes) -> date`
  - `inicio_desde_reserva(fecha: date, fecha_salida: date | None, componentes) -> date`

- [ ] **Paso 1: Prueba que falla** — `backend/apps/fleet/tests_calendario_paquete.py` (usa el vector de la §5 del spec):

```python
from datetime import date

from django.test import SimpleTestCase

from apps.fleet.calendario_paquete import (
    ComponenteCalendario, fecha_ancla, fecha_de_componente, fecha_salida,
    inicio_desde_reserva, noches_del_paquete,
)

PESCA_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='por_recurso_dia', noches=None)
HOTEL_3 = ComponenteCalendario(dia_estancia=1, estrategia_cupo='por_noche', noches=3)
TRASLADO_DIA_2 = ComponenteCalendario(dia_estancia=2, estrategia_cupo='bajo_demanda', noches=None)
INICIO = date(2026, 10, 10)


class CalendarioPaqueteTests(SimpleTestCase):
    def test_noches_del_paquete(self):
        self.assertEqual(noches_del_paquete([PESCA_DIA_2, HOTEL_3]), 3)
        self.assertIsNone(noches_del_paquete([PESCA_DIA_2]))

    def test_fecha_de_cada_componente_cuenta_desde_el_dia_1(self):
        self.assertEqual(fecha_de_componente(INICIO, 1), date(2026, 10, 10))
        self.assertEqual(fecha_de_componente(INICIO, 2), date(2026, 10, 11))

    def test_fecha_de_salida_es_inicio_mas_noches(self):
        self.assertEqual(fecha_salida(INICIO, [PESCA_DIA_2, HOTEL_3]), date(2026, 10, 13))
        self.assertIsNone(fecha_salida(INICIO, [PESCA_DIA_2]))

    def test_ancla_es_el_dia_de_la_actividad_operativa(self):
        self.assertEqual(fecha_ancla(INICIO, [PESCA_DIA_2, HOTEL_3, TRASLADO_DIA_2]), date(2026, 10, 11))

    def test_sin_actividad_el_ancla_es_el_inicio(self):
        self.assertEqual(fecha_ancla(INICIO, [HOTEL_3]), INICIO)

    def test_inicio_se_recupera_de_la_reserva(self):
        componentes = [PESCA_DIA_2, HOTEL_3]
        self.assertEqual(inicio_desde_reserva(date(2026, 10, 11), date(2026, 10, 13), componentes), INICIO)
        sin_hotel = [ComponenteCalendario(dia_estancia=1, estrategia_cupo='por_recurso_dia', noches=None)]
        self.assertEqual(inicio_desde_reserva(INICIO, None, sin_hotel), INICIO)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.fleet.tests_calendario_paquete -v 2` → ERROR (módulo inexistente).

- [ ] **Paso 3: Implementar** — `backend/apps/fleet/calendario_paquete.py`:

```python
"""Aritmética de fechas de un paquete. Función pura: sin base de datos.

Es la única fuente de esta regla (backend y frontend la replican con el mismo
vector de prueba, ver spec §5 y §7). `dia_estancia` cuenta desde 1 (día de llegada)."""
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ComponenteCalendario:
    dia_estancia: int
    estrategia_cupo: str
    noches: int | None


def noches_del_paquete(componentes) -> int | None:
    for c in componentes:
        if c.estrategia_cupo == 'por_noche':
            return c.noches
    return None


def fecha_de_componente(inicio: date, dia_estancia: int) -> date:
    return inicio + timedelta(days=dia_estancia - 1)


def fecha_salida(inicio: date, componentes) -> date | None:
    """Salida del hospedaje: inicio + noches. None si el paquete no incluye hospedaje."""
    noches = noches_del_paquete(componentes)
    return inicio + timedelta(days=noches) if noches else None


def fecha_ancla(inicio: date, componentes) -> date:
    """Día de la actividad operativa (por_recurso_dia); sin actividad, el inicio.

    Es el valor de `Reserva.fecha` en un paquete de una sola empresa: el motor de
    cupo, la agenda y la regla de una salida por día leen ese campo."""
    for c in componentes:
        if c.estrategia_cupo == 'por_recurso_dia':
            return fecha_de_componente(inicio, c.dia_estancia)
    return inicio


def inicio_desde_reserva(fecha: date, fecha_salida_reserva: date | None, componentes) -> date:
    """Recupera el inicio del paquete a partir de una Reserva ya guardada."""
    noches = noches_del_paquete(componentes)
    if fecha_salida_reserva and noches:
        return fecha_salida_reserva - timedelta(days=noches)
    return fecha
```

- [ ] **Paso 4: Verla pasar y commit**

```bash
$PY manage.py test apps.fleet.tests_calendario_paquete -v 2
git add backend/apps/fleet/calendario_paquete.py backend/apps/fleet/tests_calendario_paquete.py
git commit -m "feat(fleet): calendario del paquete como funcion pura"
```

### Tarea 2.5: Catálogo con estancia y personas incluidas

**Files:**
- Modify: `backend/apps/fleet/models.py` (`Paquete.noches`, `Paquete.componentes_calendario`)
- Modify: `backend/apps/fleet/serializers.py` (`PaqueteServicioSerializer`, `PaqueteSerializer`)
- Test: `backend/apps/fleet/tests_catalogo_anticipo.py` (se amplía)

**Interfaces:**
- Produces (JSON): `servicios_asociados[i].dia_estancia | noches | personas_incluidas`; `paquete.noches` (del hospedaje o `null`).
- Produces (Python): `Paquete.noches -> int | None`; `Paquete.componentes_calendario() -> list[ComponenteCalendario]` (ordenados por `orden`, solo servicios activos).

- [ ] **Paso 1: Prueba que falla.** En `tests_catalogo_anticipo.py`, dentro de `_sembrar` del `setUp` añade, tras crear `mono`, un hospedaje y ajusta; para no reescribir el fixture, añade una clase nueva al final del archivo:

```python
class CatalogoEstanciaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            sede = Sede.objects.create(nombre='Sede CE', slug='sede-ce-test')
            empresa = Empresa.objects.create(sede=sede, nombre='Empresa CE', slug='empresa-ce')
            pesca = Servicio.objects.create(
                empresa=empresa, nombre='Pesca', slug='pesca-ce', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'),
            )
            hotel = Servicio.objects.create(
                empresa=empresa, nombre='Cabaña', slug='cabana-ce', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            paquete = Paquete.objects.create(
                sede=sede, empresa_lider=empresa, nombre='Fin de semana', slug='finde-ce',
                precio_ancla=Decimal('9500.00'),
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=pesca, orden=1, dia_estancia=2, personas_incluidas=3)
            PaqueteServicio.objects.create(paquete=paquete, servicio=hotel, orden=2, noches=2, personas_incluidas=2)
        self.sede = sede

    def test_el_catalogo_trae_estancia_y_personas_por_componente(self):
        datos = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/finde-ce/').json()
        self.assertEqual(datos['noches'], 2)
        por_slug = {c['servicio']['slug']: c for c in datos['servicios_asociados']}
        self.assertEqual(por_slug['pesca-ce']['dia_estancia'], 2)
        self.assertEqual(por_slug['pesca-ce']['personas_incluidas'], 3)
        self.assertIsNone(por_slug['pesca-ce']['noches'])
        self.assertEqual(por_slug['cabana-ce']['noches'], 2)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.fleet.tests_catalogo_anticipo -v 2` → FAIL (`KeyError: 'noches'`).

- [ ] **Paso 3: Implementar.** En `Paquete` (models.py; import `from apps.fleet.calendario_paquete import ComponenteCalendario`):

```python
    def componentes_calendario(self):
        """Componentes activos, en orden, listos para `calendario_paquete`."""
        return [
            ComponenteCalendario(
                dia_estancia=ps.dia_estancia, estrategia_cupo=ps.servicio.estrategia_cupo, noches=ps.noches,
            )
            for ps in self.servicios_asociados.filter(servicio__activo=True)
            .select_related('servicio').order_by('orden')
        ]

    @property
    def noches(self):
        """Noches del hospedaje incluido, o None si el paquete no lo tiene."""
        ps = self.servicios_asociados.filter(servicio__estrategia_cupo='por_noche').first()
        return ps.noches if ps else None
```
En `PaqueteServicioSerializer.Meta.fields` añade `'dia_estancia', 'noches', 'personas_incluidas'`. En `PaqueteSerializer` añade `noches = serializers.IntegerField(read_only=True)` y `'noches'` a `Meta.fields`.

- [ ] **Paso 4: Verlo pasar y commit**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/fleet
git commit -m "feat(fleet): catalogo expone estancia y personas incluidas por componente"
```

### Tarea 2.6: Empresa de cada componente, legible bajo RLS

> **Por qué:** la política RLS de `fleet_paqueteservicio` solo deja ver las filas al alcance de la empresa **líder**, y `fleet_servicio` está aislada por empresa: una consulta que **une** `PaqueteServicio` con `Servicio` bajo el alcance de la líder no ve los servicios de otra empresa. `Paquete.es_cruza_empresa` (Tarea 1.2) usa esa unión y bajo PostgreSQL contaría una sola empresa. La solución es guardar una copia de la empresa en cada componente y contar sobre ella, sin unir.

**Files:**
- Modify: `backend/apps/fleet/models.py` (`PaqueteServicio.empresa`, `PaqueteServicio.save`, `Paquete.es_cruza_empresa`)
- Create: migración `apps/fleet/migrations/00NN_paqueteservicio_empresa.py`
- Test: `backend/apps/fleet/tests_paquete_reglas.py` (se amplía)

**Interfaces:**
- Produces: `PaqueteServicio.empresa` (FK a `tenancy.Empresa`, no editable, `null=True`, siempre = `servicio.empresa`); `Paquete.es_cruza_empresa` cuenta sobre esa copia y funciona bajo el alcance de la líder.

- [ ] **Paso 1: Prueba que falla.** Añade a `tests_paquete_reglas.py`:

```python
class EmpresaDelComponenteTests(OperadorTestCase):
    def setUp(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca EC', slug='pesca-ec2')
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp EC', slug='transp-ec2')
        self.s_pesca = Servicio.objects.create(
            empresa=self.pesca, nombre='Pesca', slug='pesca-ec2-s', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.s_transp = Servicio.objects.create(
            empresa=self.transp, nombre='Traslado', slug='traslado-ec2-s', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.pesca, nombre='P', slug='p-ec2', precio_ancla=Decimal('9000.00'),
            permite_anticipo=False,
        )

    def test_el_componente_copia_la_empresa_de_su_servicio(self):
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=1)
        self.assertEqual(ps.empresa_id, self.transp.pk)

    def test_es_cruza_empresa_cuenta_sobre_la_copia_sin_unir_con_servicio(self):
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_pesca, orden=1)
        self.assertFalse(self.paquete.es_cruza_empresa)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=2)
        self.assertTrue(self.paquete.es_cruza_empresa)
        # La consulta no debe unir con fleet_servicio (RLS lo oculta entre empresas).
        with self.assertNumQueries(1):
            self.paquete.es_cruza_empresa

    def test_migracion_de_datos_rellena_empresa_en_filas_viejas(self):
        import importlib
        import pkgutil
        from types import SimpleNamespace

        from django.apps import apps as django_apps
        from django.db import connection

        import apps.fleet.migrations as paquete_migraciones

        nombre = next(
            n for _, n, _ in pkgutil.iter_modules(paquete_migraciones.__path__)
            if n.endswith('_paqueteservicio_empresa')
        )
        modulo = importlib.import_module(f'apps.fleet.migrations.{nombre}')
        ps = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.s_transp, orden=1)
        PaqueteServicio.objects.filter(pk=ps.pk).update(empresa=None)
        modulo.rellenar_empresa(django_apps, SimpleNamespace(connection=connection))
        ps.refresh_from_db()
        self.assertEqual(ps.empresa_id, self.transp.pk)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.fleet.tests_paquete_reglas.EmpresaDelComponenteTests -v 2` → ERROR (`empresa` no es campo).

- [ ] **Paso 3: Implementar.** En `PaqueteServicio` (models.py):

```python
    empresa = models.ForeignKey(
        'tenancy.Empresa', on_delete=models.PROTECT, related_name='+',
        null=True, blank=True, editable=False,
        help_text='Copia de la empresa del servicio. Permite contar las empresas de un paquete sin '
                  'unir con Servicio, que RLS oculta entre empresas.',
    )

    def save(self, *args, **kwargs):
        if self.servicio_id:
            self.empresa_id = self.servicio.empresa_id
        super().save(*args, **kwargs)
```
Reemplaza `Paquete.es_cruza_empresa` (Tarea 1.2):

```python
    @property
    def es_cruza_empresa(self):
        """Sus servicios pertenecen a más de una empresa. Cuenta sobre la copia `empresa` de
        cada componente, sin unir con Servicio: funciona bajo el alcance de la líder (RLS)."""
        return (
            self.servicios_asociados.exclude(empresa__isnull=True)
            .values('empresa_id').distinct().count() > 1
        )
```

- [ ] **Paso 4: Migración de esquema + de datos.**

```bash
$PY manage.py makemigrations fleet -n paqueteservicio_empresa
```
Añade al archivo generado (después del `AddField`) la función y el `RunPython`:

```python
from apps.tenancy.rls import alcance_operador_migracion


def rellenar_empresa(apps, schema_editor):
    """Filas anteriores a este campo: la empresa es la de su servicio."""
    with alcance_operador_migracion(schema_editor.connection):
        modelo = apps.get_model('fleet', 'PaqueteServicio')
        for ps in modelo.objects.select_related('servicio').filter(empresa__isnull=True):
            modelo.objects.filter(pk=ps.pk).update(empresa_id=ps.servicio.empresa_id)
```
y `migrations.RunPython(rellenar_empresa, migrations.RunPython.noop),` como última operación.

- [ ] **Paso 5: Verlo pasar y commit**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/fleet
git commit -m "feat(fleet): empresa copiada en cada componente de paquete para contar empresas bajo RLS"
```

### Tarea 2.7: Catálogo de paquetes con componentes de otras empresas, bajo RLS

> **Por qué:** `apps/fleet/catalogo.py` serializa cada paquete dentro de `con_empresa(líder)`; su propio docstring reconoce que "un componente de otra Empresa no se renderiza todavía por esta vía". Sin esto, en PostgreSQL el catálogo de un paquete de dos empresas omite el traslado y el frontend elegiría el motor de cobro equivocado. En SQLite (desarrollo) no se nota porque no hay RLS.

**Files:**
- Modify: `backend/apps/fleet/catalogo.py` (`paquetes_de_sede`, `paquete_de_sede`, nuevo `_componentes_de`)
- Modify: `backend/apps/fleet/serializers.py` (`PaqueteSerializer`, modo `sin_componentes`)
- Test: `backend/apps/fleet/tests_paquetes_rls.py` (se amplía)

**Interfaces:**
- Consumes: `PaqueteServicio.empresa` (2.6), `PaqueteServicio.dia_estancia|noches|personas_incluidas` (2.1).
- Produces: `paquete_de_sede(sede, slug)` y `paquetes_de_sede(sede)` devuelven `servicios_asociados` completos (servicios de **todas** las empresas del paquete, cada uno serializado con el alcance de su empresa) y `noches`, `es_cruza_empresa`, `permite_anticipo` correctos.

- [ ] **Paso 1: Prueba que falla** (solo puede fallar en PostgreSQL con RLS; en SQLite pasa aunque el código esté mal). Añade a `apps/fleet/tests_paquetes_rls.py` (copia el `setUp`/imports de sus clases vecinas; abajo, lo esencial):

```python
class CatalogoPaqueteDeDosEmpresasRlsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        with scope.como_operador_plataforma():
            self.sede = Sede.objects.create(nombre='Sede CR', slug='sede-cr-test')
            self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca CR', slug='pesca-cr')
            self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp CR', slug='transp-cr')
            s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-cr-s', tipo_servicio='pesca',
                precio_base=Decimal('4000.00'),
            )
            s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-cr-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cruza', slug='cruza-cr',
                precio_ancla=Decimal('9000.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=1)
            PaqueteServicio.objects.create(paquete=paquete, servicio=s_transp, orden=2, personas_incluidas=3)

    def test_el_catalogo_trae_los_componentes_de_las_dos_empresas(self):
        datos = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/cruza-cr/').json()
        self.assertTrue(datos['es_cruza_empresa'])
        empresas = {c['servicio']['empresa_slug'] for c in datos['servicios_asociados']}
        self.assertEqual(empresas, {'pesca-cr', 'transp-cr'})
        traslado = next(c for c in datos['servicios_asociados'] if c['servicio']['slug'] == 'traslado-cr-s')
        self.assertEqual(traslado['personas_incluidas'], 3)

    def test_la_lista_del_catalogo_tambien(self):
        lista = self.client.get(f'/api/sedes/{self.sede.slug}/paquetes/').json()
        paquete = next(p for p in lista if p['slug'] == 'cruza-cr')
        self.assertEqual(len(paquete['servicios_asociados']), 2)
```

- [ ] **Paso 2: Verla fallar en PostgreSQL** (contenedor y rol según `backend/CLAUDE.md`, "Correr la suite contra Postgres en local"):

```bash
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
$PY manage.py test apps.fleet.tests_paquetes_rls.CatalogoPaqueteDeDosEmpresasRlsTests -v 2
```
Esperado: FAIL (un solo componente). Si no puedes levantar Postgres, anota que esta tarea queda sin verificar y verifícala en el gate de la Tarea 5.3.

- [ ] **Paso 3: Implementar el catálogo.** En `apps/fleet/serializers.py`, `PaqueteSerializer`:

```python
    noches = serializers.SerializerMethodField()

    def get_noches(self, obj):
        if self.context.get('sin_componentes'):
            return None  # el catálogo lo completa con los componentes que arma él (catalogo.py)
        return obj.noches

    def get_servicios_asociados(self, obj):
        if self.context.get('sin_componentes'):
            return []  # ídem: componentes de otras empresas no se pueden leer desde aquí (RLS)
        qs = obj.servicios_asociados.filter(servicio__activo=True).order_by('orden')
        return PaqueteServicioSerializer(qs, many=True).data
```
(Sustituye el `noches = serializers.IntegerField(read_only=True)` de la Tarea 2.5 y el `get_servicios_asociados` actual.) En `apps/fleet/catalogo.py`:

```python
def _componentes_de(paquete, empresas):
    """Componentes del paquete legibles bajo RLS. Las filas de PaqueteServicio se leen con el
    alcance de la líder y SIN unir con Servicio; después cada Servicio se lee y serializa con el
    alcance de SU empresa. Los alcances son secuenciales, nunca anidados."""
    with scope.con_empresa(paquete.empresa_lider):
        filas = list(
            paquete.servicios_asociados.order_by('orden').values(
                'id', 'servicio_id', 'orden', 'dia_estancia', 'noches', 'personas_incluidas', 'empresa_id',
            )
        )
    por_id = {empresa.pk: empresa for empresa in empresas}
    componentes = []
    for fila in filas:
        empresa = por_id.get(fila['empresa_id'])
        if empresa is None:
            continue
        with scope.con_empresa(empresa):
            servicio = (
                Servicio.objects.filter(pk=fila['servicio_id'], empresa=empresa, activo=True)
                .prefetch_related('servicio_personalizaciones__personalizacion')
                .first()
            )
            if servicio is None:
                continue
            componentes.append({
                'id': fila['id'], 'servicio_id': fila['servicio_id'], 'orden': fila['orden'],
                'dia_estancia': fila['dia_estancia'], 'noches': fila['noches'],
                'personas_incluidas': fila['personas_incluidas'],
                'servicio': ServicioSerializer(servicio).data,
            })
    return componentes


def _con_componentes(datos, componentes):
    datos = dict(datos)
    datos['servicios_asociados'] = componentes
    datos['noches'] = next(
        (c['noches'] for c in componentes if c['servicio']['estrategia_cupo'] == 'por_noche'), None,
    )
    return datos


def paquetes_de_sede(sede):
    """Lista de dicts serializados de los paquetes activos liderados por cualquiera de las
    Empresas activas de la Sede, con los componentes de todas las empresas que participan."""
    empresas = _empresas_activas_de(sede)
    resultado = []
    for empresa in empresas:
        with scope.con_empresa(empresa):
            paquetes = list(
                Paquete.objects.filter(empresa_lider=empresa, activo=True)
                .select_related('sede', 'empresa_lider').order_by('nombre')
            )
            datos = [PaqueteSerializer(p, context={'sin_componentes': True}).data for p in paquetes]
        for paquete, dato in zip(paquetes, datos):
            resultado.append(_con_componentes(dato, _componentes_de(paquete, empresas)))
    return resultado


def paquete_de_sede(sede, slug):
    """Dict serializado del paquete activo con ese slug en la Sede, o None."""
    empresas = _empresas_activas_de(sede)
    for empresa in empresas:
        with scope.con_empresa(empresa):
            paquete = (
                Paquete.objects.filter(empresa_lider=empresa, slug=slug, activo=True)
                .select_related('sede', 'empresa_lider').first()
            )
            if paquete is None:
                continue
            dato = PaqueteSerializer(paquete, context={'sin_componentes': True}).data
        return _con_componentes(dato, _componentes_de(paquete, empresas))
    return None
```
Actualiza el docstring del módulo: ya no dice que los componentes de otra empresa "no se renderizan todavía".

- [ ] **Paso 4: Verlo pasar** en SQLite y en PostgreSQL:

```bash
$PY manage.py test apps.fleet
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
$PY manage.py test apps.fleet.tests_paquetes_rls apps.fleet.tests_paquetes_api -v 1
```

- [ ] **Paso 5: Commit**

```bash
git add backend/apps/fleet
git commit -m "fix(fleet): el catalogo de paquetes muestra los componentes de todas las empresas bajo RLS"
```

**STOP DURO — Cierre de la Sección 2.** Reportar al dueño: el paquete ya define noches, día y personas; el admin valida en conjunto; el catálogo (incluidos los paquetes de dos empresas bajo RLS, Tareas 2.6 y 2.7) tiene todo lo que el frontend necesita. **El plan de frontend solo puede empezar cuando las Tareas 2.6 y 2.7 estén verificadas en PostgreSQL.**

---

## Sección 3 — Reserva de paquete de una sola empresa

### Tarea 3.1: Personas por componente e inicio del paquete en `Reserva`

> **Corrección tras la revisión externa:** el inicio del paquete **se guarda** en la reserva (`inicio_paquete`) en vez de derivarse de las noches actuales del catálogo. Derivarlo hacía que editar las noches de un paquete moviera hacia atrás el inicio de reservas ya vendidas (sin mover sus ocupaciones) y dejaba sin inicio derivable a las reservas anteriores a este cambio.

**Files:**
- Modify: `backend/apps/bookings/models.py` (`Reserva`, tras `fecha_salida`/`numero_personas`; `Reserva.clean`)
- Create: migración `apps/bookings/migrations/00NN_reserva_paquete_estancia.py`
- Test: `backend/apps/bookings/tests_paquete_estancia.py`

**Interfaces:**
- Produces: `Reserva.personas_por_servicio: dict` (JSON), `Reserva.inicio_paquete: date | None`, `Reserva.personas_de(servicio_id: int) -> int`, `Reserva.fecha_inicio_paquete -> date` (= `inicio_paquete` o, si no hay, `fecha`).

- [ ] **Paso 1: Prueba que falla** — `backend/apps/bookings/tests_paquete_estancia.py`:

```python
"""Reserva de paquete de una sola empresa: personas por componente y estancia."""
from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class FixturePaqueteEstancia:
    """Paquete de una empresa: pesca el día 2 + hospedaje de 3 noches."""

    def sembrar(self):
        self.sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa PE', slug='empresa-pe')
        self.pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca', slug='pesca-pe', tipo_servicio='pesca',
            precio_base=Decimal('4000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Cabaña', slug='cabana-pe', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Fin de semana', slug='finde-pe',
            precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=1, dia_estancia=2, personas_incluidas=3,
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.hotel, orden=2, noches=3, personas_incluidas=2,
        )

    def reserva(self, **extra):
        datos = dict(
            empresa=self.empresa, paquete=self.paquete, fecha=date(2026, 10, 11),
            inicio_paquete=date(2026, 10, 10), fecha_salida=date(2026, 10, 13), hora=time(6),
            numero_personas=3, nombre_cliente='Ana', telefono_cliente='+5216121234567',
            correo_cliente='ana@example.com', canal_origen='web', deslinde_aceptado=True,
            deslinde_nombre='Ana', estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        datos.update(extra)
        return Reserva(**datos)


class PersonasPorServicioTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()

    def test_personas_de_usa_el_mapa_y_cae_en_numero_personas(self):
        reserva = self.reserva(personas_por_servicio={str(self.hotel.pk): 2})
        self.assertEqual(reserva.personas_de(self.hotel.pk), 2)
        self.assertEqual(reserva.personas_de(self.pesca.pk), 3)  # no separado: numero_personas

    def test_fecha_inicio_del_paquete_es_la_guardada(self):
        self.assertEqual(self.reserva().fecha_inicio_paquete, date(2026, 10, 10))

    def test_sin_inicio_guardado_cae_en_la_fecha(self):
        # Reservas anteriores a este campo o de servicio suelto.
        self.assertEqual(self.reserva(inicio_paquete=None).fecha_inicio_paquete, date(2026, 10, 11))

    def test_editar_las_noches_del_paquete_no_mueve_el_inicio_de_una_reserva_vendida(self):
        reserva = self.reserva()
        PaqueteServicio.objects.filter(paquete=self.paquete, servicio=self.hotel).update(noches=5)
        self.assertEqual(reserva.fecha_inicio_paquete, date(2026, 10, 10))

    def test_el_inicio_no_puede_ser_posterior_a_la_actividad_ni_a_la_salida(self):
        with self.assertRaises(ValidationError) as ctx:
            self.reserva(inicio_paquete=date(2026, 10, 12)).full_clean()
        self.assertIn('inicio_paquete', ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            self.reserva(fecha=date(2026, 10, 10), inicio_paquete=date(2026, 10, 10),
                         fecha_salida=date(2026, 10, 10)).full_clean()
        self.assertTrue(ctx.exception.message_dict)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.bookings.tests_paquete_estancia -v 2` → ERROR (`inicio_paquete` / `personas_por_servicio` no son campos).

- [ ] **Paso 3: Implementar.** En `Reserva` (junto a `numero_personas`):

```python
    personas_por_servicio = models.JSONField(
        default=dict, blank=True,
        help_text='Paquete de una sola empresa: personas de cada servicio, {"<servicio_id>": n}. '
                  '`numero_personas` es el del componente operativo principal.',
    )
    inicio_paquete = models.DateField(
        null=True, blank=True,
        help_text='Paquete de una sola empresa: primer día del paquete que eligió el cliente. '
                  '`fecha` es el día de la actividad principal.',
    )
```
y, junto a `noches` / `fecha_fin_servicio`:

```python
    def personas_de(self, servicio_id):
        """Personas que van a ese componente; cae en `numero_personas` si no se separaron."""
        valor = (self.personas_por_servicio or {}).get(str(servicio_id))
        return int(valor) if valor else self.numero_personas

    @property
    def fecha_inicio_paquete(self):
        """Primer día del paquete. Lo guardado al reservar; sin eso (reserva de servicio suelto o
        anterior a este campo), `fecha`. No se deriva de las noches del catálogo: editarlas no
        debe mover reservas ya vendidas."""
        return self.inicio_paquete or self.fecha
```
En `Reserva.clean()`, junto a la comprobación de `fecha_salida` (`if self.fecha_salida and self.fecha_salida <= self.fecha:`), añade:

```python
        if self.inicio_paquete:
            if self.inicio_paquete > self.fecha:
                raise ValidationError({'inicio_paquete': 'El inicio del paquete no puede ser posterior a la actividad.'})
            if self.fecha_salida and self.fecha_salida <= self.inicio_paquete:
                raise ValidationError({'fecha_salida': 'La salida debe ser posterior al inicio del paquete.'})
```

- [ ] **Paso 4: Migración y verificación**

```bash
$PY manage.py makemigrations bookings -n reserva_paquete_estancia
$PY manage.py test apps.bookings.tests_paquete_estancia -v 2
```

- [ ] **Paso 5: Commit**

```bash
git add backend/apps/bookings
git commit -m "feat(bookings): personas por componente e inicio guardado del paquete en Reserva"
```

### Tarea 3.2: El serializador deriva fechas y personas del paquete

**Files:**
- Modify: `backend/apps/bookings/serializers.py` (`ReservaCheckoutSerializer.validate`, campos)
- Test: `backend/apps/bookings/tests_paquete_estancia.py` (se amplía)
- Ajustar: `backend/apps/bookings/tests_checkout_paquete.py`, `tests_reserva_paquete.py`, `tests_checkout_serializer.py` si usan hospedaje en paquete

**Interfaces:**
- Consumes: `calendario_paquete.*` (2.4), `PaqueteServicio.personas_incluidas` (2.1).
- Produces: la reserva de un paquete queda con `fecha` = ancla, `fecha_salida` = salida derivada, `numero_personas` = las del componente principal y `personas_por_servicio` validado; `fecha_salida` enviada por el cliente se rechaza. Campo de solo lectura `fecha_inicio_paquete` en la respuesta.

- [ ] **Paso 1: Pruebas que fallan.** Antes, abre `apps/bookings/tests_checkout_serializer.py` y copia de ahí el payload mínimo válido y cómo se arma `context` (mismo patrón); a continuación añade a `tests_paquete_estancia.py` (ajusta los nombres de campos del payload al de ese archivo si difieren):

```python
import uuid

from apps.bookings.serializers import ReservaCheckoutSerializer


class SerializadorPaqueteTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()

    def payload(self, **extra):
        datos = {
            'checkout_id': str(uuid.uuid4()), 'fecha': '2026-10-10', 'hora': '06:00:00',
            'numero_personas': 3, 'nombre_cliente': 'Ana Ruiz', 'telefono_cliente': '+5216121234567',
            'correo_cliente': 'ana@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Ana Ruiz', 'paquete': self.paquete.slug, 'personalizaciones': [],
            'personas_por_servicio': {str(self.pesca.pk): 3, str(self.hotel.pk): 2},
        }
        datos.update(extra)
        return datos

    def validar(self, **extra):
        serializador = ReservaCheckoutSerializer(data=self.payload(**extra), context={'empresa': self.empresa})
        return serializador, serializador.is_valid()

    def test_deriva_fecha_ancla_salida_y_personas_principales(self):
        serializador, valido = self.validar()
        self.assertTrue(valido, serializador.errors)
        datos = serializador.validated_data
        self.assertEqual(str(datos['fecha']), '2026-10-11')          # inicio 10 + (día 2 − 1)
        self.assertEqual(str(datos['fecha_salida']), '2026-10-13')   # inicio + 3 noches
        self.assertEqual(datos['numero_personas'], 3)                # las de la pesca (componente operativo)

    def test_rechaza_fecha_de_salida_enviada_por_el_cliente(self):
        serializador, valido = self.validar(fecha_salida='2026-10-20')
        self.assertFalse(valido)
        self.assertIn('fecha_salida', serializador.errors)

    def test_rechaza_mas_personas_que_las_incluidas(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 4, str(self.hotel.pk): 2})
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_exige_personas_de_cada_servicio_del_paquete(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 2})
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_menos_personas_en_el_hospedaje_es_valido(self):
        serializador, valido = self.validar(personas_por_servicio={str(self.pesca.pk): 3, str(self.hotel.pk): 1})
        self.assertTrue(valido, serializador.errors)
```

- [ ] **Paso 1b: Pruebas adicionales** (guardas de venta y reglas nuevas). Añade a `SerializadorPaqueteTests`:

```python
    def test_guarda_el_inicio_elegido_por_el_cliente(self):
        serializador, valido = self.validar()
        self.assertTrue(valido, serializador.errors)
        self.assertEqual(str(serializador.validated_data['inicio_paquete']), '2026-10-10')

    def test_rechaza_un_paquete_de_dos_empresas(self):
        otra = Empresa.objects.create(sede=self.sede, nombre='Transp PE', slug='transp-pe')
        traslado = Servicio.objects.create(
            empresa=otra, nombre='Traslado', slug='traslado-pe', tipo_servicio='transporte',
            estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=traslado, orden=3)
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('paquete', serializador.errors)

    def test_rechaza_un_paquete_mal_configurado(self):
        PaqueteServicio.objects.filter(paquete=self.paquete, servicio=self.hotel).update(noches=None)
        serializador, valido = self.validar()
        self.assertFalse(valido)
        self.assertIn('paquete', serializador.errors)

    def test_las_actividades_deben_ir_con_las_mismas_personas(self):
        segunda = Servicio.objects.create(
            empresa=self.empresa, nombre='Paseo', slug='paseo-pe', tipo_servicio='paseo',
            precio_base=Decimal('1000.00'),
        )
        PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=segunda, orden=3, dia_estancia=2, personas_incluidas=3,
        )
        serializador, valido = self.validar(personas_por_servicio={
            str(self.pesca.pk): 3, str(self.hotel.pk): 2, str(segunda.pk): 2,
        })
        self.assertFalse(valido)
        self.assertIn('personas_por_servicio', serializador.errors)

    def test_guardar_y_reenviar_actualiza_la_misma_reserva(self):
        # create() y update(): el reenvío del mismo checkout no duplica ni pierde el contrato nuevo.
        from rest_framework.test import APIRequestFactory

        peticion = APIRequestFactory().post('/x')
        peticion.META['REMOTE_ADDR'] = '127.0.0.1'
        contexto = {'empresa': self.empresa, 'request': peticion}
        primero = ReservaCheckoutSerializer(data=self.payload(), context=contexto)
        self.assertTrue(primero.is_valid(), primero.errors)
        reserva = primero.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio_paquete, date(2026, 10, 10))
        self.assertEqual(reserva.personas_de(self.hotel.pk), 2)
        segundo = ReservaCheckoutSerializer(
            reserva, data=self.payload(fecha='2026-10-12', checkout_id=str(reserva.checkout_id)), context=contexto,
        )
        self.assertTrue(segundo.is_valid(), segundo.errors)
        segundo.save()
        reserva.refresh_from_db()
        self.assertEqual(reserva.inicio_paquete, date(2026, 10, 12))
        self.assertEqual(Reserva.objects.filter(paquete=self.paquete).count(), 1)
```
(Añade `from datetime import date` al archivo de pruebas si falta. Si `save()` exige más campos de contexto (`captcha`, IP), copia el patrón de `apps/bookings/tests_checkout_serializer.py`.)

- [ ] **Paso 2: Verlas fallar** — `$PY manage.py test apps.bookings.tests_paquete_estancia -v 2` → FAIL (campo desconocido / sin derivación).

- [ ] **Paso 3: Implementar.** En `ReservaCheckoutSerializer` (imports: `from apps.fleet.calendario_paquete import ComponenteCalendario, fecha_ancla, fecha_salida as calcular_salida`):

1. Campo nuevo y de solo lectura:

```python
    personas_por_servicio = serializers.DictField(
        child=serializers.IntegerField(min_value=1), required=False,
    )
    fecha_inicio_paquete = serializers.DateField(read_only=True)
```
y en `Meta.fields` añade `'personas_por_servicio', 'fecha_inicio_paquete'`.

2. En `validate()`, **reemplaza** el bloque `es_hospedaje = ...` hasta el `else` que rechaza `fecha_salida` (líneas de `es_hospedaje`, `fecha`, `fecha_salida`, y los dos `if/else`) por:

```python
        fecha = attrs.get('fecha', getattr(self.instance, 'fecha_inicio_paquete', None) if self.instance else None)
        fecha_salida_cliente = attrs.get('fecha_salida')

        if paquete:
            # El paquete define noches, día de cada servicio y lugares incluidos: el
            # cliente solo elige el inicio y cuántas personas van a cada servicio.
            if paquete.es_cruza_empresa:
                raise serializers.ValidationError({
                    'paquete': 'Este paquete es de dos empresas y se reserva como orden, no como reserva.',
                })
            try:
                paquete.validar_configuracion()
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'paquete': exc.messages})
            if fecha_salida_cliente:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida la define el paquete.'})
            attrs = self._derivar_de_paquete(attrs, fecha, componentes_activos)
        else:
            es_hospedaje = bool(servicio and servicio.estrategia_cupo == 'por_noche')
            fecha_salida = attrs.get('fecha_salida', getattr(self.instance, 'fecha_salida', None) if self.instance else None)
            if es_hospedaje:
                if not fecha_salida:
                    raise serializers.ValidationError({'fecha_salida': 'La fecha de salida es requerida para servicios con hospedaje.'})
                if fecha and fecha_salida <= fecha:
                    raise serializers.ValidationError({'fecha_salida': 'La fecha de salida debe ser posterior a la fecha de llegada.'})
            elif fecha_salida:
                raise serializers.ValidationError({'fecha_salida': 'La fecha de salida solo aplica para servicios con hospedaje.'})
```
3. En el bloque final de capacidad (`numero_personas = attrs.get(...)`), envuélvelo en `if not paquete:` (con paquete la capacidad se valida por componente en `_derivar_de_paquete`).

4. Método nuevo:

```python
    def _derivar_de_paquete(self, attrs, inicio, componentes):
        from apps.fleet.models import Paquete  # noqa: F401 (tipado)

        if inicio is None:
            raise serializers.ValidationError({'fecha': 'Elige la fecha de inicio del paquete.'})
        personas = attrs.get('personas_por_servicio', {})
        esperadas = {str(ps.servicio_id): ps for ps in componentes}
        if set(personas) != set(esperadas):
            raise serializers.ValidationError({
                'personas_por_servicio': 'Indica cuántas personas van a cada servicio del paquete.',
            })
        for clave, ps in esperadas.items():
            if personas[clave] > ps.personas_incluidas:
                raise serializers.ValidationError({
                    'personas_por_servicio': (
                        f'"{ps.servicio.nombre}" incluye {ps.personas_incluidas} lugar(es) en este paquete.'
                    ),
                })
            if ps.servicio.estrategia_cupo == 'por_noche':
                habitaciones = ps.servicio.recursos.filter(activo=True)
                if habitaciones.exists() and personas[clave] > max(r.capacidad_maxima for r in habitaciones):
                    raise serializers.ValidationError({
                        'personas_por_servicio': f'Ninguna habitación de "{ps.servicio.nombre}" admite {personas[clave]} personas.',
                    })

        # El motor de cupo cuenta `numero_personas` (las del componente principal) para todas las
        # actividades del día; por eso todas las actividades del paquete van con el mismo número.
        actividades = {
            personas[str(ps.servicio_id)] for ps in componentes if ps.servicio.estrategia_cupo == 'por_recurso_dia'
        }
        if len(actividades) > 1:
            raise serializers.ValidationError({
                'personas_por_servicio': 'Las actividades del paquete van con el mismo número de personas.',
            })

        calendario = [
            ComponenteCalendario(ps.dia_estancia, ps.servicio.estrategia_cupo, ps.noches) for ps in componentes
        ]
        principal = next(
            (ps for ps in componentes if ps.servicio.estrategia_cupo == 'por_recurso_dia'),
            componentes[0] if componentes else None,
        )
        attrs['fecha'] = fecha_ancla(inicio, calendario)
        attrs['inicio_paquete'] = inicio
        attrs['fecha_salida'] = calcular_salida(inicio, calendario)
        if principal is not None:
            attrs['numero_personas'] = personas[str(principal.servicio_id)]
        return attrs
```
`componentes` llega ordenado por `orden` (ajusta la consulta de `componentes_activos` en `validate` con `.order_by('orden')` si no lo está).

- [ ] **Paso 4: Ajustar pruebas viejas.**

```bash
$PY manage.py test apps.bookings -v 1
```
Todo lo que mande un paquete (con o sin hospedaje) al serializador necesita el contrato nuevo: `personas_por_servicio` con **cada** servicio del paquete, sin `fecha_salida`, y el `PaqueteServicio` con `noches` (hospedaje) y `personas_incluidas` coherentes. Inventario verificado en la revisión externa (busca además con `grep -rn "paquete" apps --include=tests*.py`):
- `apps/bookings/tests_checkout_paquete.py` y `apps/bookings/tests_reserva_paquete.py`.
- `apps/bookings/tests_checkout_serializer.py` ≈ L149, L248, L274 y el reenvío ≈ L348: **también los casos sin hospedaje** deben mandar `personas_por_servicio`; el reenvío completo debe seguir siendo idempotente.
- `apps/bookings/tests.py` ≈ L2429 y los fixtures de `apps/payments/tests*.py` que crean reservas de paquete.
Conserva la intención de cada prueba; no dejes fixtures inválidos (`objects.create` omite validadores).

- [ ] **Paso 5: Verlo pasar**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
```

- [ ] **Paso 6: Commit**

```bash
git add backend/apps/bookings
git commit -m "feat(bookings): el paquete define fechas y lugares; el cliente elige inicio y personas por servicio"
```

### Tarea 3.3: Cupo del paquete por componente (personas y fechas propias)

**Files:**
- Modify: `backend/apps/bookings/models.py` (`_validar_cupo_de_paquete` ≈ L224)
- Modify: `backend/apps/bookings/cupo/confirmacion.py` (`_asignar_cupo_hospedaje`, Caso B)
- Test: `backend/apps/bookings/tests_paquete_estancia.py` (se amplía)

**Interfaces:**
- Consumes: `Reserva.personas_de`, `Reserva.fecha_inicio_paquete` (3.1).
- Produces: `_asignar_cupo_hospedaje(reserva, servicio, es_componente=False, *, desde=None, hasta=None, personas=None)`; el paquete de una empresa ocupa la habitación de `fecha_inicio_paquete` a `fecha_salida` y valida la pesca el día ancla con las personas de la pesca.

- [ ] **Paso 1: Pruebas que fallan.** Añade a `tests_paquete_estancia.py`:

```python
from unittest import mock

from apps.bookings.cupo.confirmacion import reservar_cupo_al_confirmar
from apps.fleet.models import Recurso


class CupoPorComponenteTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()
        Recurso.objects.create(
            empresa=self.empresa, servicio=self.hotel, nombre='Cabaña 1', capacidad_maxima=4,
        )

    def _reserva_pagada(self, personas_pesca=3, personas_hotel=1):
        reserva = self.reserva(
            estado=Reserva.Estado.PAGADA, fecha=date(2026, 10, 11), fecha_salida=date(2026, 10, 13),
            numero_personas=personas_pesca,
            personas_por_servicio={str(self.pesca.pk): personas_pesca, str(self.hotel.pk): personas_hotel},
        )
        reserva.save()
        return reserva

    @mock.patch('apps.bookings.cupo.confirmacion.evaluar_cupo', return_value=None)
    @mock.patch('apps.bookings.cupo.confirmacion.bloquear_cupo')
    def test_la_habitacion_se_ocupa_desde_el_inicio_del_paquete(self, _candado, evaluar):
        reserva = self._reserva_pagada()
        reservar_cupo_al_confirmar(reserva)
        ocupacion = reserva.ocupaciones.get()
        self.assertEqual(ocupacion.fecha_inicio, date(2026, 10, 10))
        self.assertEqual(ocupacion.fecha_fin, date(2026, 10, 13))
        # La pesca se valida el día 2 con las personas de la pesca, no las del hospedaje.
        llamada = evaluar.call_args
        self.assertEqual(llamada.args[0], date(2026, 10, 11))
        self.assertEqual(llamada.args[1], 3)
        self.assertEqual(reserva.componentes.count(), 2)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.bookings.tests_paquete_estancia.CupoPorComponenteTests -v 2` → FAIL (la ocupación arranca el 11 y usa las mismas personas).

- [ ] **Paso 3: Implementar `confirmacion.py`.** Cambia la firma y el cuerpo de `_asignar_cupo_hospedaje`:

```python
def _asignar_cupo_hospedaje(reserva, servicio, es_componente=False, *, desde=None, hasta=None, personas=None):
    desde = desde or reserva.fecha
    hasta = hasta or reserva.fecha_fin_servicio
    personas = personas or reserva.numero_personas
    # ... (el bloque de recursos_candidatos y bloquear_recurso queda igual)
    recursos_con_ocupaciones = obtener_recursos_con_ocupaciones(
        desde=desde, hasta=hasta, empresa=reserva.empresa, servicio=servicio, excluir_pk=reserva.pk,
    )
    libres = recursos_disponibles_en_rango(recursos_con_ocupaciones, desde, hasta)
    elegidos = elegir_recursos(libres, personas=personas, cantidad=1)
    # ... (el mensaje de SinCupoError queda igual)
    if not reserva.ocupaciones.filter(recurso__servicio=servicio).exists():
        for rec_id in elegidos:
            ReservaOcupacion.objects.create(
                reserva=reserva, recurso_id=rec_id, empresa=reserva.empresa,
                fecha_inicio=desde, fecha_fin=hasta, ocupa_cupo=True,
            )
```
En el **Caso B** (paquete con componentes, `reserva.orden_id is None`), usa las personas del componente y el inicio derivado:

```python
            if estrategia == 'por_recurso_dia':
                bloquear_cupo(reserva.empresa_id, reserva.fecha, servicio_id=servicio.pk)
                motivo = evaluar_cupo(
                    reserva.fecha, reserva.personas_de(servicio.pk), reserva.empresa,
                    excluir_pk=reserva.pk, estrategia_cupo='por_recurso_dia', servicio_id=servicio.pk,
                )
                ...
            elif estrategia == 'por_noche':
                _asignar_cupo_hospedaje(
                    reserva, servicio, es_componente=True,
                    desde=reserva.fecha_inicio_paquete, hasta=reserva.fecha_fin_servicio,
                    personas=reserva.personas_de(servicio.pk),
                )
```
(Los Casos A, C y D no cambian.)

- [ ] **Paso 4: `Reserva.clean` (modelo).** En `_validar_cupo_de_paquete` usa el componente y las fechas derivadas:

```python
def _validar_cupo_de_paquete(reserva):
    for ps in reserva.paquete.servicios_asociados.select_related('servicio').all():
        estrategia = ps.servicio.estrategia_cupo
        personas = reserva.personas_de(ps.servicio_id)
        if estrategia == 'por_recurso_dia':
            motivo = evaluar_cupo(
                reserva.fecha, personas, reserva.empresa,
                excluir_pk=reserva.pk, estrategia_cupo='por_recurso_dia', servicio_id=ps.servicio_id,
            )
            # ... (raise igual)
        elif estrategia == 'por_noche':
            disponible = evaluar_disponibilidad_hospedaje(
                check_in=reserva.fecha_inicio_paquete, check_out=reserva.fecha_fin_servicio,
                personas=personas, empresa=reserva.empresa, servicio=ps.servicio, excluir_pk=reserva.pk,
            )
            # ... (raise igual)
```
Nota: con `dia_estancia ≤ noches` (regla 5) se cumple siempre `fecha < fecha_salida`, así que el chequeo `fecha_salida <= fecha` de `Reserva.clean` no se dispara.

- [ ] **Paso 4b: Tope de personas de un paquete.** `Reserva._validar_tope_personas` aplica el tope global de 5 cuando la reserva no tiene servicio (todo paquete de una empresa), aunque el hospedaje admita más: un paquete de hospedaje con 6 lugares fallaría al guardar aunque el serializador lo aceptara. El tope de un paquete es **por componente** (`personas_incluidas`, ya validado contra el máximo del servicio en las reglas de paquete y en el serializador). Prueba en `tests_paquete_estancia.py`:

```python
class TopeDePersonasDelPaqueteTests(FixturePaqueteEstancia, OperadorTestCase):
    def setUp(self):
        self.sembrar()

    def test_un_paquete_de_hospedaje_admite_mas_de_cinco_personas(self):
        solo_hotel = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Solo hotel', slug='solo-hotel-pe',
            precio_ancla=Decimal('5000.00'),
        )
        PaqueteServicio.objects.create(paquete=solo_hotel, servicio=self.hotel, orden=1, noches=2, personas_incluidas=6)
        reserva = self.reserva(
            paquete=solo_hotel, numero_personas=6, fecha=date(2026, 10, 10), inicio_paquete=date(2026, 10, 10),
            fecha_salida=date(2026, 10, 12), personas_por_servicio={str(self.hotel.pk): 6},
        )
        reserva.full_clean()  # no debe lanzar
```
y en `Reserva` (`apps/bookings/models.py`):

```python
    def _validar_tope_personas(self):
        if self.paquete_id:
            # Un paquete tiene tope por componente (`personas_incluidas`), validado al reservar.
            return
        tope = MAX_PERSONAS
        # ... (el resto queda igual)
```

- [ ] **Paso 5: Verlo pasar y regresiones**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
grep -rn "\.noches" apps --include=*.py | grep -v "tests\|migrations"
```
Esperado: `OK`; el `grep` solo debe mostrar `estrategias_precio.py` y `payments/views.py` (servicios sueltos), nunca lógica de paquete.

- [ ] **Paso 6: Commit**

```bash
git add backend/apps/bookings
git commit -m "feat(bookings): cupo del paquete usa personas y fechas de cada componente"
```

### Tarea 3.4: Extras por persona con las personas del servicio dueño

**Files:**
- Modify: `backend/apps/payments/pricing.py` (`precio_paquete_total`)
- Modify: `backend/apps/payments/views.py` (`_resolver_personalizaciones`, ≈ L254-L266)
- Test: `backend/apps/payments/tests_extras_por_componente.py`

**Interfaces:**
- Produces: `precio_paquete_total(paquete, *, personalizaciones_extra=None, personas=1, moneda='MXN', personas_por_servicio=None)`; en cobro, `cantidad_efectiva/cargo_personalizacion` reciben `reserva.personas_de(sp.servicio_id)`.

- [ ] **Paso 1: Prueba que falla** — `backend/apps/payments/tests_extras_por_componente.py`:

```python
"""Un extra por persona multiplica por las personas de SU servicio."""
from decimal import Decimal

from apps.fleet.models import Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.pricing import precio_paquete_total
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class ExtrasPorComponenteTests(OperadorTestCase):
    def setUp(self):
        sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        empresa = Empresa.objects.create(sede=sede, nombre='Empresa EC', slug='empresa-ec')
        self.pesca = Servicio.objects.create(
            empresa=empresa, nombre='Pesca', slug='pesca-ec', tipo_servicio='pesca', precio_base=Decimal('4000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=empresa, nombre='Cabaña', slug='cabana-ec', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche',
        )
        self.paquete = Paquete.objects.create(
            sede=sede, empresa_lider=empresa, nombre='P', slug='p-ec', precio_ancla=Decimal('9500.00'),
        )
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.pesca, orden=1, personas_incluidas=4)
        PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.hotel, orden=2, noches=2)
        brunch = Personalizacion.objects.create(
            empresa=empresa, nombre='Brunch', tipo_interaccion='check', cobrar_por_persona=True,
        )
        desayuno = Personalizacion.objects.create(
            empresa=empresa, nombre='Desayuno', tipo_interaccion='check', cobrar_por_persona=True,
        )
        self.sp_brunch = ServicioPersonalizacion.objects.create(
            servicio=self.pesca, personalizacion=brunch, precio=Decimal('100.00'),
        )
        self.sp_desayuno = ServicioPersonalizacion.objects.create(
            servicio=self.hotel, personalizacion=desayuno, precio=Decimal('50.00'),
        )

    def test_cada_extra_multiplica_por_las_personas_de_su_servicio(self):
        total = precio_paquete_total(
            self.paquete,
            personalizaciones_extra=[self.sp_brunch.pk, self.sp_desayuno.pk],
            personas=4,
            personas_por_servicio={self.pesca.pk: 3, self.hotel.pk: 2},
        )
        # 9500 + brunch 100×3 + desayuno 50×2
        self.assertEqual(total, Decimal('9900.00'))

    def test_sin_mapa_usa_las_personas_generales(self):
        total = precio_paquete_total(
            self.paquete, personalizaciones_extra=[self.sp_brunch.pk], personas=4,
        )
        self.assertEqual(total, Decimal('9900.00'))
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.payments.tests_extras_por_componente -v 2` → FAIL (`personas_por_servicio` inesperado).

- [ ] **Paso 3: Implementar `pricing.py`.** Añade el parámetro y úsalo dentro del bucle:

```python
def precio_paquete_total(
    paquete, *, personalizaciones_extra=None, personas: int = 1, moneda: str = 'MXN',
    personas_por_servicio: dict[int, int] | None = None,
) -> Decimal | None:
    ...
    for ps in paquete.servicios_asociados.filter(servicio__activo=True).select_related('servicio'):
        personas_del_servicio = (personas_por_servicio or {}).get(ps.servicio_id, personas)
        for sp in ps.servicio.servicio_personalizaciones.filter(...).select_related('personalizacion'):
            ...
            cargo = cargo_personalizacion(
                sp.precio_en(moneda),
                cobrar_por_persona=p.cobrar_por_persona,
                cantidad_editable=p.cantidad_editable,
                personas=personas_del_servicio,
                cantidad=extras_map[sp.pk],
            )
```
(ajusta el docstring: "cada personalización por persona se multiplica por las personas de su servicio").

- [ ] **Paso 4: Cobro.** En `CrearPagoView._resolver_personalizaciones`, dentro del bucle de `seleccionadas`, cambia las dos apariciones de `personas=reserva.numero_personas` (en `cantidad_efectiva` y `cargo_personalizacion`) por `personas=reserva.personas_de(sp.servicio_id)`.

- [ ] **Paso 5: Verlo pasar y commit**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/payments
git commit -m "feat(payments): extras por persona usan las personas del servicio dueno"
```

### Tarea 3.5: La confirmación devuelve el inicio del paquete

**Files:**
- Modify: `backend/apps/payments/views.py` (`EstadoReservaView._get`, ≈ L409)
- Test: `backend/apps/payments/tests_extras_por_componente.py` (o el archivo de estado de reserva existente)

**Interfaces:**
- Produces: la respuesta `pagada` incluye `fecha_inicio_paquete` (ISO) y `personas_por_servicio`.

- [ ] **Paso 1: Prueba que falla.** Busca la prueba existente de `EstadoReservaView` (`grep -n "reservas/estado" apps/payments/tests*.py`) y añade una hermana que cree una reserva pagada de un paquete de estancia (usa `FixturePaqueteEstancia` de `apps.bookings.tests_paquete_estancia`) y espere `fecha_inicio_paquete == '2026-10-10'` y `personas_por_servicio` con las dos claves.

- [ ] **Paso 2: Implementar.** En el diccionario de la rama `pagada` añade:

```python
                'fecha_inicio_paquete': reserva.fecha_inicio_paquete,
                'personas_por_servicio': reserva.personas_por_servicio,
```

- [ ] **Paso 2b: Recuperación, correo y admin leen el inicio del paquete.** (a) En la rama `pendiente_pago` de `EstadoReservaView` (≈ L436-L450, la que hoy devuelve `'estado': 'pendiente_pago'`) añade los mismos dos campos, para que el frontend pueda reponer un pedido a medias: `'fecha_inicio_paquete': reserva.fecha_inicio_paquete` y `'personas_por_servicio': reserva.personas_por_servicio`. (b) Correo de confirmación (`apps/notifications/services.py` ≈ L120): cambia `<strong>Fecha:</strong> {reserva.fecha}` por `{reserva.fecha_inicio_paquete}` (para un paquete es el primer día, no el día de la pesca; para lo demás es `fecha`). (c) Admin de checkouts abandonados (`apps/bookings/admin.py` ≈ L607, mensaje de WhatsApp): `{obj.fecha}` por `{obj.fecha_inicio_paquete}`. Prueba: la respuesta `pendiente_pago` trae `fecha_inicio_paquete` y `personas_por_servicio` (usa la misma prueba de estado de reserva del Paso 1).

- [ ] **Paso 3: Verificar y commit**

```bash
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/payments
git commit -m "feat(payments): el estado de la reserva devuelve inicio del paquete y personas por servicio"
```

**STOP DURO — Cierre de la Sección 3.** Reportar al dueño: paquete de una empresa con estancia definida por el paquete, personas por componente, cupo correcto, extras por persona correctos.

---

## Sección 4 — Órdenes de dos empresas

### Tarea 4.1: Helper compartido de selección de extras

**Files:**
- Create: `backend/apps/bookings/personalizaciones.py`
- Modify: `backend/apps/bookings/serializers.py` (`_validar_respuesta_personalizacion`, `_sincronizar_personalizaciones`)
- Test: `backend/apps/bookings/tests_helper_personalizaciones.py`

**Interfaces:**
- Produces:
  - `validar_respuesta(sp, item) -> None` (lanza `django.core.exceptions.ValidationError`).
  - `validar_seleccion(servicio, items) -> None`: cada `id` pertenece a `servicio`, activo, sin repetir; falta responder lo obligatorio no-check. Lanza `ValidationError({'personalizaciones': ...})`.
  - `sincronizar(reserva, items) -> None`: reescribe la selección completa.

- [ ] **Paso 1: Prueba que falla** — `backend/apps/bookings/tests_helper_personalizaciones.py`:

```python
from datetime import date, time
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.bookings import personalizaciones
from apps.bookings.models import Reserva
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class HelperPersonalizacionesTests(OperadorTestCase):
    def setUp(self):
        sede, _ = Sede.objects.get_or_create(slug='la-paz', defaults={'nombre': 'La Paz'})
        self.empresa = Empresa.objects.create(sede=sede, nombre='Empresa HP', slug='empresa-hp')
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Tour', slug='tour-hp', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        otro = Servicio.objects.create(
            empresa=self.empresa, nombre='Otro', slug='otro-hp', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        check = Personalizacion.objects.create(empresa=self.empresa, nombre='Brunch', tipo_interaccion='check')
        texto = Personalizacion.objects.create(empresa=self.empresa, nombre='Alergias', tipo_interaccion='input_texto')
        self.sp_check = ServicioPersonalizacion.objects.create(servicio=self.servicio, personalizacion=check, precio=Decimal('100.00'))
        self.sp_texto = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=texto, obligatorio=True,
        )
        self.sp_ajeno = ServicioPersonalizacion.objects.create(servicio=otro, personalizacion=check, precio=Decimal('100.00'))
        self.reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio, fecha=date(2026, 11, 1), hora=time(9),
            numero_personas=2, nombre_cliente='Ana', telefono_cliente='1234567890',
            correo_cliente='ana@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
        )

    def test_seleccion_valida(self):
        personalizaciones.validar_seleccion(
            self.servicio, [{'id': self.sp_check.pk}, {'id': self.sp_texto.pk, 'respuesta': 'Ninguna'}],
        )

    def test_rechaza_un_extra_de_otro_servicio(self):
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(
                self.servicio, [{'id': self.sp_ajeno.pk}, {'id': self.sp_texto.pk, 'respuesta': 'x'}],
            )

    def test_rechaza_repetidos_y_falta_de_obligatorio(self):
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(self.servicio, [{'id': self.sp_check.pk}, {'id': self.sp_check.pk}])
        with self.assertRaises(ValidationError):
            personalizaciones.validar_seleccion(self.servicio, [{'id': self.sp_check.pk}])

    def test_sincronizar_reescribe_y_omite_respuestas_vacias(self):
        personalizaciones.sincronizar(self.reserva, [{'id': self.sp_check.pk}, {'id': self.sp_texto.pk, 'respuesta': '  '}])
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.count(), 1)
        personalizaciones.sincronizar(self.reserva, [])
        self.assertEqual(self.reserva.personalizaciones_seleccionadas.count(), 0)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.bookings.tests_helper_personalizaciones -v 2` → ERROR (módulo inexistente).

- [ ] **Paso 3: Implementar** — `backend/apps/bookings/personalizaciones.py`:

```python
"""Selección de extras (personalizaciones) de una Reserva: validar y sincronizar.

Compartido por el serializador de reservas y por la creación de órdenes."""
from django.core.exceptions import ValidationError

from apps.bookings.models import ReservaPersonalizacion
from apps.fleet.models import ServicioPersonalizacion


def validar_respuesta(sp, item):
    """Lanza ValidationError si la respuesta del cliente no cabe en la personalización."""
    ReservaPersonalizacion(
        servicio_personalizacion=sp,
        cantidad=item.get('cantidad', 1),
        respuesta=item.get('respuesta', ''),
    ).clean()


def validar_seleccion(servicio, items):
    """Cada extra pertenece a `servicio`, está activo y no se repite; nada obligatorio queda sin responder."""
    disponibles = {
        sp.pk: sp
        for sp in ServicioPersonalizacion.objects.filter(
            servicio=servicio, activo=True, personalizacion__activo=True,
        ).select_related('personalizacion')
    }
    vistos = set()
    for item in items:
        sp = disponibles.get(item.get('id'))
        if sp is None or sp.pk in vistos:
            raise ValidationError({'personalizaciones': 'Selección inválida o repetida.'})
        vistos.add(sp.pk)
        validar_respuesta(sp, item)
    for sp in disponibles.values():
        if sp.personalizacion.tipo_interaccion != 'check' and sp.obligatorio and sp.pk not in vistos:
            raise ValidationError({'personalizaciones': f'Falta responder: {sp.personalizacion.nombre}.'})


def sincronizar(reserva, items):
    """Reescribe la selección completa de la reserva (lista vacía = borra lo que hubiera)."""
    reserva.personalizaciones_seleccionadas.all().delete()
    for item in items:
        respuesta = item.get('respuesta', '')
        sp = ServicioPersonalizacion.objects.select_related('personalizacion').get(pk=item['id'])
        if sp.personalizacion.tipo_interaccion != 'check' and not respuesta.strip():
            continue
        fila = ReservaPersonalizacion(
            reserva=reserva, servicio_personalizacion=sp,
            cantidad=item.get('cantidad', 1), respuesta=respuesta,
        )
        fila.full_clean()
        fila.save()
```

- [ ] **Paso 4: El serializador usa el helper** (sin cambiar su comportamiento). En `ReservaCheckoutSerializer`:

```python
    def _validar_respuesta_personalizacion(self, sp, item):
        try:
            personalizaciones.validar_respuesta(sp, item)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'personalizaciones': exc.messages})

    def _sincronizar_personalizaciones(self, reserva, items_elegidos):
        aplica = reserva.paquete_id or reserva.servicio_id
        if not aplica:
            reserva.personalizaciones_seleccionadas.all().delete()
            return
        personalizaciones.sincronizar(reserva, items_elegidos)
```
con `from apps.bookings import personalizaciones` en los imports.

- [ ] **Paso 5: Verificar (refactor: nada debe cambiar) y commit**

```bash
$PY manage.py test apps.bookings apps.payments
git add backend/apps/bookings
git commit -m "refactor(bookings): helper compartido para validar y sincronizar extras"
```

### Tarea 4.2: Cotizar y congelar extras en un módulo de dinero

**Files:**
- Create: `backend/apps/payments/extras.py`
- Modify: `backend/apps/payments/views.py` (`CrearPagoView._resolver_personalizaciones` y el bloque de congelado)
- Test: las pruebas existentes (`tests_personalizaciones.py`) son la red de seguridad; añade `backend/apps/payments/tests_extras_modulo.py`

**Interfaces:**
- Produces:
  - `cotizar_personalizaciones(reserva) -> tuple[Decimal | int, list, list, str | None]` = `(cargo_total, a_borrar, a_congelar, error)` (misma forma que el método actual).
  - `congelar_personalizaciones(a_borrar, a_congelar) -> None`.

- [ ] **Paso 1: Prueba que falla** — `backend/apps/payments/tests_extras_modulo.py`:

```python
from datetime import date, time
from decimal import Decimal

from apps.bookings.models import Reserva, ReservaPersonalizacion
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.payments.extras import congelar_personalizaciones, cotizar_personalizaciones
from apps.testing import ApiTestCase


class ExtrasModuloTests(ApiTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(
            empresa=self.empresa, nombre='Tour', slug='tour-em', tipo_servicio='otro',
            estrategia_cupo='bajo_demanda', estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'),
        )
        check = Personalizacion.objects.create(
            empresa=self.empresa, nombre='Brunch', tipo_interaccion='check', cobrar_por_persona=True,
        )
        self.sp = ServicioPersonalizacion.objects.create(
            servicio=self.servicio, personalizacion=check, precio=Decimal('100.00'), precio_usd=Decimal('6.00'),
        )
        self.reserva = Reserva.objects.create(
            empresa=self.empresa, servicio=self.servicio, fecha=date(2026, 11, 1), hora=time(9),
            numero_personas=3, nombre_cliente='Ana', telefono_cliente='1234567890',
            correo_cliente='ana@example.com', moneda='MXN', estado=Reserva.Estado.PENDIENTE_PAGO,
        )
        self.fila = ReservaPersonalizacion.objects.create(reserva=self.reserva, servicio_personalizacion=self.sp)

    def test_cotiza_por_persona_sin_escribir(self):
        cargo, a_borrar, a_congelar, error = cotizar_personalizaciones(self.reserva)
        self.assertIsNone(error)
        self.assertEqual(cargo, Decimal('300.00'))
        self.assertEqual(a_borrar, [])
        self.fila.refresh_from_db()
        self.assertIsNone(self.fila.precio_unitario)  # cotizar no escribe

    def test_congelar_guarda_precio_y_cantidad(self):
        _, a_borrar, a_congelar, _ = cotizar_personalizaciones(self.reserva)
        congelar_personalizaciones(a_borrar, a_congelar)
        self.fila.refresh_from_db()
        self.assertEqual(self.fila.precio_unitario, Decimal('100.00'))
        self.assertEqual(self.fila.cantidad, 3)

    def test_sin_precio_en_la_moneda_devuelve_error(self):
        self.sp.precio_usd = None
        self.sp.save(update_fields=['precio_usd'])
        self.reserva.moneda = 'USD'
        _, _, _, error = cotizar_personalizaciones(self.reserva)
        self.assertIn('USD', error)
```

- [ ] **Paso 2: Verla fallar** — `$PY manage.py test apps.payments.tests_extras_modulo -v 2` → ERROR (módulo inexistente).

- [ ] **Paso 3: Implementar** — `backend/apps/payments/extras.py`. Es el cuerpo actual de `CrearPagoView._resolver_personalizaciones` (`apps/payments/views.py` L169-L269) movido a una función de módulo, con una sola diferencia de lógica: las personas de cada extra salen de `reserva.personas_de(sp.servicio_id)` (Tarea 3.4). Contenido completo:

```python
"""Cotización y congelado de extras (personalizaciones) de una Reserva.

Único lugar donde se calcula el cargo de extras: lo usan `CrearPagoView` (reserva
suelta o paquete de una empresa) y `CrearPagoOrdenView` (cada reserva de la orden)."""
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.fleet.models import Personalizacion, ServicioPersonalizacion
from apps.payments.pricing import cantidad_efectiva, cargo_personalizacion


def cotizar_personalizaciones(reserva):
    """Valida y cotiza el catálogo vigente de la reserva.

    Devuelve `(cargo_total, a_borrar, a_congelar, error)`. No escribe nada: los
    renglones inválidos se eliminan y los precios se congelan únicamente después de
    que Stripe acepte crear o actualizar el PaymentIntent (`congelar_personalizaciones`).
    """
    if reserva.paquete_id:
        activos_ids = list(
            reserva.paquete.servicios_asociados.filter(
                servicio__activo=True
            ).values_list('servicio_id', flat=True)
        )
        disponibles = {
            sp.pk: sp
            for sp in ServicioPersonalizacion.objects.filter(
                servicio_id__in=activos_ids,
                servicio__empresa=reserva.empresa,
                personalizacion__empresa=reserva.empresa,
                activo=True,
                personalizacion__activo=True,
            ).select_related('servicio', 'personalizacion')
        }
    else:
        disponibles = {
            sp.pk: sp
            for sp in ServicioPersonalizacion.objects.filter(
                servicio=reserva.servicio,
                activo=True,
                personalizacion__activo=True,
            ).select_related('servicio', 'personalizacion')
        }
    seleccionadas = list(
        reserva.personalizaciones_seleccionadas.select_related(
            'servicio_personalizacion__servicio',
            'servicio_personalizacion__personalizacion',
        )
    )
    seleccionadas_por_id = {
        fila.servicio_personalizacion_id: fila for fila in seleccionadas
    }

    faltantes = [
        sp.personalizacion.nombre
        for sp in disponibles.values()
        if (
            sp.personalizacion.tipo_interaccion != Personalizacion.TipoInteraccion.CHECK
            and sp.obligatorio
            and sp.pk not in seleccionadas_por_id
        )
    ]
    if faltantes:
        return 0, [], [], f'Falta responder "{faltantes[0]}" antes de pagar.'

    cargo_total = Decimal('0.00')
    a_borrar = []
    a_congelar = []
    for fila in seleccionadas:
        sp = disponibles.get(fila.servicio_personalizacion_id)
        if sp is None:
            a_borrar.append(fila)
            continue

        # Usa las relaciones ya verificadas del catálogo vigente para que
        # full_clean también detecte una configuración que dejó de ser válida.
        fila.servicio_personalizacion = sp
        try:
            sp.full_clean()
            fila.full_clean()
        except DjangoValidationError:
            return 0, [], [], (
                f'La configuración de "{sp.personalizacion.nombre}" cambió. '
                'Revisa tu selección antes de pagar.'
            )

        if sp.personalizacion.tipo_interaccion != Personalizacion.TipoInteraccion.CHECK:
            a_congelar.append((fila, None, 1))
            continue

        precio = sp.precio_en(reserva.moneda)
        if precio is None:
            return 0, [], [], (
                f'No hay precio de "{sp.personalizacion.nombre}" '
                f'configurado en {reserva.moneda}.'
            )
        # Las personas de un extra son las de SU servicio, no las del pedido entero.
        personas = reserva.personas_de(sp.servicio_id)
        cantidad = cantidad_efectiva(
            cobrar_por_persona=sp.personalizacion.cobrar_por_persona,
            cantidad_editable=sp.personalizacion.cantidad_editable,
            personas=personas,
            cantidad=fila.cantidad,
        )
        cargo_total += cargo_personalizacion(
            precio,
            cobrar_por_persona=sp.personalizacion.cobrar_por_persona,
            cantidad_editable=sp.personalizacion.cantidad_editable,
            personas=personas,
            cantidad=cantidad,
        )
        a_congelar.append((fila, precio, cantidad))

    return cargo_total, a_borrar, a_congelar, None


def congelar_personalizaciones(a_borrar, a_congelar):
    """Congela precio y cantidad ya cotizados. Llamar dentro de una transacción."""
    for extra in a_borrar:
        extra.delete()
    for extra, precio_unitario, cantidad in a_congelar:
        extra.precio_unitario = precio_unitario
        extra.cantidad = cantidad
        extra.save(update_fields=['precio_unitario', 'cantidad'])
```

- [ ] **Paso 4: La vista delega.** En `CrearPagoView.post`:
  - reemplaza `self._resolver_personalizaciones(reserva)` por `cotizar_personalizaciones(reserva)`;
  - reemplaza el bloque que borra/actualiza extras dentro del `transaction.atomic()` por `congelar_personalizaciones(extras_a_borrar, extras_a_congelar)`;
  - **borra** el método `_resolver_personalizaciones`;
  - añade `from .extras import congelar_personalizaciones, cotizar_personalizaciones` a los imports y elimina los imports que ya no se usen (`cantidad_efectiva`, `cargo_personalizacion` si quedaron huérfanos).

- [ ] **Paso 5: Verificar (refactor) y commit**

```bash
$PY manage.py test apps.payments.tests_extras_modulo apps.payments.tests_personalizaciones -v 1
$PY manage.py test apps.fleet apps.bookings apps.payments
git add backend/apps/payments
git commit -m "refactor(payments): cotizar y congelar extras en un solo modulo"
```

### Tarea 4.3: `CrearOrdenView` — calendario, personas y extras del paquete

**Files:**
- Modify: `backend/apps/payments/views.py` (`CrearOrdenView.post`, ≈ L560-L755)
- Test: `backend/apps/payments/tests_orden_paquete.py`

**Interfaces:**
- Consumes: `calendario_paquete.*` (2.4), `personalizaciones.validar_seleccion/sincronizar` (4.1), `PaqueteServicio.dia_estancia/noches/personas_incluidas`.
- Produces (contrato): `fecha` = inicio del paquete; cada reserva de la orden queda con su fecha calculada, `fecha_salida` en el hospedaje, `numero_personas` validado contra `personas_incluidas` y sus extras guardados. Rechaza (400) `fecha` por componente, `fecha_regreso` cuando hay hospedaje, personas por encima de lo incluido y extras que no son del servicio.

- [ ] **Paso 1: Pruebas que fallan** — `backend/apps/payments/tests_orden_paquete.py` (fixture calcado de `CrearOrdenTest`, `apps/payments/tests.py` ≈ L2519):

```python
import uuid
from decimal import Decimal

from django.test import TestCase

from apps.bookings.models import DetalleTransporte, Reserva
from apps.fleet.enums import TipoTraslado
from apps.fleet.models import (
    Paquete, PaqueteServicio, Personalizacion, Servicio, ServicioPersonalizacion, TransporteTarifa,
)
from apps.tenancy import scope
from apps.tenancy.models import Empresa, Sede


class OrdenPaqueteBase(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede OP', slug='sede-op-test', activo=True)
        self.pesca = Empresa.objects.create(sede=self.sede, nombre='Pesca OP', slug='pesca-op', activo=True)
        self.transp = Empresa.objects.create(sede=self.sede, nombre='Transp OP', slug='transp-op', activo=True)
        with scope.como_operador_plataforma():
            self.s_pesca = Servicio.objects.create(
                empresa=self.pesca, nombre='Pesca', slug='pesca-op-s', tipo_servicio='pesca',
                estrategia_cupo='por_recurso_dia', precio_base=Decimal('4000.00'),
            )
            self.s_transp = Servicio.objects.create(
                empresa=self.transp, nombre='Traslado', slug='traslado-op-s', tipo_servicio='transporte',
                estrategia_cupo='bajo_demanda', estrategia_precio='por_ruta',
            )
            TransporteTarifa.objects.create(
                empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_ACTIVIDAD, zona='centro',
                personas_min=1, personas_max=None, precio=Decimal('1500.00'), precio_usd=Decimal('90.00'),
            )
            self.paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Pesca + Traslado', slug='pesca-traslado-op',
                precio_ancla=Decimal('7500.00'), precio_ancla_usd=Decimal('450.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.s_pesca, orden=1, dia_estancia=1, personas_incluidas=3,
            )
            PaqueteServicio.objects.create(
                paquete=self.paquete, servicio=self.s_transp, orden=2, dia_estancia=1, personas_incluidas=3,
            )
            brunch = Personalizacion.objects.create(empresa=self.pesca, nombre='Brunch', tipo_interaccion='check')
            silla = Personalizacion.objects.create(empresa=self.transp, nombre='Silla de bebé', tipo_interaccion='check')
            self.sp_brunch = ServicioPersonalizacion.objects.create(
                servicio=self.s_pesca, personalizacion=brunch, precio=Decimal('400.00'), precio_usd=Decimal('23.00'),
            )
            self.sp_silla = ServicioPersonalizacion.objects.create(
                servicio=self.s_transp, personalizacion=silla, precio=Decimal('150.00'), precio_usd=Decimal('9.00'),
            )
        self.url = f'/api/{self.sede.slug}/ordenes/'

    def payload(self, **extra):
        datos = {
            'checkout_id': str(uuid.uuid4()), 'paquete': self.paquete.slug,
            'nombre_cliente': 'Carlos Lopez', 'telefono_cliente': '1234567890',
            'correo_cliente': 'carlos@example.com', 'moneda': 'MXN', 'deslinde_aceptado': True,
            'deslinde_nombre': 'Carlos Lopez', 'fecha': '2026-10-15', 'hora': '07:00:00',
            'componentes': [
                {'servicio': self.s_pesca.slug, 'numero_personas': 2,
                 'personalizaciones': [{'id': self.sp_brunch.pk}]},
                {'servicio': self.s_transp.slug, 'numero_personas': 3,
                 'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD, 'zona': 'centro',
                 'direccion_personalizada': 'Hotel Marina', 'personalizaciones': [{'id': self.sp_silla.pk}]},
            ],
        }
        datos.update(extra)
        return datos

    def crear(self, **extra):
        return self.client.post(self.url, self.payload(**extra), content_type='application/json')


class CrearOrdenPaqueteTests(OrdenPaqueteBase):
    def test_guarda_personas_por_componente_y_extras_de_cada_servicio(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        with scope.como_operador_plataforma():
            r_pesca = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], empresa=self.pesca)
            r_transp = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], empresa=self.transp)
            self.assertEqual(r_pesca.numero_personas, 2)
            self.assertEqual(r_transp.numero_personas, 3)
            self.assertEqual(list(r_pesca.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True)), [self.sp_brunch.pk])
            self.assertEqual(list(r_transp.personalizaciones_seleccionadas.values_list('servicio_personalizacion_id', flat=True)), [self.sp_silla.pk])

    def test_rechaza_personas_por_encima_de_lo_incluido(self):
        datos = self.payload()
        datos['componentes'][0]['numero_personas'] = 4
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('lugar', str(respuesta.json()))

    def test_rechaza_un_extra_que_no_es_del_servicio(self):
        datos = self.payload()
        datos['componentes'][0]['personalizaciones'] = [{'id': self.sp_silla.pk}]
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('personalizaciones', respuesta.json())

    def test_rechaza_fecha_por_componente(self):
        datos = self.payload()
        datos['componentes'][0]['fecha'] = '2026-10-20'
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('fecha', respuesta.json())

    def test_el_dia_de_cada_componente_lo_define_el_paquete(self):
        with scope.como_operador_plataforma():
            hotel = Servicio.objects.create(
                empresa=self.pesca, nombre='Cabaña', slug='cabana-op-s', tipo_servicio='hospedaje',
                estrategia_cupo='por_noche', estrategia_precio='por_noche',
            )
            # Paquete de 3 noches (hospedaje de la empresa líder) con el traslado el día 2.
            # Un paquete de dos empresas admite un servicio por empresa, por eso este paquete
            # no lleva la pesca.
            paquete = Paquete.objects.create(
                sede=self.sede, empresa_lider=self.pesca, nombre='Cabaña + Traslado', slug='cabana-traslado-op',
                precio_ancla=Decimal('9000.00'), permite_anticipo=False,
            )
            PaqueteServicio.objects.create(paquete=paquete, servicio=hotel, orden=1, noches=3, personas_incluidas=3)
            PaqueteServicio.objects.create(paquete=paquete, servicio=self.s_transp, orden=2, dia_estancia=2, personas_incluidas=3)
        datos = self.payload(paquete=paquete.slug)
        datos['componentes'] = [
            {'servicio': hotel.slug, 'numero_personas': 2},
            {'servicio': self.s_transp.slug, 'numero_personas': 3, 'tipo_traslado': TipoTraslado.REDONDO_ACTIVIDAD,
             'zona': 'centro', 'direccion_personalizada': 'Hotel Marina'},
        ]
        respuesta = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        with scope.como_operador_plataforma():
            r_hotel = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], servicio=hotel)
            r_transp = Reserva.objects.get(orden_id=respuesta.json()['orden_id'], servicio=self.s_transp)
            self.assertEqual(str(r_hotel.fecha), '2026-10-15')
            self.assertEqual(str(r_hotel.fecha_salida), '2026-10-18')
            self.assertEqual(str(r_transp.fecha), '2026-10-16')
```
- [ ] **Paso 2: Verlas fallar** — `$PY manage.py test apps.payments.tests_orden_paquete -v 2` → FAIL (extras no se guardan, personas no se validan, fechas no se derivan).

- [ ] **Paso 3: Implementar en `CrearOrdenView.post`.**

**Lectura bajo RLS (obligatoria).** La vista es pública (`AllowAny`) y no tiene alcance de empresa activo: `PaqueteServicio` solo se ve bajo el alcance de la **líder** (`0020_rls_paquetes.py`) y `fleet_servicio` está aislada por empresa, así que **no** se puede leer la configuración con `paquete.servicios_asociados...` ni con una unión a `Servicio`. La vista ya resuelve `servicios = _buscar_servicios_de_paquete(sede, paquete)` (cada `Servicio` bajo el alcance de su empresa). Añade la lectura de la configuración **sin unir**, con el alcance de la líder, y valida el paquete antes de crear nada. Justo después de calcular `servicios` y `empresas_ids`, y antes del bloque `try: with transaction.atomic():`:

```python
        from datetime import date as _date
        from apps.bookings import personalizaciones as extras_reserva
        from apps.fleet.calendario_paquete import (
            ComponenteCalendario, fecha_de_componente, fecha_salida as calcular_salida, noches_del_paquete,
        )
        from apps.fleet.models import componente_desde
        from apps.fleet.paquete_reglas import errores_de_paquete

        with scope.con_empresa(paquete.empresa_lider):
            filas_ps = {
                fila['servicio_id']: fila
                for fila in paquete.servicios_asociados.values(
                    'servicio_id', 'dia_estancia', 'noches', 'personas_incluidas',
                )
            }
        servicios = [s for s in servicios if s.id in filas_ps]
        calendario = [
            ComponenteCalendario(
                dia_estancia=filas_ps[s.id]['dia_estancia'], estrategia_cupo=s.estrategia_cupo,
                noches=filas_ps[s.id]['noches'],
            )
            for s in servicios
        ]
        errores = errores_de_paquete(
            permite_anticipo=paquete.permite_anticipo,
            componentes=[
                componente_desde(
                    s, noches=filas_ps[s.id]['noches'], dia_estancia=filas_ps[s.id]['dia_estancia'],
                    personas_incluidas=filas_ps[s.id]['personas_incluidas'],
                )
                for s in servicios
            ],
        )
        if errores:
            return Response({'paquete': errores}, status=400)
        try:
            inicio = _date.fromisoformat(str(request.data.get('fecha')))
        except ValueError:
            return Response({'fecha': 'Elige la fecha de inicio del paquete.'}, status=400)
        hay_hospedaje = noches_del_paquete(calendario) is not None
```
Dentro del bucle `for servicio in servicios:`, **sustituye** las líneas que leen `fecha`, `hora` y `personas` por (los datos de configuración son diccionarios: `ps['...']`):

```python
                    ps = filas_ps[servicio.id]
                    comp_d = _buscar_datos_comp(servicio)
                    if comp_d.get('fecha') or (hay_hospedaje and comp_d.get('fecha_regreso')):
                        raise DjangoValidationError({'fecha': 'Las fechas de cada servicio las define el paquete.'})

                    fecha = fecha_de_componente(inicio, ps['dia_estancia'])
                    personas = comp_d.get('numero_personas') or ps['personas_incluidas']
                    if personas > ps['personas_incluidas']:
                        raise DjangoValidationError({
                            'numero_personas': f'"{servicio.nombre}" incluye {ps["personas_incluidas"]} lugar(es) en este paquete.',
                        })
                    hora = comp_d.get('hora') or request.data.get('hora', '07:00:00')
```
y al asignar la reserva:

```python
                        reserva.fecha = fecha
                        reserva.fecha_salida = calcular_salida(inicio, calendario) if servicio.estrategia_cupo == 'por_noche' else None
                        reserva.hora = hora
                        reserva.numero_personas = personas
```
Para el traslado, cuando el paquete tiene hospedaje, la vuelta la define el paquete:

```python
                            fecha_regreso = (
                                calcular_salida(inicio, calendario)
                                if (hay_hospedaje and tipo_traslado == 'redondo_aeropuerto')
                                else comp_d.get('fecha_regreso') or request.data.get('fecha_regreso')
                            )
```
Tras `reserva.save()` (y del bloque de transporte) guarda los extras **dentro** del `with scope.con_empresa(empresa):`:

```python
                        items = comp_d.get('personalizaciones') or []
                        extras_reserva.validar_seleccion(servicio, items)
                        extras_reserva.sincronizar(reserva, items)
```
**Importante:** dentro del `with transaction.atomic():` los rechazos se hacen con `raise DjangoValidationError(...)`, nunca con `return Response(...)`: un `return` dentro del bloque hace commit de la orden y las reservas ya creadas (orden a medias). `DjangoValidationError` ya se captura al final de la vista (fuera del `atomic`) y responde 400 con `message_dict`. Los `return Response(...)` de arriba (antes de `atomic`) son correctos porque todavía no se escribió nada.

- [ ] **Paso 4: Verlas pasar y regresiones.** Las pruebas viejas de `CrearOrdenTest` (`apps/payments/tests.py`) mandan `fecha` por componente/`numero_personas` global: ajústalas al contrato nuevo (una `fecha` de inicio, `componentes[].numero_personas`). Inventario: `apps/bookings/tests.py` ≈ L2429 (payload global de orden) y cualquier otra que mande `fecha` por componente (`grep -rn "ordenes/" apps --include=tests*.py`).

```bash
$PY manage.py test apps.payments apps.bookings
```

- [ ] **Paso 5: Commit**

```bash
git add backend/apps/payments
git commit -m "feat(payments): la orden toma fechas, lugares y extras de cada servicio del paquete"
```

### Tarea 4.4: `CrearPagoOrdenView` — extras por empresa, USD y tarifas faltantes

**Files:**
- Modify: `backend/apps/payments/views.py` (`CrearPagoOrdenView.post`, ≈ L761-L846)
- Test: `backend/apps/payments/tests_orden_paquete.py` (se amplía)

**Interfaces:**
- Consumes: `cotizar_personalizaciones`, `congelar_personalizaciones` (4.2), `monto_por_empresa` (existente).
- Produces: `POST …/ordenes/<id>/crear-pago/` devuelve los pagos con `monto` = parte de la empresa **más sus extras**; 400 si falta precio del paquete o tarifa de transporte en la moneda de la orden; congela extras solo si Stripe aceptó.

- [ ] **Paso 1: Pruebas que fallan.** Añade a `tests_orden_paquete.py` (imports: `from unittest import mock`, `from apps.payments.tests import intent_falso` no aplica: usa `mock.Mock`):

```python
class CrearPagoOrdenTests(OrdenPaqueteBase):
    def _crear_orden(self, **extra):
        respuesta = self.crear(**extra)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        return respuesta.json()['orden_id']

    def _pago(self, orden_id):
        return self.client.post(
            f'/api/{self.sede.slug}/ordenes/{orden_id}/crear-pago/', {}, content_type='application/json',
        )

    def _stripe_falso(self):
        clientes = {}

        def para(empresa):
            if empresa.id not in clientes:
                cliente = mock.Mock()
                cliente.payment_intents.create.side_effect = lambda params, options: mock.Mock(
                    id=f'pi_{empresa.id}', client_secret=f'pi_{empresa.id}_sec',
                    amount=params['amount'], currency=params['currency'], status='requires_payment_method',
                )
                clientes[empresa.id] = cliente
            return clientes[empresa.id]
        return para, clientes

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_vector_del_spec_reparto_con_extras(self, configurar):
        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        orden_id = self._crear_orden()
        respuesta = self._pago(orden_id)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        montos = {p['empresa_slug']: p['monto'] for p in respuesta.json()}
        # 7500 − 1500 (tarifa del traslado) + 400 (brunch) = 6400 ; 1500 + 150 (silla) = 1650
        self.assertEqual(montos, {'pesca-op': '6400.00', 'transp-op': '1650.00'})
        self.assertEqual(sum(Decimal(m) for m in montos.values()), Decimal('8050.00'))

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_congela_los_extras_solo_despues_de_que_stripe_acepta(self, configurar):
        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        orden_id = self._crear_orden()
        self._pago(orden_id)
        with scope.como_operador_plataforma():
            fila = Reserva.objects.get(orden_id=orden_id, empresa=self.pesca).personalizaciones_seleccionadas.get()
            self.assertEqual(fila.precio_unitario, Decimal('400.00'))

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_usd_reparte_con_los_precios_usd(self, configurar):
        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        orden_id = self._crear_orden(moneda='USD')
        respuesta = self._pago(orden_id)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        montos = {p['empresa_slug']: p['monto'] for p in respuesta.json()}
        # 450 − 90 + 23 = 383 ; 90 + 9 = 99
        self.assertEqual(montos, {'pesca-op': '383.00', 'transp-op': '99.00'})
        params = clientes[self.pesca.id].payment_intents.create.call_args.args[0]
        self.assertEqual(params['currency'], 'usd')

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_400_si_falta_la_tarifa_de_transporte_en_la_moneda(self, configurar):
        with scope.como_operador_plataforma():
            TransporteTarifa.objects.filter(empresa=self.transp).update(precio_usd=None)
        orden_id = self._crear_orden(moneda='USD')
        respuesta = self._pago(orden_id)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('USD', respuesta.json()['detail'])
        configurar.assert_not_called()

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_400_si_el_paquete_no_tiene_precio_en_la_moneda(self, configurar):
        with scope.como_operador_plataforma():
            Paquete.objects.filter(pk=self.paquete.pk).update(precio_ancla_usd=None)
        orden_id = self._crear_orden(moneda='USD')
        respuesta = self._pago(orden_id)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('USD', respuesta.json()['detail'])
```
(Añade `from unittest import mock` al inicio del archivo.)

- [ ] **Paso 2: Verlas fallar** — `$PY manage.py test apps.payments.tests_orden_paquete.CrearPagoOrdenTests -v 2` → FAIL (montos sin extras; USD sin guardas).

- [ ] **Paso 2b: Prueba adicional de zona** (bug detectado en la revisión externa: el reparto usaba `detalle.zona`, pero un traslado de aeropuerto con hotel del catálogo conserva la zona del hotel y sus tarifas usan zona vacía; la regla existente es `DetalleTransporte.zona_efectiva()`). Añade al final de `CrearPagoOrdenTests`:

```python
    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_aeropuerto_con_hotel_del_catalogo_usa_la_tarifa_sin_zona(self, configurar):
        from apps.fleet.models import PuntoEncuentro

        para, clientes = self._stripe_falso()
        configurar.side_effect = para
        with scope.como_operador_plataforma():
            punto = PuntoEncuentro.objects.create(empresa=self.transp, nombre='Hotel Marina', zona='centro')
            TransporteTarifa.objects.create(
                empresa=self.transp, tipo_traslado=TipoTraslado.REDONDO_AEROPUERTO, zona='',
                personas_min=1, personas_max=None, precio=Decimal('4500.00'), precio_usd=Decimal('250.00'),
            )
        datos = self.payload()
        datos['componentes'][1] = {
            'servicio': self.s_transp.slug, 'numero_personas': 3, 'tipo_traslado': TipoTraslado.REDONDO_AEROPUERTO,
            'punto_encuentro': punto.pk, 'fecha_regreso': '2026-10-18', 'personalizaciones': [{'id': self.sp_silla.pk}],
        }
        creada = self.client.post(self.url, datos, content_type='application/json')
        self.assertEqual(creada.status_code, 201, creada.content)
        respuesta = self._pago(creada.json()['orden_id'])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        montos = {p['empresa_slug']: p['monto'] for p in respuesta.json()}
        # traslado: tarifa de aeropuerto 4500 + silla 150 ; líder: 7500 - 4500 + brunch 400
        self.assertEqual(montos, {'pesca-op': '3400.00', 'transp-op': '4650.00'})

    @mock.patch('apps.payments.ordenes.configurar_stripe')
    def test_503_si_un_extra_no_tiene_precio_en_la_moneda(self, configurar):
        with scope.como_operador_plataforma():
            ServicioPersonalizacion.objects.filter(pk=self.sp_brunch.pk).update(precio_usd=None)
        orden_id = self._crear_orden(moneda='USD')
        respuesta = self._pago(orden_id)
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn('USD', respuesta.json()['detail'])
        configurar.assert_not_called()
```

- [ ] **Paso 3: Implementar el método completo.** El reemplazo por fragmentos del plan anterior no compilaba (quedaban los `except` sin `try`). **Reemplaza `CrearPagoOrdenView.post` entero** (`apps/payments/views.py`, desde `def post(self, request, sede_slug, pk):` de esa clase hasta el `return Response(pagos, status=200)`) por:

```python
    def post(self, request, sede_slug, pk):
        from decimal import Decimal

        from apps.bookings.models import DetalleTransporte, Orden, Reserva
        from apps.bookings.orden_lectura import reservas_de_orden
        from apps.fleet.models import TransporteTarifa
        from apps.fleet.tarifa_transporte import TarifaTransporteNoConfigurada, resolver_tarifa_transporte
        from apps.tenancy.models import Empresa, Sede
        from .extras import congelar_personalizaciones, cotizar_personalizaciones
        from .ordenes import OrdenCerradaError, crear_pagos_orden
        from .pricing import monto_por_empresa

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        orden = _buscar_orden(sede, pk=pk)
        if not orden:
            raise Http404('No se encontró la orden solicitada.')

        if orden.estado in (Orden.Estado.CAPTURADA, Orden.Estado.CANCELADA):
            return Response({'detail': f'La orden ya está {orden.estado}.'}, status=409)

        with scope.con_empresa(orden.empresa_lider):
            precio_paquete = orden.paquete.precio_en(orden.moneda)
        if precio_paquete is None:
            return Response({'detail': f'El paquete no tiene precio en {orden.moneda}.'}, status=400)

        componentes = []
        extras_por_empresa = {}
        por_congelar = []
        for fila in reservas_de_orden(orden.id):
            empresa = Empresa.objects.get(pk=fila['empresa_id'])
            es_lider = (empresa.id == orden.empresa_lider_id)
            with scope.con_empresa(empresa):
                reserva = Reserva.objects.select_related('servicio', 'paquete', 'empresa').get(pk=fila['reserva_id'])
                monto_fijo = None
                if not es_lider and reserva.servicio and reserva.servicio.tipo_servicio == 'transporte':
                    detalle = DetalleTransporte.objects.filter(reserva=reserva).first()
                    if detalle is None:
                        return Response({'detail': 'El traslado no tiene detalle configurado.'}, status=400)
                    tarifas = TransporteTarifa.objects.filter(empresa=empresa, activo=True)
                    try:
                        tarifa = resolver_tarifa_transporte(
                            tarifas, tipo_traslado=detalle.tipo_traslado,
                            zona=detalle.zona_efectiva(), personas=reserva.numero_personas,
                        )
                    except TarifaTransporteNoConfigurada as exc:
                        return Response({'detail': str(exc)}, status=400)
                    monto_fijo = tarifa.precio_en(orden.moneda)
                    if monto_fijo is None:
                        return Response(
                            {'detail': f'Falta la tarifa de transporte en {orden.moneda}.'}, status=400,
                        )
                cargo, a_borrar, a_congelar, error = cotizar_personalizaciones(reserva)
            if error:
                return Response({'detail': error}, status=503)
            componentes.append({'empresa_id': empresa.id, 'es_lider': es_lider, 'monto_fijo': monto_fijo})
            extras_por_empresa[empresa.id] = extras_por_empresa.get(empresa.id, Decimal('0.00')) + Decimal(cargo)
            por_congelar.append((empresa, a_borrar, a_congelar))

        try:
            reparto = monto_por_empresa(
                precio_paquete=precio_paquete, componentes=componentes, moneda=orden.moneda,
            )
            # La líder sigue absorbiendo solo el residuo del precio del paquete; los extras de
            # cada empresa se le suman a ella.
            for empresa_id, cargo in extras_por_empresa.items():
                reparto[empresa_id] = reparto.get(empresa_id, Decimal('0.00')) + cargo
            pagos = crear_pagos_orden(orden, reparto)
            # Los extras se congelan solo si Stripe aceptó crear/actualizar los intents.
            for empresa, a_borrar, a_congelar in por_congelar:
                with scope.con_empresa(empresa), transaction.atomic():
                    congelar_personalizaciones(a_borrar, a_congelar)
        except OrdenCerradaError as exc:
            return Response({'detail': str(exc)}, status=409)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except stripe.StripeError as exc:
            logger.exception('Fallo al crear pagos para la orden %s: %s', orden.id, exc)
            return Response({'detail': 'No se pudo iniciar el cobro con Stripe. Intenta de nuevo.'}, status=502)

        if orden.estado == Orden.Estado.ARMANDO:
            with scope.con_empresa(orden.empresa_lider):
                orden.transicionar(Orden.Estado.AUTORIZANDO)
                orden.save(update_fields=['estado'])

        return Response(pagos, status=200)
```
Notas: (a) `zona_efectiva()` es la misma regla que ya usa el cobro de un traslado suelto (`DetalleTransporte.zona_efectiva`, `apps/bookings/models.py` ≈ L1161); (b) un extra sin precio en la moneda responde 503 como el cobro de una reserva suelta (mensaje "No hay precio de … configurado en USD"): es el comportamiento existente y el spec §6 se corrigió para reflejarlo; (c) los `return Response(...)` dentro de `with scope.con_empresa(...)` son seguros: aún no se escribió nada.

- [ ] **Paso 4: Verlas pasar y regresiones**

```bash
$PY manage.py test apps.payments apps.bookings apps.fleet
```

- [ ] **Paso 5: Commit**

```bash
git add backend/apps/payments
git commit -m "feat(payments): la orden cobra extras por empresa, soporta USD y valida tarifas faltantes"
```

**STOP DURO — Cierre de la Sección 4.** Reportar al dueño: órdenes de dos empresas con extras por servicio, personas por componente, USD y guardas; vector 6,400 / 1,650 = 8,050 verificado por prueba.

---

## Sección 5 — Cierre del backend

### Tarea 5.1: Datos demo con los campos nuevos

**Files:**
- Modify: `backend/apps/fleet/management/commands/seed_local_demo.py` (≈ L141-L160 y L246-L262)

- [ ] **Paso 1: Editar el seed.**
  - `fin-de-semana-la-paz` (una empresa): mantén `porcentaje_anticipo=50` (con `permite_anticipo` por defecto `True`). Cambia los `PaqueteServicio`: pesca `defaults={'orden': 1, 'dia_estancia': 2, 'personas_incluidas': 2}` y hospedaje `defaults={'orden': 2, 'noches': 2, 'personas_incluidas': 2}`.
  - `pesca-traslado` (dos empresas): cambia `porcentaje_anticipo=100` por `permite_anticipo=False`; los componentes conservan `personas_incluidas` por defecto (2).
  - Tras el bucle de componentes de cada paquete demo llama `paquete.validar_configuracion()` (sustituye el `paquete_cruza.full_clean()` por `paquete_cruza.full_clean(); paquete_cruza.validar_configuracion()`).
- [ ] **Paso 1b: Otros `porcentaje_anticipo=100` del seed.** `grep -n "porcentaje_anticipo" backend/apps/fleet/management/commands/seed_local_demo.py`: los Servicios de hospedaje (≈ L175) y de transporte (≈ L205) también codificaban "sin anticipo"; cámbialos a `permite_anticipo=False`.

- [ ] **Paso 2: Probar el seed en una BD limpia.**

```bash
$PY manage.py migrate
$PY manage.py seed_local_demo
```
Esperado: termina sin errores. En una BD ya sembrada `get_or_create` no actualiza filas existentes: edita esos paquetes desde el admin (o bórralos y vuelve a correr el seed).
- [ ] **Paso 3: Commit**

```bash
git add backend/apps/fleet/management
git commit -m "chore(fleet): seed demo con estancia, personas incluidas y anticipo explicito"
```

### Tarea 5.2: Documentación del backend

**Files:**
- Modify: `backend/CLAUDE.md`

- [ ] **Paso 1: Añadir una sección "Checkout unificado de paquetes"** con: (a) reglas de anticipo (servicio, paquete de una empresa, paquete de dos empresas nunca; el servidor rechaza `anticipo` si no aplica); (b) configuración del paquete (`dia_estancia`, `noches`, `personas_incluidas`, reglas de `paquete_reglas.py`); (c) semántica de `Reserva.fecha` en un paquete de una empresa (día de la actividad; inicio derivado con `fecha_inicio_paquete`); (d) `personas_por_servicio` y `personas_de`; (e) extras cotizados solo en `payments/extras.py`; (f) contrato de `POST /api/<sede>/ordenes/` (fecha de inicio, `componentes[].numero_personas/personalizaciones`, fechas rechazadas); (g) una orden asume un servicio por empresa; (h) USD en órdenes y sus guardas. Enlaza el spec.
- [ ] **Paso 2: Corregir lo desactualizado.** El gotcha "Paquetes turísticos: en v1 … un paquete agrupa servicios de una sola empresa" ya no es cierto (ver "Órdenes cruza-empresa"): actualízalo o bórralo. Reemplaza "`porcentaje_anticipo` … 100=completo" por la regla del interruptor.
- [ ] **Paso 3: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): documentar checkout unificado de paquetes"
```

### Tarea 5.3: Gate final — suite completa SQLite y PostgreSQL

**Files:** ninguno.

- [x] **Paso 1: SQLite, suite completa**

```bash
$PY manage.py test apps config
$PY manage.py check --deploy
$PY manage.py makemigrations --check --dry-run
```
Esperado: `OK`; `check --deploy` sin issues nuevos; `makemigrations --check` sin cambios pendientes.

- [x] **Paso 2: PostgreSQL con RLS** (contenedor y rol según `backend/CLAUDE.md`, "Correr la suite contra Postgres en local"):

```bash
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
$PY manage.py test apps config
```
Esperado: `OK`. Si falla algo de RLS en `ReservaPersonalizacion` de una orden, la escritura quedó fuera de `scope.con_empresa(empresa)`: corrígelo (no relajes políticas).

- [x] **Paso 3: Repaso de diffs** (checklist): (a) ninguna cifra de dinero fuera de `payments/`; (b) ningún `como_operador_plataforma()` en una vista `AllowAny`; (c) las migraciones de datos usan `alcance_operador_migracion`; (d) no hay tablas nuevas; (e) `git diff feat/transporte-multi-empresa --stat` solo toca los archivos del mapa.
- [x] **Paso 4: Anotar** en este plan el HEAD final y el nº de tests (SQLite y Postgres).

**Resultado del gate (2026-09-25).** HEAD validado antes del commit de esta anotación:
`9906497`. SQLite (`apps config`, `settings.local`): **1005 tests, OK**.
PostgreSQL (`apps config`, `settings.ci`, `ci_rls` sin `BYPASSRLS`): **1005 tests, OK**
con la base de pruebas recreada. El primer intento con `--keepdb` falló con ausencia
de los datos iniciales de `la-paz`/`sal-y-sol`; la repetición sin
`--keepdb` pasó. `check --deploy --settings=config.settings.local` terminó con código 0
y seis advertencias de seguridad propias de la configuración local (W004, W008, W009,
W012, W016 y W018), sin cambios en `settings.local` frente a la rama base.
`makemigrations --check --dry-run`: `No changes detected`.

Repaso del Paso 3: (a) **no literal**: `fleet/models.py` compara el precio del paquete
con la tarifa de transporte y el seed contiene precios demo, ambos previstos en el
plan; el cobro y el reparto viven en `payments/`. (b) **sí**: ninguna vista invoca
`como_operador_plataforma()`. (c) **sí**: todos los `RunPython` nuevos que escriben
datos usan `alcance_operador_migracion`. (d) **sí**: las migraciones nuevas solo añaden
o alteran campos. (e) **no literal**: el diff del worktree incluye cambios locales
preexistentes de `.great_cto`; el diff de commits incluye `seed_extras.py` (arreglo de
compatibilidad de la Tarea 1.2) fuera del mapa resumido, además del spec y el plan
hermano copiados en la Tarea 0.1.

**STOP DURO — Cierre del backend.** Reportar al dueño con el resumen y las pendientes de la §9 del spec. El plan de frontend puede empezar/terminar; no hay merge ni push sin luz verde.

---

## Sección 6 — Continuar reservación

Implementa spec §10/§10.1 (APROBADA). Sin tablas ni campos nuevos: `situacion` y "requiere atención"
se calculan de lo que ya existe (`Reserva.estado/monto_pagado/monto_reembolsado`, `Orden.estado`,
estado de los PaymentIntents vía `GetOrdenView`).

### Tarea 6.1: `situacion` como función pura

**Files:**
- Create: `backend/apps/payments/situacion.py`
- Test: `backend/apps/payments/tests_situacion.py`

**Interfaces:**
- Produces:
  - `Situacion` = uno de: `SIN_PAGO, PAGO_EN_PROCESO, RETENIDO_PARCIAL, RETENIDO_TOTAL,
    CONFIRMANDO_COBRO, CONFIRMADA, CANCELADA_LIBERADA, CANCELADA_DEVOLUCION_SOLICITADA,
    CANCELADA_DEVOLUCION_POR_CONFIRMAR, EXPIRADA, NO_EXISTE` (choices en `TextChoices`).
  - `situacion_de_reserva(*, estado: str, monto_pagado, monto_reembolsado,
    tiene_intent_activo: bool = False) -> Situacion`. Motor de una empresa: captura automática, sin
    paso de "retenido" — por eso, a diferencia de `situacion_de_orden`, esta función **no** consulta
    Stripe (mismo patrón que `EstadoReservaView`, que ya documenta "no llama a Stripe"; no romper esa
    convención). `tiene_intent_activo` es simplemente `bool(reserva.stripe_payment_intent_id)`: no
    dice el estado real del PI, solo si ya se intentó cobrar — suficiente para no decir "aún no has
    pagado, puedes descartar" mientras un cobro puede estar en curso (evita la corrección con el
    guarda `PagoEnCurso` de `crear-pago`, que sí consulta Stripe en ese otro endpoint). Reglas:
    `pendiente_pago` sin intent → `SIN_PAGO`; `pendiente_pago` con intent → `PAGO_EN_PROCESO`;
    `pagada`/`asignada`/`completada` → `CONFIRMADA`; `cancelada` con `monto_pagado` > 0 y
    `monto_reembolsado` < `monto_pagado` (incluido `None`/0) → `CANCELADA_DEVOLUCION_POR_CONFIRMAR`
    (un reembolso parcial **no** cuenta como solicitud completa); `cancelada` con `monto_reembolsado`
    ≥ `monto_pagado` y `monto_pagado` > 0 → `CANCELADA_DEVOLUCION_SOLICITADA`; `cancelada` sin
    `monto_pagado` → `CANCELADA_LIBERADA` (nunca se cobró: el cupo se perdió antes de pagar, o mal
    clima antes de cobrar — caso raro pero válido). Este motor no tiene paso de "retenido" ni endpoint
    de cancelación propio en este plan (solo `Orden` se cancela desde "Continuar reservación"), así
    que `monto_pagado is None` en una reserva cancelada siempre significa que no hubo nada que
    liberar — no hace falta evidencia de Stripe para ese caso.
  - `situacion_de_orden(*, estado_orden: str, pagos: list[dict]) -> Situacion`. `pagos`: una entrada
    por reserva de la orden, cada una `{'estado_pi': str | None, 'monto_pagado': Decimal | None,
    'monto_reembolsado': Decimal | None}` (mismas claves que devuelve `reservas_de_orden` +
    `estado_pi` de Stripe — quien llama **siempre** debe traer `estado_pi` fresco, incluida una orden
    ya `cancelada`: es la única evidencia de si un `void` realmente liberó la retención o falló
    dejando el dinero retenido). Reglas: `armando` → `SIN_PAGO`; `autorizando` cuenta como "dinero
    comprometido" cualquier entrada en `requires_capture` **o** `succeeded` (ambas mueven o retienen
    dinero real, a diferencia de `requires_payment_method`/`requires_confirmation`/sin intent) — si
    **ninguna** entrada tiene `estado_pi` todavía → `PAGO_EN_PROCESO`; si **todas** las que sí lo
    tienen están comprometidas → `CONFIRMANDO_COBRO`; si solo **algunas** → `RETENIDO_PARCIAL`;
    `autorizada` → `CONFIRMANDO_COBRO`; `capturada` → `CONFIRMADA`; `cancelada`: si **alguna** entrada
    sigue con `estado_pi` en `requires_capture`/en proceso (el `void` no se confirmó: `revertir_orden`
    atrapó un `StripeError` y siguió sin reintentar) **o** hay `monto_pagado` sin `monto_reembolsado`
    igual o mayor → `CANCELADA_DEVOLUCION_POR_CONFIRMAR` (nunca "liberada" mientras la retención no
    esté confirmada); si el reembolso cubre el total pagado y no queda ninguna retención pendiente →
    `CANCELADA_DEVOLUCION_SOLICITADA`; si no hubo ningún `monto_pagado` y ninguna retención pendiente
    → `CANCELADA_LIBERADA`.
  - `requiere_atencion(situacion: Situacion) -> bool` — `True` solo para
    `CANCELADA_DEVOLUCION_POR_CONFIRMAR`. Con la regla de arriba, esto ahora también cubre un `void`
    que falló y dejó dinero retenido sin resolver — correcto: alguien del equipo debe revisarlo en
    Stripe, aunque el texto que hoy ve el cliente para ese estado (§10.1) hable de "devolución" y no
    de "liberación pendiente". **Decisión pendiente del dueño** (no se resuelve en este plan): si el
    texto de esa fila de la matriz debe distinguir "devolución en curso" de "no pudimos liberar tu
    retención, lo estamos resolviendo" — hoy ambos casos comparten la misma frase aprobada en S:358.
    **Nota de diseño frente a S:383-384:** la spec pide "registrar el resultado de cada
    `payment_intents.cancel`/`refunds.create` en `revertir_orden`", lo que sugiere persistir un campo
    nuevo. Este plan logra el mismo resultado (nunca declarar "liberada" sin confirmación) sin tocar
    `revertir_orden` ni sumar columnas: `ResumenOrdenView`/`CancelarOrdenPublicaView` (Tarea 6.2)
    siempre traen `estado_pi` **fresco** desde Stripe (vía `_reservas_info_de_orden`, incluso para una
    orden ya `cancelada`), así que la evidencia de si el void se confirmó se lee en el momento en vez
    de guardarse. Es funcionalmente equivalente y no agrega estado que pueda desincronizarse, pero es
    una decisión de diseño (persistir vs. releer) que no estaba explícita antes de este review —
    mencionarla si el dueño prefiere la columna persistida que la spec sugiere literalmente.

- [ ] **Paso 1: prueba que falla** — `backend/apps/payments/tests_situacion.py`:

```python
from decimal import Decimal

from django.test import SimpleTestCase

from apps.payments.situacion import Situacion, requiere_atencion, situacion_de_orden, situacion_de_reserva


class SituacionDeReservaTests(SimpleTestCase):
    def test_pendiente_sin_intent_es_sin_pago(self):
        self.assertEqual(
            situacion_de_reserva(estado='pendiente_pago', monto_pagado=None, monto_reembolsado=None),
            Situacion.SIN_PAGO,
        )

    def test_pendiente_con_intent_activo_es_pago_en_proceso(self):
        # Ya se intento cobrar (existe stripe_payment_intent_id): no ofrecer "Descartar"
        # como si nada hubiera pasado mientras el cobro puede seguir en curso.
        self.assertEqual(
            situacion_de_reserva(
                estado='pendiente_pago', monto_pagado=None, monto_reembolsado=None,
                tiene_intent_activo=True,
            ),
            Situacion.PAGO_EN_PROCESO,
        )

    def test_pagada_es_confirmada(self):
        for estado in ('pagada', 'asignada', 'completada'):
            with self.subTest(estado=estado):
                self.assertEqual(
                    situacion_de_reserva(estado=estado, monto_pagado=Decimal('4500'), monto_reembolsado=None),
                    Situacion.CONFIRMADA,
                )

    def test_cancelada_sin_cobro_es_liberada(self):
        self.assertEqual(
            situacion_de_reserva(estado='cancelada', monto_pagado=None, monto_reembolsado=None),
            Situacion.CANCELADA_LIBERADA,
        )

    def test_cancelada_con_cobro_sin_reembolso_requiere_atencion(self):
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=None)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_parcial_sigue_requiriendo_atencion(self):
        # Regresion del hallazgo #2 del review: un reembolso de $1 sobre $4500 pagados
        # NO es "ya solicitamos tu devolucion".
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=Decimal('1'))
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_completo_ya_solicitado(self):
        s = situacion_de_reserva(estado='cancelada', monto_pagado=Decimal('4500'), monto_reembolsado=Decimal('4500'))
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_SOLICITADA)
        self.assertFalse(requiere_atencion(s))


def _pago(estado_pi=None, pagado=None, reembolsado=None):
    return {'estado_pi': estado_pi, 'monto_pagado': pagado, 'monto_reembolsado': reembolsado}


class SituacionDeOrdenTests(SimpleTestCase):
    def test_armando_es_sin_pago(self):
        self.assertEqual(situacion_de_orden(estado_orden='armando', pagos=[]), Situacion.SIN_PAGO)

    def test_autorizando_sin_ningun_intent_todavia_es_pago_en_proceso(self):
        pagos = [_pago(None), _pago(None)]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.PAGO_EN_PROCESO)

    def test_autorizando_con_una_retenida_y_otra_pendiente_es_retenido_parcial(self):
        pagos = [_pago('requires_capture'), _pago('requires_payment_method')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.RETENIDO_PARCIAL)

    def test_autorizando_con_todas_retenidas_es_confirmando_cobro(self):
        pagos = [_pago('requires_capture'), _pago('requires_capture')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizando_con_una_succeeded_y_otra_retenida_es_confirmando_cobro(self):
        # Regresion del hallazgo #4: antes esta combinacion volvia RETENIDO_PARCIAL,
        # como si al cliente le faltara pagar algo. Ambos pagos ya tienen dinero
        # comprometido (uno cobrado, el otro retenido); no hay nada pendiente de pagar.
        pagos = [_pago('succeeded', pagado=Decimal('6400')), _pago('requires_capture')]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizando_con_todas_succeeded_es_confirmando_cobro(self):
        # Regresion del hallazgo #4: antes daba PAGO_EN_PROCESO (0 en requires_capture),
        # como si nadie hubiera pagado nada.
        pagos = [_pago('succeeded', pagado=Decimal('6400')), _pago('succeeded', pagado=Decimal('1650'))]
        self.assertEqual(situacion_de_orden(estado_orden='autorizando', pagos=pagos), Situacion.CONFIRMANDO_COBRO)

    def test_autorizada_es_confirmando_cobro(self):
        self.assertEqual(situacion_de_orden(estado_orden='autorizada', pagos=[]), Situacion.CONFIRMANDO_COBRO)

    def test_capturada_es_confirmada(self):
        self.assertEqual(situacion_de_orden(estado_orden='capturada', pagos=[]), Situacion.CONFIRMADA)

    def test_cancelada_con_un_cobro_sin_reembolsar_requiere_atencion(self):
        pagos = [_pago(pagado=Decimal('6400')), _pago(pagado=None)]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_parcial_sigue_requiriendo_atencion(self):
        pagos = [_pago(pagado=Decimal('6400'), reembolsado=Decimal('1'))]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))

    def test_cancelada_con_reembolso_confirmado(self):
        pagos = [_pago(pagado=Decimal('6400'), reembolsado=Decimal('6400'))]
        self.assertEqual(situacion_de_orden(estado_orden='cancelada', pagos=pagos), Situacion.CANCELADA_DEVOLUCION_SOLICITADA)

    def test_cancelada_sin_ningun_cobro_y_void_confirmado_es_liberada(self):
        pagos = [_pago('canceled'), _pago(None)]
        self.assertEqual(situacion_de_orden(estado_orden='cancelada', pagos=pagos), Situacion.CANCELADA_LIBERADA)

    def test_cancelada_con_void_fallido_no_es_liberada(self):
        # Regresion critica del hallazgo #2 del review (B:3390 original): si el
        # `payment_intents.cancel` fallo (StripeError atrapado en revertir_orden), el
        # PI real sigue en requires_capture. Nunca decir "se libero" en ese caso.
        pagos = [_pago('requires_capture'), _pago(None)]
        s = situacion_de_orden(estado_orden='cancelada', pagos=pagos)
        self.assertEqual(s, Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR)
        self.assertTrue(requiere_atencion(s))
```

- [ ] **Paso 2: verlas fallar** — `$PY manage.py test apps.payments.tests_situacion -v 2` → ERROR (módulo inexistente).

- [ ] **Paso 3: implementar** — `backend/apps/fleet/../payments/situacion.py` (ruta real: `backend/apps/payments/situacion.py`):

```python
"""Estado de cara al cliente de una Reserva o una Orden, calculado sin tocar Stripe.

Una sola fuente para lo que el aviso "Continuar reservación" muestra (spec §10.1): nunca se
infiere en el navegador. `situacion_de_orden` recibe el estado por-pago que ya calcula
`GetOrdenView` (que sí consulta Stripe); esta función solo combina lo que ya se leyó."""
from decimal import Decimal

from django.db import models

PENDIENTES_DE_CAPTURA = {'requires_capture'}
EN_PROCESO = {'requires_payment_method', 'requires_confirmation', 'requires_action', 'processing'}
# 'succeeded' cuenta como dinero comprometido igual que 'requires_capture': en ambos
# casos el cliente ya no tiene nada pendiente de pagar en ese componente, solo difiere
# si ya se capturo o sigue retenido. Ver hallazgo #4 del review.
COMPROMETIDO = PENDIENTES_DE_CAPTURA | {'succeeded'}
# Si el void de un PI sigue en uno de estos estados tras cancelar la orden, el
# `payment_intents.cancel` de `revertir_orden` no se confirmo (fallo silencioso
# atrapado como StripeError) y el dinero sigue retenido. Ver hallazgo #2.
AUN_RETENIDO_TRAS_CANCELAR = PENDIENTES_DE_CAPTURA | EN_PROCESO


class Situacion(models.TextChoices):
    SIN_PAGO = 'sin_pago', 'Sin pagar'
    PAGO_EN_PROCESO = 'pago_en_proceso', 'Pago en proceso'
    RETENIDO_PARCIAL = 'retenido_parcial', 'Pago parcial retenido'
    RETENIDO_TOTAL = 'retenido_total', 'Todo retenido'
    CONFIRMANDO_COBRO = 'confirmando_cobro', 'Confirmando el cobro'
    CONFIRMADA = 'confirmada', 'Confirmada'
    CANCELADA_LIBERADA = 'cancelada_liberada', 'Cancelada, sin cobro'
    CANCELADA_DEVOLUCION_SOLICITADA = 'cancelada_devolucion_solicitada', 'Cancelada, devolución solicitada'
    CANCELADA_DEVOLUCION_POR_CONFIRMAR = 'cancelada_devolucion_por_confirmar', 'Cancelada, devolución por confirmar'
    EXPIRADA = 'expirada', 'Expirada'
    NO_EXISTE = 'no_existe', 'No existe'


def _situacion_cancelada(*, pagado_total, reembolsado_total, aun_retenido):
    """Compartida por reserva y orden. `aun_retenido`=True cuando hay evidencia de que
    un void no se confirmo (ver AUN_RETENIDO_TRAS_CANCELAR); nunca se declara
    "liberada" mientras eso sea cierto, y un reembolso parcial nunca cuenta como
    solicitud completa (hallazgo #2 del review)."""
    if aun_retenido:
        return Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
    if pagado_total > 0:
        if reembolsado_total >= pagado_total:
            return Situacion.CANCELADA_DEVOLUCION_SOLICITADA
        return Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
    return Situacion.CANCELADA_LIBERADA


def situacion_de_reserva(*, estado, monto_pagado, monto_reembolsado, tiene_intent_activo=False):
    if estado == 'pendiente_pago':
        return Situacion.PAGO_EN_PROCESO if tiene_intent_activo else Situacion.SIN_PAGO
    if estado in ('pagada', 'asignada', 'completada'):
        return Situacion.CONFIRMADA
    if estado == 'cancelada':
        # Motor de una empresa: captura automatica, sin paso de "retenido" y sin
        # endpoint de cancelacion propio en este plan — monto_pagado is None siempre
        # significa que nunca hubo nada que liberar, sin necesitar evidencia de Stripe.
        return _situacion_cancelada(
            pagado_total=monto_pagado or Decimal('0'),
            reembolsado_total=monto_reembolsado or Decimal('0'),
            aun_retenido=False,
        )
    return Situacion.NO_EXISTE


def situacion_de_orden(*, estado_orden, pagos):
    if estado_orden == 'armando':
        return Situacion.SIN_PAGO
    if estado_orden == 'autorizando':
        con_evidencia = [p for p in pagos if p.get('estado_pi')]
        if not con_evidencia:
            return Situacion.PAGO_EN_PROCESO
        comprometidos = sum(1 for p in pagos if p.get('estado_pi') in COMPROMETIDO)
        if comprometidos == 0:
            return Situacion.PAGO_EN_PROCESO
        if comprometidos < len(pagos):
            return Situacion.RETENIDO_PARCIAL
        return Situacion.CONFIRMANDO_COBRO
    if estado_orden == 'autorizada':
        return Situacion.CONFIRMANDO_COBRO
    if estado_orden == 'capturada':
        return Situacion.CONFIRMADA
    if estado_orden == 'cancelada':
        pagado_total = sum((p.get('monto_pagado') or Decimal('0')) for p in pagos)
        reembolsado_total = sum((p.get('monto_reembolsado') or Decimal('0')) for p in pagos)
        aun_retenido = any(p.get('estado_pi') in AUN_RETENIDO_TRAS_CANCELAR for p in pagos)
        return _situacion_cancelada(
            pagado_total=pagado_total, reembolsado_total=reembolsado_total, aun_retenido=aun_retenido,
        )
    return Situacion.NO_EXISTE


def requiere_atencion(situacion):
    return situacion == Situacion.CANCELADA_DEVOLUCION_POR_CONFIRMAR
```

- [ ] **Paso 4: verlas pasar y commit**

```bash
$PY manage.py test apps.payments.tests_situacion -v 2
git add backend/apps/payments/situacion.py backend/apps/payments/tests_situacion.py
git commit -m "feat(payments): situacion del cliente como funcion pura (spec 10.1)"
```

### Tarea 6.2: Endpoints de resumen (sin datos personales) y de cancelación

**Files:**
- Modify: `backend/apps/payments/views.py` (nuevas `ResumenReservaView`, `ResumenOrdenView`,
  `CancelarOrdenPublicaView`; extrae `_reservas_info_de_orden` de `GetOrdenView.get`)
- Modify: `backend/apps/payments/urls.py`
- Test: `backend/apps/payments/tests_resumen.py`

**Interfaces:**
- Produces:
  - `GET /api/<empresa_slug>/reservas/resumen/?checkout_id=` → `404` si no existe **o si la reserva
    es de otra empresa** (predicado explícito `empresa=empresa`, no solo el scope RLS — mismo patrón
    que `EstadoReservaView`; en SQLite el scope no aísla, así que sin el predicado explícito una
    reserva de otra empresa se filtra igual, hallazgo #15 del review); si existe:
    `{situacion, producto, monto: str|None, moneda, forma_pago, folio: int, vence_en: null}` (una
    reserva no vence: solo las órdenes con captura manual tienen `vence_en`).
  - `GET /api/<sede_slug>/ordenes/resumen/?checkout_id=` → `404` si no existe; si existe:
    `{situacion, producto, moneda, forma_pago, montos: [{empresa, monto, monto_reembolsado, estado}],
    folio, vence_en: str|None, actualizado_en}`. `vence_en` = `orden.actualizado_en +
    ORDEN_TIMEOUT_AUTORIZACION` cuando `situacion` es `RETENIDO_PARCIAL`/`PAGO_EN_PROCESO` — **no**
    `creado_en`: `conciliar_pagos` compara contra `actualizado_en` (hallazgo #8 del review); usar otro
    campo hace que el aviso prometa un vencimiento que el conciliador todavía no aplicaría.
  - `POST /api/<sede_slug>/ordenes/<pk>/cancelar/` con `{checkout_id}` en el cuerpo → llama
    `revertir_orden(orden, 'cancelada por el cliente')`; `403` si el `checkout_id` no coincide (misma
    prueba de posesión que ya usa `CrearPagoOrdenView`); `409` si la orden ya se capturó mientras se
    procesaba la cancelación (`OrdenCerradaError`, misma carrera que ya maneja `OrdenAdmin` — hallazgo
    #14) — en ambos casos exitosos y en el 409 devuelve el **mismo contrato completo** que
    `ResumenOrdenView` (no solo `{situacion}`: el componente `ContinuarReservacion` necesita
    `producto`/`montos`/`folio` para mostrar el resultado, hallazgo #6).
  - `nombre_producto(reserva_o_paquete) -> str` (helper compartido: `paquete.nombre` o
    `servicio.nombre`, con fallback 'tu reserva').
  - `_resumen_de_orden(orden) -> dict` (helper de módulo, compartido por `ResumenOrdenView` y
    `CancelarOrdenPublicaView` para que ambos devuelvan exactamente el mismo contrato): arma `pagos`
    para `situacion_de_orden` cruzando `_reservas_info_de_orden(orden)` (trae `estado_pi`/`monto` de
    Stripe) con `reservas_de_orden(orden.id)` (trae `monto_reembolsado`) por `reserva_id`, y arma la
    respuesta completa.

- [ ] **Paso 1: prueba que falla** — `backend/apps/payments/tests_resumen.py` (fixture calcada de
  `TrasladoPagoFixture` para reserva y de `CrearOrdenTest`/`OrdenesModuloTest` para orden; solo el
  esqueleto esencial, copia el `setUp` de esas clases):

```python
from apps.payments.situacion import Situacion
from apps.payments.tests import TrasladoPagoFixture
from apps.testing import ApiTestCase


class ResumenReservaTest(TrasladoPagoFixture, ApiTestCase):
    def test_sin_pago(self):
        reserva = self.reserva()
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['situacion'], Situacion.SIN_PAGO)
        self.assertIsNone(r.json()['monto'])

    def test_no_existe(self):
        import uuid
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={uuid.uuid4()}')
        self.assertEqual(r.status_code, 404)

    def test_confirmada(self):
        reserva = self.reserva()
        reserva.estado = 'pagada'
        reserva.monto_pagado = 4500
        reserva.save(update_fields=['estado', 'monto_pagado'])
        r = self.client.get(f'/api/{self.empresa.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        self.assertEqual(r.json()['situacion'], Situacion.CONFIRMADA)

    def test_reserva_de_otra_empresa_da_404(self):
        # Hallazgo #15: el predicado explicito de empresa no debe depender solo del
        # scope RLS (que en SQLite no aisla). Otra empresa del fixture consultando el
        # mismo checkout_id no debe ver la reserva.
        reserva = self.reserva()
        otra = self.otra_empresa()  # ajusta al helper real del fixture para una segunda Empresa
        r = self.client.get(f'/api/{otra.slug}/reservas/resumen/?checkout_id={reserva.checkout_id}')
        self.assertEqual(r.status_code, 404)
```

Y una clase de orden que reutilice el `setUp` de `apps.payments.tests.OrdenesModuloTest` (cópialo o
impórtalo, siguiendo el patrón ya usado en `tests_orden_paquete.py`): verifica `SIN_PAGO` en
`armando`, `CONFIRMANDO_COBRO`/`CANCELADA_*` mockeando `configurar_stripe` igual que en esas clases, y
el endpoint de cancelar (`POST .../cancelar/`) con `checkout_id` correcto (200, llama
`revertir_orden`) y con uno equivocado (403, no llama nada). Suma estos tres casos, que reproducen
hallazgos críticos del review — sin ellos la regresión que motivó este plan vuelve a colarse:

- **Void fallido no dice "liberada".** Mockea `cliente.payment_intents.cancel` para que lance
  `stripe.error.StripeError`, deja el PI simulado en `requires_capture`, llama al endpoint de
  cancelar y verifica que la respuesta trae `situacion == CANCELADA_DEVOLUCION_POR_CONFIRMAR` (nunca
  `CANCELADA_LIBERADA`) y que la orden queda marcada para atención en el admin (Tarea 6.3).
- **`vence_en` coincide con conciliación.** Con una orden `autorizando` cuyo `actualizado_en` está a
  1 hora y `creado_en` a 30 horas (usa `Orden.objects.filter(pk=...).update(actualizado_en=..., creado_en=...)`
  para fijar ambos campos sin pasar por `auto_now`), verifica que `vence_en` del resumen sigue vigente
  (no vencido) — si el endpoint calculara desde `creado_en` este caso fallaría.
- **Cancelar contra una orden ya capturada devuelve 409, no 500.** Deja la orden en `Orden.Estado.CAPTURADA`
  antes de llamar al endpoint de cancelar; verifica `409` y que la respuesta trae el resumen actual
  (`situacion == CONFIRMADA`), no una traza de `OrdenCerradaError` sin manejar.

- [ ] **Paso 2: verlas fallar** — `$PY manage.py test apps.payments.tests_resumen -v 2` → 404 en toda
  ruta (no existen).

- [ ] **Paso 3: implementar.** En `apps/payments/views.py`, extrae el cuerpo del `for fila in filas:`
  de `GetOrdenView.get` (el que arma `estado_pi`/`client_secret`/`monto` por Stripe) a un helper de
  módulo `_reservas_info_de_orden(orden)` que devuelva la misma lista `reservas_info`, y haz que
  `GetOrdenView.get` lo llame (refactor: nada debe cambiar en su respuesta). Añade:

```python
def _nombre_producto(paquete, servicio):
    if paquete:
        return paquete.nombre
    if servicio:
        return servicio.nombre
    return 'tu reserva'


class ResumenReservaView(APIView):
    """Resumen sin datos personales para el aviso "Continuar reservación" (spec §10.1).
    No llama a Stripe: la situación sale de lo que el webhook/conciliar_pagos ya dejaron en la BD."""

    throttle_scope = 'estado_reserva'

    def get(self, request, empresa_slug):
        from .situacion import situacion_de_reserva

        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            crudo = request.query_params.get('checkout_id')
            try:
                checkout_id = uuid.UUID(str(crudo))
            except (ValueError, TypeError):
                return Response({'detail': 'checkout_id inválido.'}, status=400)
            # Predicado explicito de empresa ademas del scope RLS: en SQLite
            # scope.con_empresa no aisla filas (hallazgo #15 del review), y el
            # patron real ya establecido en EstadoReservaView (views.py:385) ya lo
            # hace asi. No lo dejes solo al scope.
            reserva = (
                Reserva.objects.filter(checkout_id=checkout_id, empresa=empresa)
                .order_by('-id').first()
            )
            if reserva is None:
                return Response({'detail': 'No se encontró.'}, status=404)
            situacion = situacion_de_reserva(
                estado=reserva.estado, monto_pagado=reserva.monto_pagado,
                monto_reembolsado=reserva.monto_reembolsado,
                tiene_intent_activo=bool(reserva.stripe_payment_intent_id),
            )
            return Response({
                'situacion': situacion,
                'producto': _nombre_producto(reserva.paquete, reserva.servicio),
                'monto': str(reserva.monto_pagado) if reserva.monto_pagado is not None else None,
                'moneda': reserva.moneda,
                'forma_pago': reserva.forma_pago,
                'folio': reserva.id,
                'vence_en': None,
            })


def _pagos_de_orden(orden, reservas_info):
    """Cruza `_reservas_info_de_orden` (estado_pi/monto via Stripe) con
    `reservas_de_orden` (monto_reembolsado; no vive en la primera) por reserva_id.
    Sin este cruce CANCELADA_DEVOLUCION_POR_CONFIRMAR nunca se detecta (hallazgo #3)."""
    from apps.bookings.orden_lectura import reservas_de_orden

    reembolsos = {f['reserva_id']: f.get('monto_reembolsado') for f in reservas_de_orden(orden.id)}
    return [
        {
            'estado_pi': r['pago']['estado_pi'],
            'monto_pagado': Decimal(r['pago']['monto']) if r['pago'].get('monto') else None,
            'monto_reembolsado': reembolsos.get(r['reserva_id']),
        }
        for r in reservas_info
    ]


def _resumen_de_orden(orden, *, status_override=None):
    """Contrato completo compartido por ResumenOrdenView y CancelarOrdenPublicaView
    (hallazgo #6: cancelar debe devolver lo mismo que consulta ContinuarReservacion,
    no solo {situacion})."""
    from .situacion import situacion_de_orden

    reservas_info = _reservas_info_de_orden(orden)
    pagos = _pagos_de_orden(orden, reservas_info)
    situacion = situacion_de_orden(estado_orden=orden.estado, pagos=pagos)
    vence_en = None
    if situacion in (Situacion.RETENIDO_PARCIAL, Situacion.PAGO_EN_PROCESO):
        # actualizado_en, no creado_en: conciliar_pagos compara contra actualizado_en
        # (management/commands/conciliar_pagos.py:177) — hallazgo #8.
        vence_en = (orden.actualizado_en + ORDEN_TIMEOUT_AUTORIZACION).isoformat()
    with scope.con_empresa(orden.empresa_lider):
        producto = _nombre_producto(orden.paquete, None)
    return Response({
        'situacion': situacion,
        'producto': producto,
        'moneda': orden.moneda,
        'forma_pago': orden.forma_pago,
        'montos': [
            {
                'empresa': r['empresa_slug'], 'monto': r['pago']['monto'],
                'monto_reembolsado': str(p['monto_reembolsado']) if p['monto_reembolsado'] else None,
                'estado': p['estado_pi'],
            }
            for r, p in zip(reservas_info, pagos)
        ],
        'folio': orden.id,
        'vence_en': vence_en,
        'actualizado_en': orden.actualizado_en.isoformat(),
    }, status=status_override or 200)


class ResumenOrdenView(APIView):
    """Resumen sin datos personales de una Orden. A diferencia de ResumenReservaView sí consulta
    Stripe (vía _reservas_info_de_orden) porque el estado por-pago no vive completo en la BD."""

    throttle_scope = 'estado_reserva'
    permission_classes = []

    def get(self, request, sede_slug):
        from apps.bookings.models import Orden
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        crudo = request.query_params.get('checkout_id')
        try:
            checkout_id = uuid.UUID(str(crudo))
        except (ValueError, TypeError):
            return Response({'detail': 'checkout_id inválido.'}, status=400)
        orden = _buscar_orden(sede, checkout_id=checkout_id)
        if not orden:
            return Response({'detail': 'No se encontró.'}, status=404)
        return _resumen_de_orden(orden)


class CancelarOrdenPublicaView(APIView):
    """El propio cliente cancela su orden a medias. Prueba de posesión = mismo checkout_id que
    creó la orden (igual que CrearPagoOrdenView). Nunca expone a otro checkout_id revertir una
    orden ajena."""

    throttle_scope = 'pagos'
    permission_classes = []

    def post(self, request, sede_slug, pk):
        from apps.bookings.models import Orden
        from apps.payments.ordenes import OrdenCerradaError, revertir_orden
        from apps.tenancy.models import Sede

        sede = get_object_or_404(Sede, slug=sede_slug, activo=True)
        orden = _buscar_orden(sede, pk=pk)
        if not orden:
            raise Http404('No se encontró la orden solicitada.')
        crudo = request.data.get('checkout_id')
        if not orden.checkout_id or str(orden.checkout_id) != str(crudo):
            return Response({'detail': 'checkout_id inválido para esta orden.'}, status=403)

        try:
            revertir_orden(orden, 'cancelada por el cliente desde "Continuar reservación"')
        except OrdenCerradaError:
            # Carrera: la orden se capturo mientras se procesaba la cancelacion (mismo
            # caso que ya atrapa OrdenAdmin.cancelar_orden, admin.py:325). No es un 500:
            # el cliente necesita ver que su reserva SI se confirmo, no una traza.
            with scope.con_empresa(orden.empresa_lider):
                orden.refresh_from_db()
            return _resumen_de_orden(orden, status_override=409)

        with scope.con_empresa(orden.empresa_lider):
            orden.refresh_from_db()
        return _resumen_de_orden(orden)
```

Añade `ORDEN_TIMEOUT_AUTORIZACION` y `OrdenCerradaError` al import desde `apps.payments.ordenes` y
`Situacion` desde `.situacion` en los imports de módulo de `views.py`. `Sede` **no** es un import de
módulo en este archivo (es local a cada vista, patrón ya establecido — ver `GetOrdenView.get`,
`views.py:909`); replicar ese mismo patrón local en `ResumenOrdenView.get` y
`CancelarOrdenPublicaView.post` en vez de asumir un `Sede` global (hallazgo #7: el código tal como
estaba en el plan compila pero lanza `NameError` al primer request real).

En `apps/payments/urls.py` añade las tres rutas: `reservas/resumen/` (bajo el prefijo de empresa),
`<sede_slug>/ordenes/resumen/` y `<sede_slug>/ordenes/<int:pk>/cancelar/` (mismo patrón que las rutas
de `ordenes/` ya existentes).

- [ ] **Paso 4: verlas pasar y commit**

```bash
$PY manage.py test apps.payments apps.bookings apps.fleet
git add backend/apps/payments
git commit -m "feat(payments): endpoints de resumen y cancelacion para Continuar reservacion"
```

### Tarea 6.3: Admin — "requiere atención" para Vendedora/Jefe

**Files:**
- Modify: `backend/apps/bookings/admin.py` (`ReservaAdmin`, `OrdenAdmin`)
- Test: `backend/apps/bookings/tests_admin_atencion.py`

**Decisión pendiente del dueño (no resuelta en este plan):** qué significa exactamente "confirmar"
una devolución — spec S:385 solo dice que queda `requiere_atencion` y que "quién confirma" es
Vendedora o Jefe, sin definir la mutación. Este plan asume, como default seguro, que confirmar
**no** dispara un reembolso/void real desde el admin (evita mover dinero con un clic sin la
verificación de Stripe delante); solo registra que una persona ya revisó el caso a mano (en el
dashboard de Stripe o donde corresponda) y lo marca resuelto en el sistema. Si el dueño quiere que el
botón dispare el `refund`/`cancel` de Stripe de verdad, hay que rediseñar la Tarea 6.3 antes de
implementarla — **no lo decidas en el código sin confirmarlo primero.**

**Interfaces:**
- Produces: filtro y columna "Requiere atención" en `ReservaAdmin` (usa
  `apps.payments.situacion.situacion_de_reserva`/`requiere_atencion` directamente sobre los campos
  del modelo, sin nueva columna en BD); acción real `confirmar_devolucion` en `ReservaAdmin` (Jefe
  **y** Vendedora, según S:326) que marca la reserva resuelta — bajo el default de arriba: setea
  `reembolsada=True`, `monto_reembolsado=monto_pagado`, `reembolsada_en=timezone.now()` **solo** si
  `requiere_atencion` es cierto para esa fila (evita marcar como resuelto algo que no lo requería);
  columna+acción equivalentes en `OrdenAdmin` operando sobre las reservas componentes de la orden
  (hallazgo #9 del review: la versión anterior de esta tarea solo tenía una columna de lectura,
  `atencion_col`, sin ninguna acción que de verdad cerrara la atención).

- [ ] **Paso 1: prueba que falla** — `backend/apps/bookings/tests_admin_atencion.py`: crea una
  `Reserva` cancelada con `monto_pagado` > 0 y `monto_reembolsado` en blanco; entra al admin como
  Jefe/Vendedora (usa el patrón de `crear_jefe`/`crear_vendedora` de `apps/testing.py`) y verifica que
  aparece en `changelist_view` filtrando por el nuevo filtro, y que una reserva pagada normal no.
  Suma: ejecutar `confirmar_devolucion` como Vendedora sobre esa reserva marca `reembolsada=True` y
  `monto_reembolsado == monto_pagado`, y queda registrado en el "History" del objeto (verifica
  `LogEntry.objects.filter(object_id=reserva.pk).exists()` tras la acción, o usa
  `change_message`/`admin.models.ADDITION` según el patrón real de auditoría del admin de Django);
  ejecutarla sobre una reserva que **no** requiere atención no cambia nada (guarda explícita).

- [ ] **Paso 2: verla fallar.**

- [ ] **Paso 3: implementar.** En `apps/bookings/admin.py` (import `from apps.payments.situacion
import requiere_atencion, situacion_de_reserva`):

```python
class RequiereAtencionFilter(admin.SimpleListFilter):
    title = 'requiere atención (devolución)'
    parameter_name = 'requiere_atencion'

    def lookups(self, request, model_admin):
        return (('si', 'Sí'),)

    def queryset(self, request, queryset):
        if self.value() != 'si':
            return queryset
        ids = [
            r.pk for r in queryset.only('pk', 'estado', 'monto_pagado', 'monto_reembolsado')
            if requiere_atencion(situacion_de_reserva(
                estado=r.estado, monto_pagado=r.monto_pagado, monto_reembolsado=r.monto_reembolsado,
            ))
        ]
        return queryset.filter(pk__in=ids)
```
Añádelo a `ReservaAdmin.list_filter`, una columna calculada y la acción real (con guarda de rol
Jefe/Vendedora en `get_actions`, mismo patrón que `OrdenAdmin.cancelar_orden`):

```python
    def requiere_atencion_col(self, obj):
        s = situacion_de_reserva(estado=obj.estado, monto_pagado=obj.monto_pagado, monto_reembolsado=obj.monto_reembolsado)
        return '⚠️ Confirmar devolución' if requiere_atencion(s) else ''
    requiere_atencion_col.short_description = 'Atención'

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not (
            scope.es_operador_plataforma(request.user)
            or request.user.groups.filter(name__in=['Jefe', 'Vendedora']).exists()
        ):
            actions.pop('confirmar_devolucion', None)
        return actions

    @admin.action(description='Confirmar devolución (ya se resolvió fuera del sistema)')
    def confirmar_devolucion(self, request, queryset):
        confirmadas = 0
        for reserva in queryset:
            s = situacion_de_reserva(
                estado=reserva.estado, monto_pagado=reserva.monto_pagado,
                monto_reembolsado=reserva.monto_reembolsado,
            )
            if not requiere_atencion(s):
                continue
            reserva.reembolsada = True
            reserva.monto_reembolsado = reserva.monto_pagado
            reserva.reembolsada_en = timezone.now()
            reserva.save(update_fields=['reembolsada', 'monto_reembolsado', 'reembolsada_en'])
            confirmadas += 1
        self.message_user(request, f'{confirmadas} reserva(s) marcadas como devolución confirmada.')
```
Añade `'confirmar_devolucion'` a `ReservaAdmin.actions`. Para `OrdenAdmin`, añade el mismo par
columna+acción operando sobre las reservas componentes: un método `atencion_col` que llame
`reservas_de_orden` por fila y aplique `situacion_de_orden`/`requiere_atencion` (documenta que es
O(n) llamadas por página, aceptable porque `OrdenAdmin` ya pagina pocas filas), y una acción
`confirmar_devolucion_orden` con la misma guarda de rol que `cancelar_orden` (`get_actions`, línea
310) que itera las reservas de cada orden bajo `scope.con_empresa(empresa)` por fila (mismo patrón
que `ordenes.revertir_orden`, ya que cada reserva pertenece a una empresa distinta bajo RLS) y aplica
la misma mutación que `ReservaAdmin.confirmar_devolucion`.

- [ ] **Paso 4: verlo pasar y commit**

```bash
$PY manage.py test apps.bookings
git add backend/apps/bookings
git commit -m "feat(bookings): admin muestra reservas y ordenes que requieren confirmar devolucion"
```

### Tarea 6.4: Vocabulario "retenido" en lo que ya ve el cliente

**Files:**
- Modify: `backend/CLAUDE.md` (nota de vocabulario)

- [ ] **Paso 1:** añade una nota corta en `backend/CLAUDE.md`, sección de pagos: "autorizado"/
  "autorización" son términos internos (código, admin); de cara al cliente (JSON de API, correos,
  WhatsApp) es siempre "retenido"/"retención". El backend no manda ningún string de cara al cliente
  con "autorizado" hoy (los correos actuales no lo mencionan); el frontend es quien debe respetarlo
  (ver plan de frontend, Sección 5).
- [ ] **Paso 2: Commit**

```bash
git add backend/CLAUDE.md
git commit -m "docs(backend): autorizado es termino interno, retenido de cara al cliente"
```

**STOP DURO — Cierre de la Sección 6.** Reportar al dueño: `situacion` calculada sin nuevas tablas,
endpoints de resumen/cancelar, admin con "requiere atención" para Vendedora/Jefe.

---

## Autorrevisión del plan

1. **Cobertura del spec:** D4 anticipo → 1.1-1.3; D5 USD → 4.3-4.4; D6 noches → 2.1-2.4, 3.2; D7 día de componente → 2.1, 2.4, 3.2, 4.3; D8 personas → 2.1, 3.1-3.4, 4.3; D3 extras por empresa → 4.1-4.4; D9 → sin cambios (ya es así) verificado en 4.4; contrato de API §6 → 1.3, 2.5, 3.2, 3.5, 4.3, 4.4; regla 1-8 de §5 → 2.2, 2.3.
2. **Marcadores pendientes:** ninguno. El código movido en 4.2 está completo en el plan. Las ediciones sobre código existente (3.2, 3.3, 4.3, 4.4) indican el bloque a reemplazar y traen el reemplazo completo.
3. **Consistencia de tipos:** `personas_de(servicio_id)`, `fecha_inicio_paquete`, `anticipo_disponible`, `es_cruza_empresa`, `componentes_calendario()`, `cotizar_personalizaciones`, `congelar_personalizaciones`, `validar_seleccion`, `sincronizar`, `errores_de_paquete`, `hay_conflicto_anticipo`, `peor_tarifa` se definen antes de usarse y con la misma firma en todas las tareas.
3b. **Continuar reservación (Sección 6, spec §10/§10.1):** situación → 6.1; endpoints de resumen/cancelar → 6.2; admin "requiere atención" → 6.3; vocabulario → 6.4. Depende de `ORDEN_TIMEOUT_AUTORIZACION` y `OrdenCerradaError` (ya existen en `ordenes.py`) y de `reservas_de_orden` (Tarea 6.2 confirma que trae `monto_reembolsado`). **Correcciones del review adversarial de 2026-09-23** (ver `docs/superpowers/plans/REVIEW-continuar-reservacion.md`) integradas en 6.1 (cancelada nunca "liberada" sin evidencia de void confirmado; estados transitorios de orden ya no se aplanan mal), 6.2 (`Sede` como import local, `vence_en` desde `actualizado_en`, resumen de reserva con predicado explícito de empresa, cancelar responde el contrato completo y maneja `OrdenCerradaError` como 409) y 6.3 (acción real de confirmación, no solo columna de lectura — con una decisión de alcance marcada explícitamente pendiente del dueño).
4. **Riesgos conocidos:** (a) los payloads de `apps/bookings/tests_checkout_serializer.py` pueden diferir de los usados en 3.2: copiar de ahí; (b) migraciones: el número lo asigna `makemigrations`; (c) las pruebas viejas que asumían el contrato anterior (paquete con hospedaje, `CrearOrdenTest`) se ajustan en 3.2 y 4.3 sin cambiar su intención.
