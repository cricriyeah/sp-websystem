# Agenda operativa — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una pantalla donde se reparten los viajes ya vendidos —asignar panga y capitán sin entrar a cada reserva— y donde lo que está mal se ve de lejos.

**Architecture:** Un modelo proxy `bookings.Agenda` sobre `Reserva` con `list_editable`, el mismo patrón que ya usa `CheckoutAbandonado`. Las reglas viven en el modelo, no en el admin: la transición `pagada` ↔ `asignada` en `Reserva.save()` y la regla de una salida por panga y por capitán al día en `Reserva.clean()`, para que valgan igual desde el admin de Reservas, el shell o cualquier pantalla futura. Los dos modos de uso son dos opciones de un mismo filtro.

**Tech Stack:** Django 6 + django-unfold (admin), Postgres en producción y CI, sqlite en local.

**Spec:** `docs/superpowers/specs/2026-08-19-agenda-operativa-design.md`

## Global Constraints

- **Una panga hace un solo viaje por día, y un capitán también.** Salidas de 5 a 7am, viaje de 6 a 7 horas: escalonar no existe.
- **Poner la panga basta para pasar de `pagada` a `asignada`. El capitán NO se exige** — se marca en rojo, no se bloquea.
- **La transición de estado solo ocurre entre `pagada` y `asignada`.** `completada` y `cancelada` nunca se mueven.
- **Los strings de Python del repo van sin acentos** (ASCII). Comentarios y docstrings en español, explicando el *porqué*, siguiendo el estilo del archivo que se toca.
- **`ESTADOS_QUE_OCUPAN_CUPO`** (`pagada`, `asignada`, `completada`) es lo que cuenta para la regla de una salida por día. Una cancelada suelta su panga.
- **El sitio no se ha lanzado**: todo lo que hay en producción son pruebas. No hay migración de datos ni auditoría de filas viejas.
- Tests: `venv/Scripts/python.exe manage.py test` desde `backend/`.
- Commits en español, en imperativo, con prefijo `feat:` / `fix:` / `test:` / `docs:`.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/bookings/models.py` | Modificar | Proxy `Agenda`; transición de estado en `Reserva.save()`; regla de una salida por día en `Reserva.clean()`. Todas las reglas del negocio en un solo lugar. |
| `backend/apps/bookings/admin.py` | Modificar | `AgendaAdmin` con `list_editable`, el filtro `Cuando` y las columnas de aviso. Solo presentación: no decide reglas. |
| `backend/apps/bookings/management/commands/setup_roles.py` | Modificar | Permisos de la vendedora sobre `bookings.agenda` y sobre `fleet.embarcacionnodisponible` (hueco heredado de la pieza del cupo). |
| `backend/apps/bookings/tests.py` | Modificar | Estado, regla de una salida por día, avisos. |
| `backend/apps/bookings/tests_agenda.py` | Crear | Los tests de la pantalla: filtro, columnas, permisos. `tests.py` ya pasa de 900 líneas y esto es una pantalla nueva con su propia superficie. |
| `backend/CLAUDE.md` | Modificar | Corregir la nota que dice que la doble asignación no se valida, y documentar la agenda. |
| `docs/contexto-negocio.md` | Modificar | La regla de una salida por panga y por capitán al día. |

<!-- arch-critic: revisión adversarial hecha en línea (este harness no despacha subagentes sin petición explícita del usuario). Hallazgos aplicados antes de escribir las tareas: (1) la transición de estado va en `save()` y la validación en `clean()` — separarlas importa, porque `save()` corre siempre y `clean()` solo cuando alguien valida; poner la transición en `clean()` haría que un `save()` directo dejara el estado inconsistente; (2) la regla de una salida por día se consulta contra la base, así que necesita `excluir_pk` igual que el cupo, o editar una reserva ya asignada chocaría consigo misma; (3) los tests de la pantalla van a archivo aparte: `tests.py` ya está en ~950 líneas y mezclar la superficie del admin con las reglas del modelo hace ambas más difíciles de leer; (4) el filtro `Cuando` devuelve un queryset y el `ordering` del proxy hace el resto — no hace falta lógica de orden en el filtro. -->

---

## Task 1: El proxy `Agenda`

**Files:**
- Modify: `backend/apps/bookings/models.py` (al final del archivo, después de `CheckoutAbandonado`)
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `Reserva`, `Reserva.Estado`.
- Produces: `Agenda` (proxy de `Reserva`), `Agenda.ESTADOS_EN_AGENDA = [Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA]`, `Agenda.por_repartir()` que devuelve el queryset de esos dos estados.

- [ ] **Step 1: Escribe el test que falla**

En `backend/apps/bookings/tests.py`, al final:

```python
class AgendaListaTests(TestCase):
    """La agenda reparte lo vendido: solo lo que todavia se puede repartir."""

    def setUp(self):
        crear_flota()
        self.fecha = date.today() + timedelta(days=3)

    def test_lista_las_pagadas_y_las_asignadas(self):
        pagada = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        asignada = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        asignada.embarcacion = Embarcacion.objects.first()
        asignada.save()

        en_agenda = set(Agenda.por_repartir().values_list('pk', flat=True))

        self.assertEqual(en_agenda, {pagada.pk, asignada.pk})

    def test_no_lista_las_que_no_se_reparten(self):
        """Una cancelada no se reparte, una completada ya salio, y una
        pendiente_pago no es una reserva todavia."""
        crear_reserva(fecha=self.fecha, estado=Reserva.Estado.COMPLETADA)
        Reserva.objects.create(**datos_reserva(
            fecha=self.fecha, estado=Reserva.Estado.CANCELADA))
        Reserva.objects.create(**datos_reserva(
            fecha=self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO))

        self.assertEqual(Agenda.por_repartir().count(), 0)

    def test_ordena_lo_que_sale_primero_primero(self):
        """Al reves que el listado de Reservas, que es un historial."""
        tarde = crear_reserva(fecha=self.fecha + timedelta(days=1))
        temprano = crear_reserva(fecha=self.fecha)

        self.assertEqual(
            list(Agenda.por_repartir().values_list('pk', flat=True)),
            [temprano.pk, tarde.pk],
        )
