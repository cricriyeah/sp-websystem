# Salidas en varios días dentro de un paquete (versión ligera) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un paquete de una sola empresa pueda incluir una actividad de mar que se repite en días seguidos (4 o 6 días), sin sobreventa de pangas en ningún día, con **una sola panga para toda la estancia** (se asigna en la reserva, en la Agenda de siempre) y con habitaciones asignadas automáticamente (más de una si el grupo no cabe en una).

**Architecture:** `PaqueteServicio.salidas` (días seguidos, default 1) y un modelo mínimo `ReservaSalida` (una fila por día de mar de una reserva de paquete, sin panga ni capitán: solo marca el día ocupado, patrón de `ReservaOcupacion`). El motor de cupo cuenta las salidas por su fecha y deja de contar por `Reserva.fecha` a las reservas con salidas. La confirmación del pago valida y crea las salidas dentro de la misma transacción que ya hace rollback y reembolso 100 % si algo falla. La panga y el capitán de la reserva valen para todos sus días. El hospedaje elige automáticamente cuántas habitaciones hacen falta (el motor ya soporta `cantidad_recursos`) y el backoffice las reasigna con el inline de ocupaciones que ya existe.

**Tech Stack:** Django 5 / DRF, tests `OperadorTestCase`/`TestCase`, SQLite y Postgres (RLS por `empresa_id`).

**Spec:** `docs/superpowers/specs/2026-10-01-paquetes-por-persona-y-salidas-multidia-design.md` (sección "Cambio 2").

## Global Constraints

- Una actividad con `salidas = 1` (todo lo existente) se comporta **exactamente** igual que hoy. Todo el código nuevo se activa solo con `salidas > 1`.
- Sin sobreventa en ningún día: cada día de mar compite por la misma flota con las reservas sueltas y con otros paquetes.
- Solo paquetes de **una empresa**. Un paquete de dos empresas con `salidas > 1` se rechaza en `paquete_reglas`.
- Días seguidos: las salidas son `dia_estancia, dia_estancia+1, …, dia_estancia+salidas-1`, y deben caer dentro de la estancia (≤ noches del hospedaje).
- Cada tabla nueva con `empresa_id` lleva su política RLS `tenancy_alcance` (lo exige el guardarraíl de `apps/tenancy/tests_rls.py`).
- La confirmación de pago corre dentro de la transacción del webhook / `conciliar_pagos`; si falta cupo en cualquier día, rollback y reembolso 100 % (comportamiento actual, no se reescribe).
- Los locks de cupo se toman en orden de fecha ascendente (evita interbloqueos entre dos paquetes que se solapan).
- Python del venv: `C:/Users/kkjf/desarrollo/sistema-pescadeportiva/backend/venv/Scripts/python.exe` (`$PY`). Comandos desde `backend/` del worktree.
- Probar en SQLite **y** en Postgres antes de cerrar (contenedor `psd-pg`, ver `backend/CLAUDE.md`). Las pruebas de locks y de RLS solo prueban algo real en Postgres.

## Decisiones del dueño (2026-10-01)

- El precio es por persona completo: no baja si alguien no usa hospedaje o traslado (las cantidades por servicio son logística).
- Una sola panga para toda la estancia, asignada en la reserva (Agenda actual). No se asigna panga por día.
- Las habitaciones se asignan automáticamente (varias si hace falta) y el backoffice puede cambiarlas.

## Fuera de alcance (fase 2, se decide con el dueño)

- Panga distinta por día y pantalla de "Salidas al mar".
- Cuadrícula de panorama de la agenda con las salidas.
- Aviso de asignación y correo/WhatsApp de confirmación listando cada día de mar.
- Aviso de disponibilidad de todos los días al elegir la fecha de inicio en el checkout (hoy un paquete ya se cobra y, si falta cupo, se reembolsa solo; no cambia).
- Paquetes de dos empresas con actividad de varios días.

## File Map

| Archivo | Responsabilidad |
|---|---|
| `backend/apps/fleet/calendario_paquete.py` | `ComponenteCalendario.salidas`, `fechas_de_componente`, `fechas_de_actividad` (función pura) |
| `backend/apps/fleet/paquete_reglas.py` | `Componente.salidas` y las reglas de días seguidos / dentro de la estancia / una empresa |
| `backend/apps/fleet/models.py` | `PaqueteServicio.salidas`; `componente_desde/de` y `componentes_calendario` lo pasan |
| `backend/apps/fleet/admin.py`, `serializers.py` | Mostrar y exponer `salidas` |
| `backend/apps/bookings/models.py` | `ReservaSalida`; `_validar_cupo_de_paquete` revisa cada día; una panga cubre todos los días de la reserva |
| `backend/apps/bookings/migrations/0049_*.py`, `0050_*.py` | Tabla `ReservaSalida` y su política RLS |
| `backend/apps/bookings/cupo/adaptador.py` | El contexto de cupo cuenta salidas y excluye de `Reserva.fecha` a las reservas con salidas |
| `backend/apps/bookings/cupo/confirmacion.py` | Valida cada día y crea las `ReservaSalida` al confirmar |
| `backend/apps/bookings/cupo/nucleo.py`, `adaptador.py`, `confirmacion.py` | `habitaciones_necesarias` y asignación automática de varias habitaciones |
| `backend/apps/bookings/serializers.py`, `backend/apps/payments/views.py` | Pasan `salidas` al calendario del paquete |

<!-- arch-critic: omitido a propósito (el dueño reserva Opus para el orquestador); el riesgo se cubre con pruebas de sobreventa y la compuerta de Postgres -->

---

### Task 1: Calendario y reglas puras

**Files:**
- Modify: `backend/apps/fleet/calendario_paquete.py`
- Modify: `backend/apps/fleet/paquete_reglas.py`
- Test: `backend/apps/fleet/tests_calendario_paquete.py`, `backend/apps/fleet/tests_paquete_reglas.py`