```

Agrega `Agenda` al import de `.models` en la cabecera del archivo.

- [ ] **Step 2: Corre el test y verifica que falla**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests.AgendaListaTests -v 2`
Esperado: FAIL — `ImportError: cannot import name 'Agenda'`.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, al final del archivo:

```python
class Agenda(Reserva):
    """Proxy de `Reserva` para repartir los viajes ya vendidos.

    Es la pantalla donde se decide que panga y que capitan le toca a cada viaje.
    Proxy y no modelo nuevo a proposito, igual que `CheckoutAbandonado`: es la
    misma fila vista con otro filtro y otras columnas. Si un viaje se cancela,
    desaparece de aqui solo.

    Lista solo `pagada` y `asignada`, que son los dos estados que todavia se
    pueden repartir. Una cancelada no se reparte, una completada ya salio, y una
    `pendiente_pago` no es una reserva todavia — esa vive en la pantalla de
    checkouts abandonados.
    """

    ESTADOS_EN_AGENDA = [Reserva.Estado.PAGADA, Reserva.Estado.ASIGNADA]

    class Meta:
        proxy = True
        # Ascendente, al reves que el listado de Reservas: eso es un historial y
        # enseña lo mas reciente arriba; esto es una agenda y lo que sale primero
        # va primero. De paso, los viajes atrasados quedan hasta arriba solos por
        # ser los mas viejos: lo que esta mal aparece sin que nadie lo ordene.
        ordering = ['fecha', 'hora']
        verbose_name = 'agenda'
        verbose_name_plural = 'agenda'

    @classmethod
    def por_repartir(cls):
        return cls.objects.filter(estado__in=cls.ESTADOS_EN_AGENDA)
```

- [ ] **Step 4: Genera la migración**

Run: `cd backend && venv/Scripts/python.exe manage.py makemigrations bookings -n agenda`
Esperado: una migración con `CreateModel` de `Agenda` marcada `proxy=True` (`options={'proxy': True, ...}`), sin tocar tablas. Un proxy necesita migración porque Django le crea su propio `ContentType` y sus permisos.

- [ ] **Step 5: Corre los tests y verifica que pasan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests.AgendaListaTests -v 2`
Esperado: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/migrations/ backend/apps/bookings/tests.py
git commit -m "feat(agenda): proxy Agenda con los viajes que faltan por repartir"
```

---

## Task 2: Poner la panga asigna el viaje

**Files:**
- Modify: `backend/apps/bookings/models.py:465-475` (`Reserva.save`)
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `Reserva.Estado`.
- Produces: `Reserva.save()` deriva el estado antes de guardar. Sin función pública nueva.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/bookings/tests.py`, al final:

```python
class TransicionDeAsignacionTests(TestCase):
    """Poner la panga da el viaje por asignado; quitarla lo regresa.

    El capitan no entra en esto a proposito: se acordo que poner la panga baste,
    sabiendo que un viaje puede llegar a la salida sin capitan. La compensacion
    es el aviso en rojo de la agenda, no una validacion que frene el trabajo.
    """

    def setUp(self):
        crear_flota()
        self.panga = Embarcacion.objects.first()
        self.capitan = Capitan.objects.create(nombre='Juan Perez', telefono='+5216121234567')
        self.fecha = date.today() + timedelta(days=3)

    def test_ponerle_panga_a_una_pagada_la_deja_asignada(self):
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)

    def test_quitarle_la_panga_a_una_asignada_la_regresa_a_pagada(self):
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)
        reserva.embarcacion = self.panga
        reserva.save()

        reserva.embarcacion = None
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_el_capitan_solo_no_asigna_el_viaje(self):
        """Sin panga no hay viaje repartido, por mucho capitan que tenga."""
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.capitan = self.capitan
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PAGADA)

    def test_una_completada_no_se_mueve(self):
        """Estados finales: los decide una persona, no un efecto secundario."""
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.COMPLETADA)

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.COMPLETADA)

    def test_una_cancelada_no_se_mueve(self):
        reserva = Reserva.objects.create(**datos_reserva(
            fecha=self.fecha, estado=Reserva.Estado.CANCELADA))

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.CANCELADA)

    def test_una_pendiente_de_pago_no_se_asigna_por_ponerle_panga(self):
        """Un checkout sin pagar no es un viaje que repartir."""
        reserva = Reserva.objects.create(**datos_reserva(
            fecha=self.fecha, estado=Reserva.Estado.PENDIENTE_PAGO))

        reserva.embarcacion = self.panga
        reserva.save()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.PENDIENTE_PAGO)
```

Agrega `Capitan` al import de `apps.fleet.models` en la cabecera del archivo.

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests.TransicionDeAsignacionTests -v 2`
Esperado: FAIL en los dos primeros — el estado se queda en `pagada` y en `asignada` respectivamente. Los otros cuatro pasan ya (nada los mueve todavía); tienen que seguir pasando al final.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, dentro de `Reserva.save()`, como primera cosa que hace el método:

```python
    def save(self, *args, **kwargs):
        self._derivar_estado_de_asignacion()

        # Si la llamada trae `update_fields` y toca la embarcacion, `estado` tiene
        # que ir en esa lista o el UPDATE no lo escribe: la fila quedaria diciendo
        # `pagada` con una panga puesta. El listado editable del admin guarda asi.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'embarcacion' in update_fields:
            kwargs['update_fields'] = [*update_fields, 'estado']

        # Sella cuando se atribuyo la venta, venga de donde venga (link ?ref= al
        # crear la reserva, panel de la vendedora, shell). Va en save() y no en la
        # vista porque hay varias entradas y todas deben dejar la misma constancia.
        if self.vendedora_id != getattr(self, '_vendedora_original', None):
            self.vendedora_asignada_en = timezone.now() if self.vendedora_id else None
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'vendedora' in update_fields:
                kwargs['update_fields'] = [*update_fields, 'vendedora_asignada_en']
        super().save(*args, **kwargs)
        self._vendedora_original = self.vendedora_id

    def _derivar_estado_de_asignacion(self):
        """Poner la panga da el viaje por asignado; quitarla lo regresa a pagada.

        Va en save() y no en el admin para que valga igual desde el shell o desde
        cualquier pantalla futura, y va en save() y no en clean() porque clean()
        solo corre cuando alguien valida: un save() directo dejaria el estado
        diciendo una cosa y la panga otra.

        Solo entre esos dos estados. `completada` y `cancelada` son finales y los
        decide una persona, no el efecto secundario de editar un campo; y una
        `pendiente_pago` no es un viaje que repartir.

        El capitan no cuenta: se acordo que poner la panga baste, sabiendo que un
        viaje puede llegar a la salida sin capitan. Eso se avisa en rojo en la
        agenda, no se frena aqui.
        """
        if self.estado == self.Estado.PAGADA and self.embarcacion_id:
            self.estado = self.Estado.ASIGNADA
        elif self.estado == self.Estado.ASIGNADA and not self.embarcacion_id:
            self.estado = self.Estado.PAGADA
```

- [ ] **Step 4: Escribe el test de `update_fields`**

```python
    def test_guardar_solo_la_embarcacion_tambien_mueve_el_estado(self):
        """El listado editable del admin puede guardar con update_fields; si
        `estado` no va en esa lista, el UPDATE no lo escribe y la fila queda
        diciendo `pagada` con una panga puesta."""
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        reserva.embarcacion = self.panga
        reserva.save(update_fields=['embarcacion'])

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, Reserva.Estado.ASIGNADA)
```