**Interfaces:**
- Produces: `ComponenteCalendario(dia_estancia, estrategia_cupo, noches, salidas=1)`; `fechas_de_componente(inicio: date, dia_estancia: int, salidas: int = 1) -> list[date]`; `fechas_de_actividad(inicio: date, componentes) -> list[date]`; `Componente(..., tope_personas, salidas: int = 1)`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests_calendario_paquete.py` (importar los nombres nuevos desde `apps.fleet.calendario_paquete`):

```python
    def test_fechas_de_componente_son_dias_seguidos(self):
        self.assertEqual(
            fechas_de_componente(date(2026, 11, 14), 2, 4),
            [date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)],
        )

    def test_fechas_de_componente_una_salida_es_el_comportamiento_de_siempre(self):
        self.assertEqual(fechas_de_componente(date(2026, 11, 14), 1), [date(2026, 11, 14)])

    def test_fechas_de_actividad_toma_la_primera_actividad(self):
        componentes = [
            ComponenteCalendario(1, 'por_noche', 5),
            ComponenteCalendario(2, 'por_recurso_dia', None, 4),
        ]
        self.assertEqual(
            fechas_de_actividad(date(2026, 11, 14), componentes),
            [date(2026, 11, 15), date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 18)],
        )
        self.assertEqual(fecha_ancla(date(2026, 11, 14), componentes), date(2026, 11, 15))

    def test_fechas_de_actividad_sin_actividad_es_vacia(self):
        self.assertEqual(fechas_de_actividad(date(2026, 11, 14), [ComponenteCalendario(1, 'por_noche', 5)]), [])
```

En `tests_paquete_reglas.py`, usando el helper que ya usan las pruebas de ese archivo para armar `Componente` (leer el archivo y reutilizarlo; los campos son keyword), y cambiar la aserción de la línea ~144 a `'mismos días'`:

```python
    def _actividad(self, dia, salidas, empresa_id=1):
        return Componente(
            servicio_nombre='Pesca', empresa_id=empresa_id, estrategia_cupo='por_recurso_dia', noches=None,
            dia_estancia=dia, personas_incluidas=2, tope_personas=3, salidas=salidas,
        )

    def _hotel(self, noches):
        return Componente(
            servicio_nombre='Hotel', empresa_id=1, estrategia_cupo='por_noche', noches=noches,
            dia_estancia=1, personas_incluidas=2, tope_personas=None,
        )

    def test_salidas_seguidas_dentro_de_la_estancia_son_validas(self):
        # Paquete A: 5 noches, mar días 2 a 5.
        self.assertEqual(errores_de_paquete(
            permite_anticipo=False, componentes=[self._hotel(5), self._actividad(2, 4)],
        ), [])
        # Paquete B: 7 noches, mar días 2 a 7.
        self.assertEqual(errores_de_paquete(
            permite_anticipo=False, componentes=[self._hotel(7), self._actividad(2, 6)],
        ), [])

    def test_las_salidas_no_pueden_pasar_de_la_estancia(self):
        errores = errores_de_paquete(
            permite_anticipo=False, componentes=[self._hotel(5), self._actividad(2, 5)],
        )
        self.assertTrue(any('fuera de la estancia' in e for e in errores))

    def test_sin_hospedaje_no_hay_salidas_multiples(self):
        errores = errores_de_paquete(permite_anticipo=False, componentes=[self._actividad(1, 3)])
        self.assertTrue(any('dura un día' in e for e in errores))

    def test_salidas_solo_para_actividades(self):
        hotel = Componente(
            servicio_nombre='Hotel', empresa_id=1, estrategia_cupo='por_noche', noches=3,
            dia_estancia=1, personas_incluidas=2, tope_personas=None, salidas=2,
        )
        errores = errores_de_paquete(permite_anticipo=False, componentes=[hotel])
        self.assertTrue(any('solo aplican a actividades' in e for e in errores))

    def test_las_actividades_deben_compartir_los_mismos_dias(self):
        errores = errores_de_paquete(
            permite_anticipo=False,
            componentes=[self._hotel(5), self._actividad(2, 4), self._actividad(2, 3)],
        )
        self.assertTrue(any('mismos días' in e for e in errores))

    def test_salidas_multiples_no_se_admiten_entre_dos_empresas(self):
        traslado = Componente(
            servicio_nombre='Traslado', empresa_id=2, estrategia_cupo='bajo_demanda', noches=None,
            dia_estancia=1, personas_incluidas=2, tope_personas=None,
        )
        errores = errores_de_paquete(
            permite_anticipo=False, componentes=[self._actividad(1, 2, empresa_id=1), traslado],
        )
        self.assertTrue(any('una sola empresa' in e for e in errores))
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.fleet.tests_calendario_paquete apps.fleet.tests_paquete_reglas`
Expected: FAIL (`ImportError`/`TypeError` por `salidas` y `fechas_de_componente`).

- [ ] **Step 3: Implementar el calendario**

En `calendario_paquete.py`:

```python
@dataclass(frozen=True)
class ComponenteCalendario:
    dia_estancia: int
    estrategia_cupo: str
    noches: int | None
    salidas: int = 1
```

Y después de `fecha_de_componente`:

```python
def fechas_de_componente(inicio: date, dia_estancia: int, salidas: int = 1) -> list[date]:
    """Los días en que ocurre un componente: `salidas` días seguidos desde su día de estancia."""
    return [fecha_de_componente(inicio, dia_estancia + i) for i in range(max(1, salidas))]


def fechas_de_actividad(inicio: date, componentes) -> list[date]:
    """Días de mar del paquete: los de su primera actividad (por_recurso_dia). Vacío si no hay."""
    for c in componentes:
        if c.estrategia_cupo == 'por_recurso_dia':
            return fechas_de_componente(inicio, c.dia_estancia, c.salidas)
    return []
```

- [ ] **Step 4: Implementar las reglas**

En `paquete_reglas.py`, agregar `salidas: int = 1` al final de `Componente`. Dentro de `errores_de_paquete`:

1. En el `for c in componentes:` inicial, después del bloque de `noches`, agregar:

```python
        if c.salidas < 1:
            errores.append(f'"{c.servicio_nombre}": las salidas deben ser al menos 1.')
        elif c.salidas > 1 and c.estrategia_cupo != POR_RECURSO_DIA:
            errores.append(f'"{c.servicio_nombre}": las salidas solo aplican a actividades.')
```

2. Reemplazar el segundo ciclo (el de `noches_paquete`) por:

```python
    noches_paquete = hospedajes[0].noches if hospedajes and hospedajes[0].noches else None
    for c in componentes:
        if c.estrategia_cupo == POR_NOCHE or c.dia_estancia < 1:
            continue
        ultimo_dia = c.dia_estancia + max(1, c.salidas) - 1
        if noches_paquete is None and ultimo_dia != 1:
            errores.append(
                f'"{c.servicio_nombre}": sin hospedaje el paquete dura un día; el servicio debe caer el día 1.'
            )
        elif noches_paquete is not None and ultimo_dia > noches_paquete:
            errores.append(
                f'"{c.servicio_nombre}": el día {ultimo_dia} cae fuera de la estancia '
                f'({noches_paquete} noche(s); el último día válido es el {noches_paquete}).'
            )