- [ ] **Step 5: Corre los tests y verifica que pasan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings -v 1`
Esperado: PASS. Toda la suite de `bookings`, no solo la clase nueva: `save()` lo usa todo el sistema.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/tests.py
git commit -m "feat(agenda): poner la panga asigna el viaje, quitarla lo regresa"
```

---

## Task 3: Una salida por panga y por capitán al día

**Files:**
- Modify: `backend/apps/bookings/models.py:477-495` (`Reserva.clean` y sus ayudantes)
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `ESTADOS_QUE_OCUPAN_CUPO`.
- Produces: `Reserva._validar_una_salida_por_dia()`, llamada desde `Reserva.clean()`. Levanta `ValidationError` con las claves `embarcacion` o `capitan`.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/bookings/tests.py`, al final:

```python
class UnaSalidaPorDiaTests(TestCase):
    """Una panga hace un solo viaje al dia, y un capitan tambien.

    Las salidas son de 5 a 7am y el viaje dura de 6 a 7 horas, asi que escalonar
    dos salidas con la misma panga no existe. El repo decia lo contrario hasta
    esta tarea (ver backend/CLAUDE.md).
    """

    def setUp(self):
        crear_flota()
        self.panga = Embarcacion.objects.first()
        self.capitan = Capitan.objects.create(nombre='Juan Perez', telefono='+5216121234567')
        self.fecha = date.today() + timedelta(days=3)

    def test_la_misma_panga_dos_veces_el_mismo_dia_se_rechaza(self):
        crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      embarcacion=self.panga)

        otra = Reserva(**datos_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        with self.assertRaises(ValidationError) as ctx:
            otra.full_clean()

        self.assertIn('embarcacion', ctx.exception.message_dict)
        self.assertIn('una sola salida por dia', str(ctx.exception))

    def test_el_mismo_capitan_dos_veces_el_mismo_dia_se_rechaza(self):
        crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      capitan=self.capitan)

        otra = Reserva(**datos_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.capitan = self.capitan
        with self.assertRaises(ValidationError) as ctx:
            otra.full_clean()

        self.assertIn('capitan', ctx.exception.message_dict)

    def test_la_misma_panga_en_dias_distintos_se_acepta(self):
        crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                      embarcacion=self.panga)

        otra = Reserva(**datos_reserva(fecha=self.fecha + timedelta(days=1),
                                       estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        otra.full_clean()

    def test_una_cancelada_suelta_su_panga(self):
        cancelada = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                                  embarcacion=self.panga)
        cancelada.estado = Reserva.Estado.CANCELADA
        cancelada.save()

        otra = Reserva(**datos_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA))
        otra.embarcacion = self.panga
        otra.full_clean()

    def test_editar_una_reserva_ya_asignada_no_choca_consigo_misma(self):
        reserva = crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA,
                                embarcacion=self.panga)

        reserva.nombre_cliente = 'Ana Ruiz Corregido'
        reserva.full_clean()

    def test_una_reserva_sin_panga_no_choca_con_otra_sin_panga(self):
        """Dos viajes sin repartir el mismo dia son lo normal, no un choque."""
        crear_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)

        Reserva(**datos_reserva(fecha=self.fecha, estado=Reserva.Estado.PAGADA)).full_clean()
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests.UnaSalidaPorDiaTests -v 2`
Esperado: FAIL en los dos primeros — hoy la doble asignación se acepta.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, agrega la llamada en `clean()` justo después de `self._validar_capacidad_embarcacion()`:

```python
        self._validar_capacidad_embarcacion()
        self._validar_una_salida_por_dia()
        self._validar_cambio_de_fecha()
```

y el método, junto a los otros ayudantes de validación:

```python
    def _validar_una_salida_por_dia(self):
        """Una panga hace un solo viaje al dia, y un capitan tambien.

        Las salidas son de 5 a 7am y el viaje dura de 6 a 7 horas: no hay forma
        de escalonar dos salidas con la misma panga. `backend/CLAUDE.md` decia lo
        contrario ("la doble asignacion no se valida a proposito") y esa nota se
        corrige junto con este cambio.

        Cuentan los estados que ya ocupan cupo: una reserva cancelada suelta su
        panga y su capitan para que otro viaje del dia los use.

        La regla ya estaba medio vigente sin que nadie la escribiera — el motor de
        cupo exige que haya al menos tantas pangas a flote como viajes, o sea, ya
        vende como si cada panga hiciera una sola salida diaria. Esto la hace
        cumplir del otro lado, al repartir.
        """
        del_dia = Reserva.objects.filter(fecha=self.fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO)
        if self.pk:
            del_dia = del_dia.exclude(pk=self.pk)

        if self.embarcacion_id and del_dia.filter(embarcacion_id=self.embarcacion_id).exists():
            raise ValidationError({
                'embarcacion': f'{self.embarcacion.nombre} ya tiene un viaje el {self.fecha}. '
                               f'Una panga hace una sola salida por dia.',
            })

        if self.capitan_id and del_dia.filter(capitan_id=self.capitan_id).exists():
            raise ValidationError({
                'capitan': f'{self.capitan.nombre} ya tiene un viaje el {self.fecha}. '
                           f'Un capitan hace una sola salida por dia.',
            })
```

- [ ] **Step 4: Corre toda la suite**

Run: `cd backend && venv/Scripts/python.exe manage.py test -v 1`
Esperado: PASS. Si algún test viejo falla por asignar la misma panga dos veces el mismo día, ese test codificaba la regla vieja: actualízalo, no aflojes la validación.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/tests.py
git commit -m "feat(agenda): una panga y un capitan hacen una sola salida por dia"
```

---

## Task 4: La pantalla

**Files:**
- Modify: `backend/apps/bookings/admin.py` (al final, después de `CheckoutAbandonadoAdmin`)
- Create: `backend/apps/bookings/tests_agenda.py`

**Interfaces:**
- Consumes: `Agenda`, `Agenda.ESTADOS_EN_AGENDA`, `Agenda.por_repartir()` (Task 1).
- Produces: `AgendaAdmin` registrado sobre `Agenda`; `CuandoFilter(admin.SimpleListFilter)` con `parameter_name = 'cuando'` y valores `manana` / `semana`.

- [ ] **Step 1: Escribe los tests que fallan**

Crea `backend/apps/bookings/tests_agenda.py`:

```python
"""Pruebas de la pantalla de agenda.

Aparte de `tests.py` porque eso ya cubre las reglas del modelo y pasa de 900
lineas; esto es la superficie del admin: que se liste, que se filtre y que se
vea lo que esta mal.
"""
from datetime import date, time, timedelta

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.fleet.models import Capitan, Embarcacion
from apps.testing import crear_flota

from .models import Reserva


def datos(**overrides):
    base = {
        'fecha': date.today() + timedelta(days=3),
        'hora': time(6, 0),
        'numero_personas': 2,
        'nombre_cliente': 'Ana Ruiz',
        'telefono_cliente': '+5216121234567',
        'correo_cliente': 'ana@example.com',
        'canal_origen': Reserva.CanalOrigen.WEB,
        'deslinde_aceptado': True,
        'deslinde_nombre': 'Ana Ruiz',
        'estado': Reserva.Estado.PAGADA,
    }
    base.update(overrides)
    return base


def viaje(**overrides):
    """Se guarda sin full_clean para poder sembrar fechas pasadas: la regla de
    las 48 horas no deja reprogramar hacia atras, y aqui hace falta un atrasado."""
    crear_flota()
    return Reserva.objects.create(**datos(**overrides))


class AgendaAdminTests(TestCase):
    def setUp(self):
        crear_flota()
        self.url = reverse('admin:bookings_agenda_changelist')
        self.client.force_login(
            User.objects.create_superuser('jefe', 'jefe@example.com', 'x')
        )

    def _filas(self, **params):
        respuesta = self.client.get(self.url, params)
        self.assertEqual(respuesta.status_code, 200)
        return {r.pk for r in respuesta.context['cl'].result_list}

    def test_el_modo_manana_trae_solo_manana(self):
        manana = viaje(fecha=date.today() + timedelta(days=1))
        viaje(fecha=date.today() + timedelta(days=2))

        self.assertEqual(self._filas(cuando='manana'), {manana.pk})

    def test_el_modo_semana_trae_los_proximos_siete_dias(self):
        dentro = viaje(fecha=date.today() + timedelta(days=6))
        viaje(fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(cuando='semana'), {dentro.pk})

    def test_el_modo_semana_trae_los_atrasados_sin_repartir(self):
        """Un viaje cobrado que ya paso y nadie repartio es un error que hay que
        ver. Esconderlo no lo arregla."""
        atrasado = viaje(fecha=date.today() - timedelta(days=2))

        self.assertIn(atrasado.pk, self._filas(cuando='semana'))

    def test_el_modo_semana_no_trae_los_atrasados_ya_repartidos(self):
        """Ese se repartio, aunque haya pasado."""
        repartido = viaje(fecha=date.today() - timedelta(days=2),
                          estado=Reserva.Estado.ASIGNADA,
                          embarcacion=Embarcacion.objects.first())

        self.assertNotIn(repartido.pk, self._filas(cuando='semana'))

    def test_sin_filtro_abre_en_la_semana(self):
        dentro = viaje(fecha=date.today() + timedelta(days=2))
        viaje(fecha=date.today() + timedelta(days=30))

        self.assertEqual(self._filas(), {dentro.pk})

    def test_avisa_de_un_viaje_asignado_sin_capitan(self):
        viaje(fecha=date.today() + timedelta(days=2),
              estado=Reserva.Estado.ASIGNADA,
              embarcacion=Embarcacion.objects.first())

        self.assertContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_no_avisa_cuando_el_viaje_tiene_capitan(self):
        viaje(fecha=date.today() + timedelta(days=2),
              estado=Reserva.Estado.ASIGNADA,
              embarcacion=Embarcacion.objects.first(),
              capitan=Capitan.objects.create(nombre='Juan Perez', telefono='+5216121234567'))

        self.assertNotContains(self.client.get(self.url), 'SIN CAPITAN')

    def test_avisa_de_un_viaje_atrasado(self):
        viaje(fecha=date.today() - timedelta(days=2))

        self.assertContains(self.client.get(self.url), 'ATRASADO')

    def test_un_viaje_futuro_sin_panga_no_se_marca(self):
        """No es un error: es el trabajo pendiente, y es a lo que se viene aqui.
        Marcarlo volveria roja la agenda entera y el rojo dejaria de significar algo."""
        viaje(fecha=date.today() + timedelta(days=2))

        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, 'ATRASADO')
        self.assertNotContains(respuesta, 'SIN CAPITAN')

    def test_la_panga_y_el_capitan_se_editan_en_el_listado(self):
        """El punto entero de la pantalla: repartir sin entrar a cada reserva."""
        viaje(fecha=date.today() + timedelta(days=2))

        formset = self.client.get(self.url).context['cl'].formset

        self.assertIn('embarcacion', formset.forms[0].fields)
        self.assertIn('capitan', formset.forms[0].fields)


class AgendaPermisosTests(TestCase):
    def setUp(self):
        crear_flota()
        call_command('setup_roles')
        self.vendedora = User.objects.create_user(
            'maria', 'maria@example.com', 'x', is_staff=True)
        self.vendedora.groups.add(Group.objects.get(name='Vendedora'))
        self.client.force_login(self.vendedora)

    def test_la_vendedora_ve_la_agenda(self):
        respuesta = self.client.get(reverse('admin:bookings_agenda_changelist'))
        self.assertEqual(respuesta.status_code, 200)

    def test_la_vendedora_no_puede_agregar_desde_la_agenda(self):
        """Una reserva se crea vendiendo, no se inventa desde aqui."""
        respuesta = self.client.get(reverse('admin:bookings_agenda_add'))
        self.assertEqual(respuesta.status_code, 403)

    def test_la_vendedora_puede_marcar_una_panga_fuera_de_servicio(self):
        """Hueco heredado de la pieza del cupo: el modelo se creo sin darle el
        permiso, y marcar que la Lupita esta en mantenimiento es trabajo suyo."""
        respuesta = self.client.get(
            reverse('admin:fleet_embarcacionnodisponible_add'))
        self.assertEqual(respuesta.status_code, 200)
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests_agenda -v 1`
Esperado: FAIL — `NoReverseMatch: 'bookings_agenda_changelist' is not a valid view function or pattern name`.