```

3. Reemplazar el bloque `dias_actividad` por:

```python
    dias_actividad = {
        (c.dia_estancia, max(1, c.salidas)) for c in componentes if c.estrategia_cupo == POR_RECURSO_DIA
    }
    if len(dias_actividad) > 1:
        errores.append(
            'Las actividades del paquete deben ocurrir los mismos días de la estancia '
            '(mismo día de inicio y mismo número de salidas).'
        )

    if len(empresas) > 1 and any(c.salidas > 1 for c in componentes):
        errores.append('Una actividad de varios días solo se admite en un paquete de una sola empresa.')
```

Actualizar en `tests_paquete_reglas.py` la aserción existente `'mismo día'` a `'mismos días'`.

- [ ] **Step 5: Verificar que pasan**

Run: `$PY manage.py test apps.fleet.tests_calendario_paquete apps.fleet.tests_paquete_reglas`
Expected: PASS.

- [ ] **Step 6: (sin commit; el dueño no lo pidió)**

---

### Task 2: Modelos y migraciones

**Files:**
- Modify: `backend/apps/fleet/models.py` (`PaqueteServicio`, `componente_desde`, `componente_de`, `Paquete.componentes_calendario`)
- Modify: `backend/apps/fleet/admin.py:159`, `backend/apps/fleet/serializers.py:67`
- Modify: `backend/apps/bookings/models.py` (clase nueva `ReservaSalida`, después de `ReservaOcupacion`)
- Modify: `backend/apps/bookings/serializers.py:339`, `backend/apps/payments/views.py:543`
- Create: `backend/apps/fleet/migrations/0039_paqueteservicio_salidas.py`, `backend/apps/bookings/migrations/0049_reservasalida.py`, `backend/apps/bookings/migrations/0050_rls_reservasalida.py`
- Test: `backend/apps/bookings/tests_salidas.py` (nuevo)

**Interfaces:**
- Consumes: `ComponenteCalendario(..., salidas)`, `Componente(..., salidas)` (Task 1).
- Produces: `PaqueteServicio.salidas: int`; `ReservaSalida(empresa, reserva, servicio, fecha)` con `related_name='salidas'` en `Reserva`.

- [ ] **Step 1: Escribir las pruebas que fallan**

Crear `backend/apps/bookings/tests_salidas.py`:

```python
"""Modelo ReservaSalida: una salida al mar por día de una reserva de paquete."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.bookings.models import Reserva, ReservaSalida
from apps.fleet.models import Paquete, PaqueteServicio, Servicio
from apps.tenancy.models import Empresa, Sede
from apps.testing import OperadorTestCase


class SalidasBase(OperadorTestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre='Sede Salidas', slug='sede-salidas')
        self.empresa = Empresa.objects.create(sede=self.sede, nombre='Empresa Salidas', slug='empresa-salidas')
        self.pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Mar', slug='pesca-mar', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000.00'),
        )
        self.hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Mar', slug='hotel-mar', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('2000.00'),
        )
        self.paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Mar 4 días', slug='mar-4',
            precio_ancla=Decimal('10000.00'),
        )
        self.ps_hotel = PaqueteServicio.objects.create(paquete=self.paquete, servicio=self.hotel, orden=1, noches=5)
        self.ps_pesca = PaqueteServicio.objects.create(
            paquete=self.paquete, servicio=self.pesca, orden=2, dia_estancia=2, salidas=4,
        )
        self.inicio = date.today() + timedelta(days=20)

    def reserva_con_salidas(self, estado=Reserva.Estado.PAGADA, personas=2, salidas=4):
        reserva = Reserva.objects.create(
            empresa=self.empresa, paquete=self.paquete, fecha=self.inicio + timedelta(days=1),
            inicio_paquete=self.inicio, fecha_salida=self.inicio + timedelta(days=5), hora=time(6, 0),
            numero_personas=personas, nombre_cliente='Cliente Mar', telefono_cliente='+5216121234567',
            correo_cliente='mar@example.com', canal_origen='web', deslinde_aceptado=True, moneda='MXN',
            estado=estado,
        )
        for i in range(salidas):
            ReservaSalida.objects.create(
                empresa=self.empresa, reserva=reserva, servicio=self.pesca,
                fecha=self.inicio + timedelta(days=1 + i),
            )
        return reserva


class ReservaSalidaModelTests(SalidasBase):
    def test_paqueteservicio_guarda_las_salidas(self):
        self.ps_pesca.refresh_from_db()
        self.assertEqual(self.ps_pesca.salidas, 4)
        self.assertEqual(self.ps_hotel.salidas, 1)

    def test_una_reserva_tiene_una_salida_por_dia(self):
        reserva = self.reserva_con_salidas()
        fechas = list(reserva.salidas.order_by('fecha').values_list('fecha', flat=True))
        self.assertEqual(fechas, [self.inicio + timedelta(days=d) for d in (1, 2, 3, 4)])

    def test_no_se_repite_el_mismo_dia_de_la_misma_reserva(self):
        reserva = self.reserva_con_salidas()
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ReservaSalida.objects.create(
                    empresa=self.empresa, reserva=reserva, servicio=self.pesca, fecha=self.inicio + timedelta(days=1),
                )
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.bookings.tests_salidas`
Expected: FAIL (`ImportError: cannot import name 'ReservaSalida'`).

- [ ] **Step 3: Implementar los modelos**

`backend/apps/fleet/models.py`, en `PaqueteServicio` después de `personas_incluidas`:

```python
    salidas = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Solo actividades: cuántos días SEGUIDOS se repite, empezando en el día indicado '
                  'arriba. Ejemplo: día 2 con 4 salidas = días 2, 3, 4 y 5. Debe caber dentro de la estancia.',
    )
```

`componente_desde` gana el parámetro `salidas=1` y lo pasa a `Componente(..., salidas=salidas)`; `componente_de(ps)` lo llama con `salidas=ps.salidas`; `Paquete.componentes_calendario` construye `ComponenteCalendario(dia_estancia=ps.dia_estancia, estrategia_cupo=..., noches=ps.noches, salidas=ps.salidas)`. En `backend/apps/bookings/serializers.py:339` y `backend/apps/payments/views.py:543` agregar `ps.salidas` / `ps['salidas']` al `ComponenteCalendario` (leer cada sitio: el segundo trabaja con diccionarios, `filas_ps[servicio.id]`; agregar la clave `salidas` donde se arma ese diccionario).

`backend/apps/fleet/admin.py:159`: agregar `'salidas'` a `fields` de `PaqueteServicioInline`. `backend/apps/fleet/serializers.py:67`: agregar `'salidas'` a `fields` de `PaqueteServicioSerializer`.

`backend/apps/bookings/models.py`, después de `ReservaOcupacion`:

```python
class ReservaSalida(models.Model):
    """Una salida al mar de una reserva de paquete que repite la actividad en días seguidos.

    Existe solo cuando la actividad del paquete tiene `salidas > 1`; el resto de las reservas
    siguen contando por `Reserva.fecha`. Cuenta como ocupación mientras la reserva esté en un
    estado que ocupa cupo (no se guarda una bandera aparte: se deriva de `reserva.estado`).
    No lleva panga ni capitán: los de la reserva valen para todos sus días.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='salidas')
    reserva = models.ForeignKey(Reserva, on_delete=models.CASCADE, related_name='salidas')
    servicio = models.ForeignKey('fleet.Servicio', on_delete=models.PROTECT, related_name='+')
    fecha = models.DateField()
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha']
        verbose_name = 'salida al mar'
        verbose_name_plural = 'salidas al mar'
        constraints = [
            models.UniqueConstraint(fields=['reserva', 'servicio', 'fecha'], name='reservasalida_unica_por_dia'),
        ]
        indexes = [models.Index(fields=['empresa', 'fecha'], name='reservasalida_empresa_fecha')]

    def __str__(self):
        return f'Salida {self.fecha} — Reserva #{self.reserva_id}'