- [ ] **Step 3: Implementa el filtro y el admin**

En `backend/apps/bookings/admin.py`, agrega `Agenda` al import de `.models` y al final del archivo:

```python
class CuandoFilter(admin.SimpleListFilter):
    """Los dos modos de usar la agenda, que son dos rangos de fechas y nada mas.

    "Cerrar el dia" y "repartir la semana" no son dos pantallas: es la misma
    tabla mirando distintos dias.
    """

    title = 'cuando'
    parameter_name = 'cuando'

    def lookups(self, request, model_admin):
        return [
            ('manana', 'Manana'),
            ('semana', 'Proximos 7 dias'),
        ]

    def queryset(self, request, queryset):
        hoy = timezone.localdate()

        if self.value() == 'manana':
            # Cerrar el dia se hace la tarde anterior: si la salida es a las 6am,
            # a esa hora ya nadie esta asignando pangas.
            manana = hoy + timedelta(days=1)
            return queryset.filter(fecha=manana)

        # Por defecto, repartir la semana. Los atrasados sin repartir entran a
        # proposito: un viaje cobrado que ya paso y nadie asigno es un error que
        # hay que ver. Los atrasados que si se repartieron no, esos ya se
        # resolvieron aunque hayan pasado.
        return queryset.filter(
            models.Q(fecha__range=(hoy, hoy + timedelta(days=7)))
            | models.Q(fecha__lt=hoy, estado=Reserva.Estado.PAGADA)
        )


@admin.register(Agenda)
class AgendaAdmin(ModelAdmin):
    """Repartir los viajes ya vendidos: que panga y que capitan le toca a cada uno.

    Se edita en el propio listado, que es el punto entero de la pantalla: con
    ocho o diez viajes en un fin de semana, entrar a cada reserva son treinta
    clics para lo que en la cabeza es una sola decision.
    """

    list_display = [
        'fecha', 'hora', 'nombre_cliente', 'numero_personas',
        'embarcacion', 'capitan', 'aviso',
    ]
    list_editable = ['embarcacion', 'capitan']
    list_display_links = ['nombre_cliente']
    list_filter = [CuandoFilter]
    search_fields = ['nombre_cliente', 'telefono_cliente']
    autocomplete_fields = ['embarcacion', 'capitan']
    list_per_page = 50

    def get_queryset(self, request):
        # `embarcacion` y `capitan` salen en el listado: sin esto es una consulta
        # por fila.
        return Agenda.por_repartir().select_related('embarcacion', 'capitan')

    def has_add_permission(self, request):
        # Una reserva se crea vendiendo, no se inventa desde aqui.
        return False

    def has_delete_permission(self, request, obj=None):
        # Una reserva se cancela, no se borra (ver docs/contexto-negocio.md).
        return False

    @admin.display(description='Aviso')
    def aviso(self, obj):
        """Lo que esta mal, en rojo y sin ambiguedad.

        Un viaje `pagada` sin panga y con fecha futura NO se marca: eso no es un
        error, es el trabajo pendiente y es justo a lo que se viene a esta
        pantalla. Marcarlo volveria roja la agenda entera el primer dia y el rojo
        dejaria de significar algo.
        """
        if obj.estado == Reserva.Estado.PAGADA and obj.fecha < timezone.localdate():
            return format_html(
                '<span style="color:#dc2626;font-weight:600">ATRASADO</span>'
            )
        if obj.estado == Reserva.Estado.ASIGNADA and not obj.capitan_id:
            return format_html(
                '<span style="color:#dc2626;font-weight:600">SIN CAPITAN</span>'
            )
        return '—'
```

Agrega a la cabecera de `admin.py`:

```python
from datetime import timedelta

from django.db import models
```

- [ ] **Step 4: Corre los tests de la pantalla**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests_agenda.AgendaAdminTests -v 2`
Esperado: PASS. `AgendaPermisosTests` sigue fallando: los permisos son la Task 5.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/admin.py backend/apps/bookings/tests_agenda.py
git commit -m "feat(agenda): pantalla para repartir panga y capitan desde el listado"
```

---

## Task 5: Los permisos de la vendedora

**Files:**
- Modify: `backend/apps/bookings/management/commands/setup_roles.py:20-35`
- Test: `backend/apps/bookings/tests_agenda.py` (la clase `AgendaPermisosTests` de la Task 4)

**Interfaces:**
- Consumes: `Agenda` (Task 1) — su `ContentType` existe gracias a la migración del proxy.
- Produces: el grupo `Vendedora` con permisos `bookings.change_agenda`, `bookings.view_agenda` y los cuatro de `fleet.embarcacionnodisponible`.

- [ ] **Step 1: Corre los tests que ya fallan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests_agenda.AgendaPermisosTests -v 2`
Esperado: FAIL — la vendedora recibe 403 en la agenda y en embarcaciones no disponibles.

- [ ] **Step 2: Implementa**

En `backend/apps/bookings/management/commands/setup_roles.py`, dentro de la lista `permisos`:

```python
            # Reservas: vista operativa completa. Sin delete (se cancela, no se borra).
            ('bookings', 'reserva', ['add', 'change', 'view']),
            # Agenda: repartir panga y capitan de los viajes ya vendidos. Es un
            # proxy de Reserva y por eso tiene permisos propios. Sin add ni
            # delete: una reserva se crea vendiendo y se cancela, no se inventa
            # ni se borra desde la agenda.
            ('bookings', 'agenda', ['change', 'view']),