```

- [ ] **Step 4: Generar y escribir las migraciones**

Run: `$PY manage.py makemigrations fleet -n paqueteservicio_salidas` y `$PY manage.py makemigrations bookings -n reservasalida`.
Expected: una `AddField` en fleet 0039 y una `CreateModel` en bookings 0049 (verificar que no traigan cambios ajenos).

Crear `backend/apps/bookings/migrations/0050_rls_reservasalida.py` copiando `0027_rls_reservaocupacion.py` con `TABLAS_CON_EMPRESA_ID = ['bookings_reservasalida']`, el docstring adaptado y `dependencies = [('bookings', '0049_reservasalida')]`; mantener las funciones `aplicar_politicas_*` / `revertir_politicas_*` renombradas a `..._salida`.

- [ ] **Step 5: Verificar que pasan**

Run: `$PY manage.py test apps.bookings.tests_salidas apps.fleet apps.tenancy`
Expected: PASS (`tests_rls` se salta en SQLite; se verifica en Postgres en la Task 8).

---

### Task 3: El motor de cupo cuenta las salidas

**Files:**
- Modify: `backend/apps/bookings/cupo/adaptador.py` (`obtener_contexto_cupo`, `obtener_contexto_rango`)
- Test: `backend/apps/bookings/tests_cupo_salidas.py` (nuevo; reusa `SalidasBase` de `tests_salidas.py`)

**Interfaces:**
- Consumes: `ReservaSalida` (Task 2).
- Produces: `obtener_contexto_cupo(fecha, empresa, excluir_pk)` y `obtener_contexto_rango(...)` cuentan las salidas como un grupo en su día; una reserva con salidas no cuenta por `Reserva.fecha`.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
"""El cupo cuenta cada salida en su día y no cuenta dos veces el primer día."""
from datetime import timedelta

from apps.bookings.cupo.adaptador import obtener_contexto_cupo, obtener_contexto_rango
from apps.bookings.models import Reserva, evaluar_cupo
from apps.bookings.tests_salidas import SalidasBase
from apps.fleet.models import Embarcacion


class CupoConSalidasTests(SalidasBase):
    def dia(self, n):
        return self.inicio + timedelta(days=n)

    def test_cada_dia_de_mar_cuenta_un_grupo(self):
        self.reserva_con_salidas(personas=2)
        for n in (1, 2, 3, 4):
            self.assertEqual(obtener_contexto_cupo(self.dia(n), self.empresa).grupos, [2], f'día {n}')
        self.assertEqual(obtener_contexto_cupo(self.dia(5), self.empresa).grupos, [])

    def test_el_primer_dia_no_se_cuenta_dos_veces(self):
        self.reserva_con_salidas(personas=2)
        self.assertEqual(len(obtener_contexto_cupo(self.dia(1), self.empresa).grupos), 1)

    def test_una_reserva_cancelada_no_cuenta(self):
        self.reserva_con_salidas(estado=Reserva.Estado.CANCELADA)
        self.assertEqual(obtener_contexto_cupo(self.dia(2), self.empresa).grupos, [])

    def test_excluir_pk_excluye_tambien_sus_salidas(self):
        reserva = self.reserva_con_salidas()
        self.assertEqual(obtener_contexto_cupo(self.dia(3), self.empresa, excluir_pk=reserva.pk).grupos, [])

    def test_el_rango_cuenta_las_salidas(self):
        self.reserva_con_salidas(personas=3)
        ctx = obtener_contexto_rango(self.dia(0), self.dia(6), self.empresa)
        self.assertEqual(ctx.grupos_por_fecha.get(self.dia(2)), [3])
        self.assertNotIn(self.dia(5), ctx.grupos_por_fecha)

    def test_no_se_puede_vender_una_panga_ya_ocupada_un_dia_intermedio(self):
        Embarcacion.objects.create(empresa=self.empresa, nombre='Panga Unica', clase='chica', capacidad_maxima=3)
        self.reserva_con_salidas(personas=2)
        # El día 3 de mar la única panga ya va con el paquete: otro grupo no cabe.
        self.assertEqual(evaluar_cupo(self.dia(3), 2, self.empresa), 'sin_panga')
        # El día 5 la panga está libre.
        self.assertIsNone(evaluar_cupo(self.dia(5), 2, self.empresa))
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.bookings.tests_cupo_salidas`
Expected: FAIL (los días 2 a 4 devuelven `[]`; el día 1 cuenta mal).

- [ ] **Step 3: Implementar**

En `adaptador.py`, `obtener_contexto_cupo`: importar `ReservaSalida` junto a `Reserva`, y reemplazar la consulta de ocupadas y el cálculo de `grupos`:

```python
    ocupadas = Reserva.objects.filter(
        fecha=fecha,
        estado__in=ESTADOS_QUE_OCUPAN_CUPO,
        empresa=empresa,
        salidas__isnull=True,  # las reservas con salidas cuentan por sus salidas, no por `fecha`
    )
    salidas = ReservaSalida.objects.filter(
        fecha=fecha, empresa=empresa, reserva__estado__in=ESTADOS_QUE_OCUPAN_CUPO,
    )
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)
        salidas = salidas.exclude(reserva_id=excluir_pk)

    grupos = [
        *ocupadas.values_list('numero_personas', flat=True),
        *salidas.values_list('reserva__numero_personas', flat=True),
    ]
```

En `obtener_contexto_rango`, con el mismo criterio:

```python
    grupos_por_fecha = defaultdict(list)
    for fecha, personas_de_esa in Reserva.objects.filter(
        fecha__range=(desde, hasta),
        estado__in=ESTADOS_QUE_OCUPAN_CUPO,
        empresa=empresa,
        salidas__isnull=True,
    ).values_list('fecha', 'numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)
    for fecha, personas_de_esa in ReservaSalida.objects.filter(
        fecha__range=(desde, hasta), empresa=empresa, reserva__estado__in=ESTADOS_QUE_OCUPAN_CUPO,
    ).values_list('fecha', 'reserva__numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)
```

(Cuidar que `grupos` quede ordenado por quien lo consuma: las estrategias ya ordenan antes de comparar; no cambia.)

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.bookings.tests_cupo_salidas apps.bookings.tests_cupo_nucleo apps.bookings.tests_cupo_adaptador apps.bookings.tests_cupo_rango apps.bookings.cupo`
Expected: PASS (las pruebas de cupo existentes no cambian: sin salidas el resultado es idéntico).

---

### Task 4: Confirmación del pago y validación por día

**Files:**
- Modify: `backend/apps/bookings/cupo/confirmacion.py` (caso B, rama `por_recurso_dia`, ~líneas 106-123)
- Modify: `backend/apps/bookings/models.py` (`_validar_cupo_de_paquete`, ~línea 224)
- Test: `backend/apps/payments/tests_salidas_multidia.py` (nuevo)

**Interfaces:**
- Consumes: `fechas_de_componente` (Task 1), `ReservaSalida` (Task 2), contexto de cupo (Task 3).
- Produces: confirmar el pago de un paquete con `salidas > 1` valida cupo en cada día (en orden de fecha, con su lock) y crea una `ReservaSalida` por día; si algún día no tiene cupo lanza `SinCupoError` (rollback y reembolso 100 % ya existentes).

- [ ] **Step 1: Escribir las pruebas que fallan**

Mismo estilo y fixtures que `AplicarPagoCupoHospedajeYPaquetesTests` en `payments/tests.py` (empresa con llaves Stripe de prueba, `crear_flota`, `aplicar_pago_exitoso`, `APLICADO`); copiar los imports de ese archivo. Una clase `AplicarPagoSalidasMultidiaTests(TestCase)` con:

```python
    def _paquete_de_mar(self, noches=5, dia=2, salidas=4):
        s_pesca = Servicio.objects.create(
            empresa=self.empresa, nombre='Pesca Mar', slug='pesca-mar', tipo_servicio='pesca',
            estrategia_cupo='por_recurso_dia', precio_base=Decimal('3000.00'), activo=True,
        )
        s_hotel = Servicio.objects.create(
            empresa=self.empresa, nombre='Hotel Mar', slug='hotel-mar', tipo_servicio='hospedaje',
            estrategia_cupo='por_noche', estrategia_precio='por_noche', precio_base=Decimal('2000.00'), activo=True,
        )
        Recurso.objects.create(empresa=self.empresa, servicio=s_hotel, nombre='Hab 1', capacidad_maxima=2, activo=True)
        paquete = Paquete.objects.create(
            sede=self.sede, empresa_lider=self.empresa, nombre='Mar', slug='mar',
            precio_ancla=Decimal('10000.00'), permite_anticipo=False, activo=True,
        )
        PaqueteServicio.objects.create(paquete=paquete, servicio=s_hotel, orden=1, noches=noches)
        PaqueteServicio.objects.create(paquete=paquete, servicio=s_pesca, orden=2, dia_estancia=dia, salidas=salidas)
        return paquete, s_pesca

    def _reserva_pendiente(self, paquete, inicio, dia=2, noches=5):
        reserva = Reserva(
            empresa=self.empresa, paquete=paquete, fecha=inicio + timedelta(days=dia - 1), inicio_paquete=inicio,
            fecha_salida=inicio + timedelta(days=noches), hora=time(6, 0), numero_personas=2,
            nombre_cliente='Cliente Mar', telefono_cliente='+5216121234567', correo_cliente='mar@example.com',
            canal_origen=Reserva.CanalOrigen.WEB, deslinde_aceptado=True, deslinde_nombre='Cliente Mar',
            checkout_id=uuid.uuid4(), moneda='MXN', precio_total=Decimal('10000.00'),
            forma_pago=Reserva.FormaPago.COMPLETO,
        )
        reserva.save()
        return reserva

    def _intent(self, reserva):
        return {
            'id': f'pi_mar_{reserva.pk}', 'amount_received': 1000000, 'currency': 'mxn',
            'metadata': {'reserva_id': str(reserva.pk)}, 'created': int(timezone.now().timestamp()),
        }

    def test_confirmar_el_pago_crea_una_salida_por_dia_de_mar(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, s_pesca = self._paquete_de_mar()
            reserva = self._reserva_pendiente(paquete, inicio)
            self.assertEqual(aplicar_pago_exitoso(self._intent(reserva), self.empresa), APLICADO)
            fechas = list(reserva.salidas.order_by('fecha').values_list('fecha', flat=True))
        self.assertEqual(fechas, [inicio + timedelta(days=d) for d in (1, 2, 3, 4)])

    def test_sin_cupo_en_un_dia_intermedio_no_deja_salidas_y_reembolsa(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, s_pesca = self._paquete_de_mar()
            reserva = self._reserva_pendiente(paquete, inicio)
            # Llenar la flota el día 3 de mar con reservas sueltas de pesca.
            tope = len(capacidades_disponibles(inicio + timedelta(days=2), self.empresa))
            for i in range(tope):
                Reserva.objects.create(
                    empresa=self.empresa, servicio=s_pesca, fecha=inicio + timedelta(days=2), hora=time(6, 0),
                    numero_personas=3, nombre_cliente=f'Lleno {i}', telefono_cliente='+5216121234567',
                    correo_cliente=f'l{i}@example.com', canal_origen='whatsapp', moneda='MXN',
                    estado=Reserva.Estado.PAGADA,
                )
            with mock.patch('apps.payments.services.reembolsar', return_value=True) as reembolso:
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.salidas.count(), 0)
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
            reembolso.assert_called_once()
```

(`capacidades_disponibles` se importa de `apps.fleet.models`. Si `crear_flota` no deja capacidad 3 en todas las pangas, el segundo test sigue siendo válido porque llena tantas reservas como pangas haya a flote; las reservas sueltas con `objects.create` no pasan por `clean`.)

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.payments.tests_salidas_multidia`
Expected: FAIL (no se crean salidas; el segundo día no se valida).

- [ ] **Step 3: Implementar la confirmación**

En `confirmacion.py`, importar `fechas_de_componente` (de `apps.fleet.calendario_paquete`) y `ReservaSalida`. Reemplazar el cuerpo de `if estrategia == 'por_recurso_dia':` del caso B por:

```python
            if estrategia == 'por_recurso_dia':
                personas = reserva.personas_de(servicio.pk)
                if ps.salidas > 1:
                    fechas = sorted(fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas))
                else:
                    fechas = [reserva.fecha]
                for dia in fechas:
                    bloquear_cupo(reserva.empresa_id, dia, servicio_id=servicio.pk)
                    motivo = evaluar_cupo(
                        dia, personas, reserva.empresa, excluir_pk=reserva.pk,
                        estrategia_cupo='por_recurso_dia', servicio_id=servicio.pk,
                    )
                    if motivo:
                        raise SinCupoError(
                            f'No hay cupo disponible para el componente {servicio.nombre} el {dia} ({motivo}).'
                        )
                if ps.salidas > 1:
                    for dia in fechas:
                        ReservaSalida.objects.create(
                            empresa=reserva.empresa, reserva=reserva, servicio=servicio, fecha=dia,
                        )
                ReservaPaqueteComponente.objects.create(
                    reserva=reserva, servicio=servicio, empresa=reserva.empresa,
                    estado_cupo=ReservaPaqueteComponente.EstadoCupo.OK,
                )
```

En `models.py`, `_validar_cupo_de_paquete`, rama `por_recurso_dia`: iterar las fechas igual (con `ps.salidas > 1` usar `fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas)`, si no `[reserva.fecha]`), llamar `evaluar_cupo` por cada una con `excluir_pk=reserva.pk` y levantar `ValidationError({'fecha': f'No hay cupo disponible para el servicio {ps.servicio.nombre} el {dia} ({motivo}).'})`.

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.payments.tests_salidas_multidia apps.payments.tests apps.bookings`
Expected: PASS (los paquetes de un solo día no cambian).

---

### Task 5: Una panga cubre todos los días de la reserva

**Files:**
- Modify: `backend/apps/bookings/models.py` (`Reserva._validar_una_salida_por_dia`)
- Test: `backend/apps/bookings/tests_salidas_panga.py` (nuevo; reusa `SalidasBase` de `tests_salidas.py`)

**Interfaces:**
- Consumes: `ReservaSalida` (Task 2).
- Produces: la `embarcacion` y el `capitan` de una reserva con salidas cuentan como usados en **cada** día de mar; la regla "una panga, una salida por día" cruza reservas sueltas y paquetes. El estado pasa a `asignada` al poner la panga, como siempre (sin cambios en `_derivar_estado_de_asignacion`).

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
"""Una sola panga para toda la estancia: ocupa todos los días de mar."""
from datetime import time, timedelta

from django.core.exceptions import ValidationError

from apps.bookings.models import Reserva
from apps.bookings.tests_salidas import SalidasBase
from apps.fleet.models import Capitan, Embarcacion


class UnaPangaTodaLaEstanciaTests(SalidasBase):
    def setUp(self):
        super().setUp()
        self.p1 = Embarcacion.objects.create(empresa=self.empresa, nombre='P1', clase='chica', capacidad_maxima=3)
        self.p2 = Embarcacion.objects.create(empresa=self.empresa, nombre='P2', clase='chica', capacidad_maxima=3)
        self.reserva = self.reserva_con_salidas()

    def _suelta(self, dia, embarcacion):
        return Reserva(
            empresa=self.empresa, servicio=self.pesca, fecha=self.inicio + timedelta(days=dia), hora=time(6, 0),
            numero_personas=2, nombre_cliente='Suelta', telefono_cliente='+5216121234567',
            correo_cliente='s@example.com', canal_origen='whatsapp', moneda='MXN',
            estado=Reserva.Estado.ASIGNADA, embarcacion=embarcacion,
        )

    def _asignar(self, reserva, embarcacion):
        reserva.embarcacion = embarcacion
        reserva.full_clean()
        reserva.save()

    def test_poner_la_panga_da_el_viaje_por_asignado(self):
        self._asignar(self.reserva, self.p1)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, Reserva.Estado.ASIGNADA)

    def test_la_panga_del_paquete_choca_con_una_reserva_suelta_en_un_dia_intermedio(self):
        self._asignar(self.reserva, self.p1)
        with self.assertRaises(ValidationError) as ctx:
            self._suelta(3, self.p1).full_clean()  # día 3 de mar
        self.assertIn('embarcacion', ctx.exception.message_dict)

    def test_la_misma_panga_en_un_dia_libre_es_valida(self):
        self._asignar(self.reserva, self.p1)
        self._suelta(6, self.p1).full_clean()  # el día 6 ya no hay mar del paquete

    def test_una_reserva_suelta_ya_asignada_bloquea_la_panga_a_un_paquete(self):
        suelta = self._suelta(3, self.p1)
        suelta.full_clean()
        suelta.save()
        self.reserva.embarcacion = self.p1
        with self.assertRaises(ValidationError) as ctx:
            self.reserva.full_clean()
        self.assertIn('embarcacion', ctx.exception.message_dict)

    def test_dos_paquetes_no_comparten_panga_si_se_traslapan(self):
        self._asignar(self.reserva, self.p1)
        otra = self.reserva_con_salidas()
        otra.embarcacion = self.p1
        with self.assertRaises(ValidationError):
            otra.full_clean()
        otra.embarcacion = self.p2
        otra.full_clean()

    def test_el_capitan_tampoco_se_repite_en_ningun_dia_de_mar(self):
        capitan = Capitan.objects.create(empresa=self.empresa, nombre='Capitán Uno')
        self.reserva.capitan = capitan
        self.reserva.full_clean()
        self.reserva.save()
        suelta = self._suelta(2, self.p2)
        suelta.capitan = capitan
        with self.assertRaises(ValidationError) as ctx:
            suelta.full_clean()
        self.assertIn('capitan', ctx.exception.message_dict)
```

(Verificar al implementar los campos obligatorios de `fleet.Capitan`; si hay otros, completarlos en la prueba.)

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.bookings.tests_salidas_panga`
Expected: FAIL (la panga solo se compara contra `Reserva.fecha`).

- [ ] **Step 3: Implementar**

En `models.py`, dentro de `Reserva`:

```python
    def _fechas_de_viaje(self):
        """Los días en que esta reserva usa panga: sus salidas, o su fecha si es de un solo día."""
        if self.pk and self.salidas.exists():
            return list(self.salidas.values_list('fecha', flat=True))
        return [self.fecha]
```

Reescribir el cuerpo de `_validar_una_salida_por_dia`, conservando el `return` inicial para servicios que no son `por_recurso_dia` y los textos de error actuales (con `dia` en lugar de `self.fecha`):

```python
        for dia in self._fechas_de_viaje():
            del_dia = Reserva.objects.filter(
                models.Q(fecha=dia) | models.Q(salidas__fecha=dia),
                estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa_id=self.empresa_id,
            ).distinct()
            if self.pk:
                del_dia = del_dia.exclude(pk=self.pk)

            if self.embarcacion_id and del_dia.filter(embarcacion_id=self.embarcacion_id).exists():
                raise ValidationError({
                    'embarcacion': f'{self.embarcacion.nombre} ya tiene un viaje el {dia}. '
                                   f'Una panga hace una sola salida por dia.',
                })
            if self.capitan_id and del_dia.filter(capitan_id=self.capitan_id).exists():
                raise ValidationError({
                    'capitan': f'{self.capitan.nombre} ya tiene un viaje el {dia}. '
                               f'Un capitan hace una sola salida por dia.',
                })
```

(Leer el cuerpo actual del método antes de reemplazarlo y conservar sus mensajes exactos para que las pruebas existentes de la agenda sigan pasando.)

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.bookings.tests_salidas_panga apps.bookings.tests_agenda apps.bookings.tests`
Expected: PASS (las reservas de un solo día no cambian).

---

### Task 6: Habitaciones automáticas (varias si el grupo no cabe en una)

**Files:**
- Modify: `backend/apps/bookings/cupo/nucleo.py` (función pura nueva)
- Modify: `backend/apps/bookings/cupo/adaptador.py` (`evaluar_disponibilidad_hospedaje`)
- Modify: `backend/apps/bookings/cupo/confirmacion.py` (`_asignar_cupo_hospedaje`)
- Modify: `backend/apps/bookings/serializers.py` (`_derivar_de_paquete`, la comprobación "Ninguna habitación admite")
- Test: `backend/apps/bookings/tests_cupo_nucleo.py`, `backend/apps/payments/tests_salidas_multidia.py`

**Interfaces:**
- Produces: `habitaciones_necesarias(capacidades_libres: list[int], personas: int) -> int | None`; el hospedaje reserva 1..N habitaciones según el grupo. El backoffice ya puede reasignar con `ReservaOcupacionInline`.

- [ ] **Step 1: Escribir las pruebas que fallan**

En `tests_cupo_nucleo.py`:

```python
    def test_habitaciones_necesarias_toma_las_mas_grandes_primero(self):
        self.assertEqual(habitaciones_necesarias([2, 2, 2, 4], 5), 2)   # 4 + 2
        self.assertEqual(habitaciones_necesarias([2, 2], 2), 1)
        self.assertEqual(habitaciones_necesarias([2, 2], 4), 2)

    def test_habitaciones_necesarias_none_si_no_alcanzan(self):
        self.assertIsNone(habitaciones_necesarias([2, 2], 5))
        self.assertIsNone(habitaciones_necesarias([], 1))
```

En `tests_salidas_multidia.py` (misma clase `AplicarPagoSalidasMultidiaTests`; `_paquete_de_mar` deja una habitación de 2 personas):

```python
    def test_un_grupo_que_no_cabe_en_una_habitacion_ocupa_dos(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            Recurso.objects.create(empresa=self.empresa, servicio=hotel, nombre='Hab 2', capacidad_maxima=2, activo=True)
            reserva = self._reserva_pendiente(paquete, inicio)
            Reserva.objects.filter(pk=reserva.pk).update(
                numero_personas=3, personas_por_servicio={str(hotel.pk): 3},
            )
            reserva.refresh_from_db()
            self.assertEqual(aplicar_pago_exitoso(self._intent(reserva), self.empresa), APLICADO)
            self.assertEqual(reserva.ocupaciones.count(), 2)

    def test_si_no_alcanzan_las_habitaciones_juntas_no_se_confirma(self):
        inicio = date.today() + timedelta(days=30)
        with scope.con_empresa(self.empresa):
            crear_flota(self.empresa)
            paquete, _ = self._paquete_de_mar()
            hotel = Servicio.objects.get(slug='hotel-mar')
            reserva = self._reserva_pendiente(paquete, inicio)
            Reserva.objects.filter(pk=reserva.pk).update(
                numero_personas=3, personas_por_servicio={str(hotel.pk): 3},
            )
            reserva.refresh_from_db()
            with mock.patch('apps.payments.services.reembolsar', return_value=True):
                aplicar_pago_exitoso(self._intent(reserva), self.empresa)
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)
```

(En el segundo test hay una sola habitación de 2, así que 3 personas no alcanzan.)

- [ ] **Step 2: Verificar que fallan**

Run: `$PY manage.py test apps.bookings.tests_cupo_nucleo apps.payments.tests_salidas_multidia`
Expected: FAIL (`ImportError: habitaciones_necesarias`; solo se asigna una habitación).

- [ ] **Step 3: Implementar**

En `nucleo.py`:

```python
def habitaciones_necesarias(capacidades_libres, personas):
    """Menor cantidad de habitaciones, tomando siempre las más grandes, cuya capacidad suma al
    menos `personas`. None si ni todas juntas alcanzan."""
    total = 0
    for cantidad, capacidad in enumerate(sorted(capacidades_libres, reverse=True), start=1):
        total += capacidad
        if total >= personas:
            return cantidad
    return None
```

En `adaptador.py`, `evaluar_disponibilidad_hospedaje`: cambiar el parámetro a `cantidad_recursos: int | None = None` y, tras obtener `recursos_con_ocupaciones` y antes de armar la demanda:

```python
    if cantidad_recursos is None:
        libres = recursos_disponibles_en_rango(recursos_con_ocupaciones, check_in, check_out)
        cantidad_recursos = habitaciones_necesarias([cap for _, cap in libres], personas) or 1
```

(importar `habitaciones_necesarias` y `recursos_disponibles_en_rango` desde `.nucleo`).

En `confirmacion.py`, `_asignar_cupo_hospedaje`: después de calcular `libres`, reemplazar `elegir_recursos(libres, personas=personas, cantidad=1)` por:

```python
    cantidad = habitaciones_necesarias([cap for _, cap in libres], personas)
    elegidos = elegir_recursos(libres, personas=personas, cantidad=cantidad) if cantidad else None
```

(importar `habitaciones_necesarias`; el resto —el `SinCupoError` cuando `elegidos` es `None`— queda igual).

En `serializers.py::_derivar_de_paquete`, cambiar la condición de la habitación:

```python
                if habitaciones.exists() and personas[clave] > sum(r.capacidad_maxima for r in habitaciones):
                    raise serializers.ValidationError({
                        'personas_por_servicio': f'Las habitaciones de "{ps.servicio.nombre}" no alcanzan para {personas[clave]} personas.',
                    })
```

- [ ] **Step 4: Verificar que pasan**

Run: `$PY manage.py test apps.bookings apps.payments`
Expected: PASS. Si alguna prueba existente asumía "no cabe en una habitación = rechazo", revisarla: con varias habitaciones libres ahora se acepta; ajustar la aserción a "no alcanzan juntas".

---

### Task 7: API y compatibilidad de lectura

**Files:**
- Modify: `backend/apps/fleet/catalogo.py` (revisar los usos de `dia_estancia`), `backend/apps/fleet/serializers.py`
- Test: `backend/apps/fleet/tests_paquetes_api.py`

**Interfaces:**
- Produces: el catálogo público de un paquete devuelve `salidas` en cada servicio asociado.

- [ ] **Step 1: Escribir la prueba que falla** en `tests_paquetes_api.py`, siguiendo la forma de las pruebas de ese archivo: crear un paquete con una actividad `dia_estancia=2, salidas=4`, pedir el catálogo y comprobar que `servicios_asociados[...]['salidas'] == 4` y que un servicio normal devuelve `1`.
- [ ] **Step 2: Verificar que falla.** Run: `$PY manage.py test apps.fleet.tests_paquetes_api` — Expected: FAIL (`KeyError: 'salidas'`) si Task 2 no agregó el campo al serializador; si ya pasa, la prueba queda como respaldo.
- [ ] **Step 3: Implementar.** Revisar `catalogo.py` (`grep -n dia_estancia apps/fleet/catalogo.py`) y agregar `salidas` donde se construyan los diccionarios de componentes del catálogo.
- [ ] **Step 4: Verificar.** Run: `$PY manage.py test apps.fleet` — Expected: PASS.

---

### Task 8: Compuerta de backend y documentación

**Files:**
- Modify: `backend/CLAUDE.md` (secciones "Cupo diario" y "Cupo multidimensional, hospedaje y paquetes turísticos")

- [ ] **Step 1: Documentar.** En `backend/CLAUDE.md`, sección "Cupo multidimensional…", agregar:

```markdown
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
```

- [ ] **Step 2: Suite completa en SQLite.** Run: `$PY manage.py test apps config` — Expected: solo falla `apps.finance.tests.PanelPorPeriodoTests.test_una_etiqueta_y_un_dato_por_cada_dia_del_periodo` si se corre un día 1 del mes (defecto de esa prueba, no de este cambio).
- [ ] **Step 3: Suite completa en Postgres.** Con Docker abierto: `docker start psd-pg`, y `DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 $PY manage.py test apps config --noinput`. Expected: PASS, incluida `test_guardarrail_toda_tabla_con_empresa_tiene_politica` (que confirma la política RLS de `bookings_reservasalida`) y las pruebas de salidas bajo el rol sin `BYPASSRLS`. Si Docker no está disponible, **decirlo** y no cerrar el gate.
- [ ] **Step 4: Concurrencia (solo Postgres).** Agregar a `backend/apps/bookings/tests_concurrencia.py`, siguiendo el patrón de pruebas de esa clase, una prueba con dos hilos que confirman a la vez dos paquetes con salidas solapadas sobre una flota de una sola panga; esperado: exactamente uno queda confirmado y el otro cancelado con reembolso. Marcar `@skipUnless(connection.vendor == 'postgresql', ...)` como las demás.

---

### Task 9: Frontend — **bloqueada hasta que termine la Task 6 del precio por persona (que conserva los selectores por servicio)**

El frontend replica el calendario con vectores de prueba compartidos. Alcance previsto (se entrega como prompt a un agente, después de la aprobación del dueño):

- `frontend/src/lib/calendario-paquete.ts`: `salidas` en el componente, `fechasDeComponente(inicio, diaEstancia, salidas)` y `fechasDeActividad`, con los mismos vectores que `tests_calendario_paquete.py` (inicio 2026-11-14, día 2, 4 salidas → 15 a 18 de noviembre).
- `frontend/src/lib/api.ts`: el tipo del servicio asociado gana `salidas: number`.
- `grupo-servicio.tsx`: la tarjeta de la actividad muestra los días de mar ("Salidas: 15 al 18 de noviembre") en vez de un solo día.
- Sin cambios al selector de fecha ni a la disponibilidad (fuera de alcance).
- Aprobación previa del dueño: la explicación del texto de la tarjeta antes de escribir código.

### Task 10: Catálogo de La Ventana Travel — **bloqueada por respuestas del cliente y por las Tasks 1-8 y la del precio por persona**

**Files:**
- Modify: `backend/apps/fleet/management/commands/seed_catalogo_real.py`
- Test: `backend/apps/fleet/tests_seed_catalogo_real.py` (nuevo)

Cargar los dos paquetes de La Ventana Travel con `precio_por_persona=True`:
- **A:** "5 noches con mar" — hospedaje `noches=5`, actividad `dia_estancia=2, salidas=4`, traslado de aeropuerto; **$45,000 MXN / $2,500 USD** por persona.
- **B:** "7 noches con mar" — hospedaje `noches=7`, actividad `dia_estancia=2, salidas=6`, traslado; **$52,500 MXN / $2,916.67 USD** por persona (tipo de cambio de 18 pesos por dólar, sin redondear centavos, decisión del dueño).
- `personas_incluidas`: la actividad el tope de la embarcación (la pesca con mosca admite 3); el hospedaje la capacidad total de sus habitaciones (4 habitaciones demo = 10); el traslado 14. El cliente elige cuántas personas son y hospedaje y traslado pueden llevar menos.
- `permite_anticipo=False` hasta que el cliente responda lo del anticipo.
- **Pendiente del cliente (★ en `docs/preguntas-cliente-la-ventana-travel.md`): qué actividad se hace cada día de mar.** Hasta que responda, el seed usa `pesca-con-mosca` como placeholder en una constante `ACTIVIDAD_DE_MAR` al inicio del archivo, con un comentario que lo diga.
- Prueba: el seed es idempotente (correrlo dos veces no duplica paquetes ni componentes) y `paquete.validar_configuracion()` no lanza.