```

y en el bloque de `fleet`:

```python
            # Catalogo de flota: solo consulta, para asignar embarcacion/capitan.
            ('fleet', 'embarcacion', ['view']),
            ('fleet', 'capitan', ['view']),
            # Que panga no sale un dia (mantenimiento, motor). Es trabajo diario
            # suyo, no de los jefes. Con delete a proposito: si marco una fuera
            # por error, o el motor se arreglo antes, tiene que poder deshacerlo
            # — no es un registro historico, es el estado de un dia.
            ('fleet', 'embarcacionnodisponible', ['add', 'change', 'delete', 'view']),
```

Cuidado con el nombre: el `model` del `ContentType` es el nombre de la clase en
minúsculas y **sin acentos** — `embarcacionnodisponible`. Con acento revienta con
un `ContentType.DoesNotExist` que no dice de dónde viene.

- [ ] **Step 3: Corre los tests y verifica que pasan**

Run: `cd backend && venv/Scripts/python.exe manage.py test apps.bookings.tests_agenda -v 1`
Esperado: PASS (las dos clases).

- [ ] **Step 4: Corre toda la suite**

Run: `cd backend && venv/Scripts/python.exe manage.py test -v 1`
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/management/commands/setup_roles.py
git commit -m "feat(agenda): permisos de la vendedora sobre la agenda y las pangas fuera de servicio"
```

---

## Task 6: La documentación deja de mentir

**Files:**
- Modify: `backend/CLAUDE.md:111-113`
- Modify: `docs/contexto-negocio.md` (sección Embarcaciones)

- [ ] **Step 1: Corrige `backend/CLAUDE.md`**

Reemplaza la nota falsa:

```markdown
- **La doble asignacion de panga/capitan no se valida a proposito**: la vendedora puede
  querer sacar dos viajes con la misma panga escalonando la salida. Es criterio suyo,
  no del sistema.
```

por:

```markdown
- **Una panga hace una sola salida por dia, y un capitan tambien.** Se valida en
  `Reserva._validar_una_salida_por_dia()`, llamada desde `clean()`, asi que aplica
  igual desde la agenda, desde el admin de Reservas y desde el shell. Cuentan los
  estados de `ESTADOS_QUE_OCUPAN_CUPO`: una cancelada suelta su panga. Las salidas
  son de 5 a 7am y el viaje dura de 6 a 7 horas — escalonar no existe. (Esta nota
  decia lo contrario hasta agosto de 2026, cuando el negocio aclaro la regla.)
```

Y agrega, en la lista de pantallas del admin:

```markdown
- **Agenda** (`bookings.Agenda`, proxy de `Reserva`): reparte los viajes vendidos.
  Lista solo `pagada` y `asignada`, con `list_editable` para embarcacion y capitan.
  Poner la panga sube el estado a `asignada` y quitarla lo regresa — la transicion
  vive en `Reserva.save()`, no en el admin. El capitan no se exige: un viaje
  `asignada` sin capitan se marca "SIN CAPITAN" en rojo. El filtro "Cuando" tiene
  dos modos: "Manana" (cerrar el dia, se hace la tarde anterior) y "Proximos 7
  dias" (repartir la semana, incluye los atrasados que siguen en `pagada`).
```

- [ ] **Step 2: Corrige `docs/contexto-negocio.md`**

En la sección de Embarcaciones, después de la línea que ya habla de un solo viaje
por día, deja explícito que ahora se valida:

```markdown
- Una panga y un capitán hacen **un solo viaje por día**: las salidas son de 5 a 7am y el
  viaje dura de 6 a 7 horas, así que no hay forma de escalonar dos con la misma panga.
  **El sistema lo hace cumplir**: asignar la misma panga —o el mismo capitán— a dos
  viajes del mismo día se rechaza al guardar, venga de la agenda o del admin de
  reservas. Una reserva cancelada suelta su panga.
```

- [ ] **Step 3: Commit**

```bash
git add backend/CLAUDE.md docs/contexto-negocio.md
git commit -m "docs: una panga y un capitan hacen una sola salida por dia"
```

---

## Después de desplegar (paso manual)

**Correr `python manage.py setup_roles` en producción**, desde el shell de Render
(servicio `pescadeportiva-api`). Es idempotente. Sin eso la vendedora no ve la
agenda ni puede marcar pangas fuera de servicio: los permisos nuevos existen en el
código pero nadie se los ha dado al grupo.

## Fuera de alcance (confirmado en el spec)

- Asignar automáticamente qué panga le toca a cada viaje.
- Los capitanes en el motor de cupo: se pueden vender diez viajes un día con seis
  capitanes y nadie se entera hasta repartir.
- Reprogramar desde la agenda: cambiar la fecha tiene su propia regla de 48 horas
  y su propia pantalla.
- Vista de calendario: es una tabla ordenada por fecha y hora.
