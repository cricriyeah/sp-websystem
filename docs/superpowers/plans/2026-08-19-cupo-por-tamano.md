# Cupo consciente del tamaño del grupo — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el sistema deje de vender viajes que la flota real no puede operar, decidiendo el cupo en función del tamaño del grupo y no solo del número de viajes.

**Architecture:** `fleet` responde qué pangas están a flote un día (capacidad de cada una, de mayor a menor) sin saber nada de reservas. `bookings` toma esa lista y los grupos ya vendidos de ese día y decide con un emparejamiento exacto —el grupo más grande con la panga más grande— si cabe uno más. El mismo núcleo puro alimenta la validación al guardar, el endpoint `/api/cupo/`, la búsqueda de la próxima fecha y un comando de auditoría, así que no hay dos criterios que puedan divergir.

**Tech Stack:** Django 5 + DRF (backend, `backend/`), Next.js 16 + TypeScript (frontend, `frontend/`), Postgres en producción y CI, sqlite en local.

**Spec:** `docs/superpowers/specs/2026-08-17-cupo-por-tamano-design.md`

## Global Constraints

- **La flota real es 8 pangas de capacidad 3 y 2 de capacidad 5**, máximo 10. Ninguno de esos números se escribe en el código de producción: salen del catálogo `Embarcacion`.
- **`MAX_PERSONAS = 5`** ya está en `apps/bookings/models.py` y no se toca en este plan.
- **`CUPO_MAXIMO_DEFAULT = 10`** sigue siendo un tope de *viajes*, independiente de la disponibilidad física. No se fusiona con la capacidad de la flota.
- **Los strings de Python del repo van sin acentos** (ASCII). Los de las dictionaries del frontend sí llevan acentos. Respetar cada convención donde toca.
- **Comentarios y docstrings en español**, explicando el *porqué*, siguiendo el estilo del archivo que se toca.
- **`caben` decide si se cobra o no**: tiene que ser exacto, nunca una heurística.
- **`bloquear_cupo_del_dia(fecha)` se toma siempre ANTES de contar**, dentro de la transacción. Ese orden no cambia en ningún paso de este plan.
- **`personas` en `/api/cupo/` es opcional con default 1**: una petición sin el parámetro debe responder exactamente lo que respondía antes.
- Backend tests: `python manage.py test` desde `backend/`. Frontend: `npx tsc --noEmit` y `npm run lint` desde `frontend/`.
- Commits en español, en imperativo, con prefijo `feat:` / `fix:` / `test:` / `docs:`.

---

## File Map

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `backend/apps/fleet/models.py` | Modificar | `Embarcacion.activa`, etiquetas de `Clase` sin cifra, `EmbarcacionNoDisponible`, `capacidades_por_fecha` / `capacidades_disponibles`. Única fuente sobre qué pangas hay a flote. |
| `backend/apps/fleet/migrations/0006_*.py`, `0007_*.py` | Crear | `AddField activa` + `AlterField clase`; `CreateModel EmbarcacionNoDisponible`. |
| `backend/apps/fleet/admin.py` | Modificar | `activa` en el listado de `Embarcacion`; alta de `EmbarcacionNoDisponible` (único lugar para marcar una panga fuera un día hasta que exista la agenda). |
| `backend/apps/fleet/tests.py` | Modificar | Cobertura de `activa`, `EmbarcacionNoDisponible` y `capacidades_disponibles`. |
| `backend/apps/testing.py` | Modificar | `crear_flota()`: sin flota en la base, toda reserva sería inválida y la suite entera fallaría. |
| `backend/apps/bookings/models.py` | Modificar | Núcleo puro (`caben`, `motivo_sin_lugar`), `evaluar_cupo`, `validar_cupo_diario(fecha, personas, ...)`, `proxima_fecha_disponible(desde, personas, ...)`, `Reserva.clean`. |
| `backend/apps/bookings/views.py` | Modificar | `CupoDisponibleView` acepta `personas` y publica `motivo_no_disponible`. |
| `backend/apps/bookings/serializers.py` | Modificar | `CupoSerializer` gana `motivo_no_disponible`. |
| `backend/apps/bookings/management/commands/revisar_cupo.py` | Crear | Auditoría de los días ya vendidos que la flota real no puede operar. |
| `backend/apps/bookings/tests.py` | Modificar | Tests 1-19 del spec que tocan `bookings`. |
| `backend/apps/bookings/tests_concurrencia.py` | Modificar | Su `setUp` necesita la flota. |
| `backend/apps/finance/tests.py` · `notifications/tests.py` · `payments/tests.py` | Modificar | Sus helpers `crear_reserva` necesitan la flota. |
| `frontend/src/lib/api.ts` | Modificar | Tipo `Cupo` con `motivo_no_disponible`; `getCupo(fecha, personas)`. |
| `frontend/src/components/checkout-view.tsx` | Modificar | Reconsultar el cupo también al cambiar el número de personas; elegir el mensaje según el motivo. |
| `frontend/src/app/[lang]/dictionaries/es.json` · `en.json` | Modificar | Copia nueva: "no queda panga para tu grupo" ≠ "ese día está lleno". |
| `backend/CLAUDE.md` | Modificar | Firma del motor de cupo, endpoint y comando nuevos. |
| `docs/contexto-negocio.md` | Modificar | Que la disponibilidad diaria de la flota es un dato que se captura. |

<!-- arch-critic: revisión adversarial hecha en línea (este harness no despacha subagentes sin petición explícita del usuario). Hallazgos aplicados al File Map antes de escribir las tareas: (1) `fleet` no importa `bookings` en ningún punto — la dirección de dependencia queda igual que hoy y no hay ciclo; (2) el criterio de "cabe" tiene cuatro consumidores (validación, API, próxima fecha, comando), así que se factoriza en la función pura `motivo_sin_lugar` que los cuatro llaman, en vez de replicar el `if`; (3) la validación pasa a depender de una tabla que en los tests está vacía, lo que rompería los 87 puntos de creación de reservas: por eso `apps/testing.py` entra como tarea propia y ANTES de tocar `Reserva.clean`; (4) `capacidades_disponibles(fecha)` se implementa como el caso de un día de `capacidades_por_fecha(desde, hasta)` para que la ruta de una fecha y la de 90 días no puedan discrepar. -->

---

## Task 1: `Embarcacion` se puede dar de baja y deja de mentir su capacidad

**Files:**
- Modify: `backend/apps/fleet/models.py:82-97`
- Modify: `backend/apps/fleet/admin.py:38-42`
- Create: `backend/apps/fleet/migrations/0006_embarcacion_activa.py` (la genera Django)
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Consumes: nada.
- Produces: `Embarcacion.activa: BooleanField(default=True)`. `Embarcacion.Clase.CHICA.label == 'Chica'`, `Embarcacion.Clase.GRANDE.label == 'Grande'`. `str(embarcacion) == 'Lupita (Grande, max. 5)'`.

- [ ] **Step 1: Escribe el test que falla**

En `backend/apps/fleet/tests.py`, cambia el import de modelos y agrega la clase al final:

```python
from .models import Embarcacion, Tarifa


class EmbarcacionTests(TestCase):
    def test_nace_activa(self):
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        self.assertTrue(panga.activa)

    def test_la_etiqueta_de_clase_no_carga_la_capacidad(self):
        """La capacidad vive en `capacidad_maxima` y en ningun otro lado.

        La etiqueta decia "Grande (max. 6 personas)" y era falsa: ninguna panga
        lleva mas de 5. Un numero escrito en dos lugares es un numero que puede
        discrepar."""
        for clase in Embarcacion.Clase:
            self.assertNotIn('personas', clase.label)

    def test_str_muestra_la_capacidad(self):
        """El selector de la agenda enseña la capacidad donde se necesita."""
        panga = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        self.assertEqual(str(panga), 'Lupita (Grande, max. 5)')
```

- [ ] **Step 2: Corre el test y verifica que falla**

Run: `cd backend && python manage.py test apps.fleet.tests.EmbarcacionTests -v 2`
Esperado: FAIL — `Embarcacion` no tiene `activa` y `str()` no incluye la capacidad.

- [ ] **Step 3: Implementa el modelo**

En `backend/apps/fleet/models.py`, reemplaza la clase `Embarcacion` completa:

```python
class Embarcacion(models.Model):
    class Clase(models.TextChoices):
        # Sin cifra en la etiqueta a proposito: la capacidad vive en
        # `capacidad_maxima` y unicamente ahi. Decian "(max. 3 personas)" y
        # "(max. 6 personas)" — la segunda era falsa y nadie se entero, porque el
        # numero de verdad estaba en otro campo. `Clase` sigue existiendo porque
        # el negocio piensa en chicas y grandes y la copia del sitio las nombra
        # asi; solo deja de cargar un dato que no le toca.
        CHICA = 'chica', 'Chica'
        GRANDE = 'grande', 'Grande'

    nombre = models.CharField(max_length=100, unique=True)
    clase = models.CharField(max_length=10, choices=Clase.choices)
    capacidad_maxima = models.PositiveSmallIntegerField(
        help_text='Numero maximo de personas que puede llevar esta embarcacion.'
    )
    activa = models.BooleanField(
        default=True,
        help_text='Desmarcalo para sacar la panga de la flota sin borrarla (vendida, '
                  'fuera de servicio). Una panga inactiva deja de contar para el cupo '
                  'pero conserva los viajes historicos que tiene asignados.',
    )

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        # Con la capacidad, porque el selector de la agenda es donde se asigna
        # una panga a un grupo y ahi hace falta saber cuanta gente lleva.
        return f'{self.nombre} ({self.get_clase_display()}, max. {self.capacidad_maxima})'
```

Baja logica y no borrado: mismo patron que `Vendedora.activo`, y borrar dejaria viajes historicos sin panga.

En `backend/apps/fleet/admin.py`, reemplaza `EmbarcacionAdmin`:

```python
@admin.register(Embarcacion)
class EmbarcacionAdmin(ModelAdmin):
    list_display = ['nombre', 'clase', 'capacidad_maxima', 'activa']
    list_filter = ['clase', 'activa']
    list_editable = ['activa']
    search_fields = ['nombre']
```

- [ ] **Step 4: Genera y revisa la migración**

Run:
```bash
cd backend && python manage.py makemigrations fleet -n embarcacion_activa
cat apps/fleet/migrations/0006_embarcacion_activa.py
```
Esperado: un `AddField` de `activa` con `default=True` y un `AlterField` de `clase` que solo cambia `choices`. Los valores guardados (`chica`, `grande`) no se tocan: no hace falta migración de datos.

- [ ] **Step 5: Corre los tests y verifica que pasan**

Run: `cd backend && python manage.py test apps.fleet -v 2`
Esperado: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/fleet/models.py backend/apps/fleet/admin.py backend/apps/fleet/migrations/ backend/apps/fleet/tests.py
git commit -m "feat(flota): baja logica de embarcaciones y la capacidad en un solo lugar"
```

---

## Task 2: Qué pangas están a flote un día concreto

**Files:**
- Modify: `backend/apps/fleet/models.py` (al final del archivo)
- Modify: `backend/apps/fleet/admin.py`
- Create: `backend/apps/fleet/migrations/0007_embarcacionnodisponible.py` (la genera Django)
- Test: `backend/apps/fleet/tests.py`

**Interfaces:**
- Consumes: `Embarcacion.activa` (Task 1).
- Produces:
  - `EmbarcacionNoDisponible(fecha, embarcacion, motivo, registrado_por, creado_en)` con `unique_together = ('fecha', 'embarcacion')`.
  - `capacidades_por_fecha(desde, hasta) -> dict[date, list[int]]` — una entrada por cada día del rango, cada lista ordenada de mayor a menor. **Dos consultas**, no una por día.
  - `capacidades_disponibles(fecha) -> list[int]` — el caso de un solo día.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/fleet/tests.py`, ajusta la cabecera:

```python
from datetime import date, timedelta
from decimal import Decimal

from django.db.utils import IntegrityError
from django.test import TestCase, TransactionTestCase

from apps.payments.pricing import PERSONAS_INCLUIDAS

from .models import (
    Embarcacion,
    EmbarcacionNoDisponible,
    Tarifa,
    capacidades_disponibles,
    capacidades_por_fecha,
)
```

y agrega al final:

```python
class CapacidadesDisponiblesTests(TestCase):
    def setUp(self):
        self.fecha = date.today() + timedelta(days=10)
        self.chica = Embarcacion.objects.create(
            nombre='Chuy', clase=Embarcacion.Clase.CHICA, capacidad_maxima=3
        )
        self.grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )

    def test_devuelve_las_capacidades_de_mayor_a_menor(self):
        self.assertEqual(capacidades_disponibles(self.fecha), [5, 3])

    def test_excluye_las_inactivas(self):
        self.grande.activa = False
        self.grande.save()
        self.assertEqual(capacidades_disponibles(self.fecha), [3])

    def test_excluye_la_marcada_no_disponible_solo_ese_dia(self):
        """Una panga en mantenimiento el jueves vuelve a contar el viernes."""
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=self.grande, motivo='Mantenimiento'
        )
        self.assertEqual(capacidades_disponibles(self.fecha), [3])
        self.assertEqual(capacidades_disponibles(self.fecha + timedelta(days=1)), [5, 3])

    def test_el_rango_no_hace_una_consulta_por_dia(self):
        """El costo no puede crecer con la ventana: de aqui cuelga la busqueda
        de los proximos 90 dias del checkout."""
        with self.assertNumQueries(2):
            capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=89))

    def test_el_rango_trae_una_entrada_por_dia(self):
        rango = capacidades_por_fecha(self.fecha, self.fecha + timedelta(days=2))
        self.assertEqual(len(rango), 3)
        self.assertEqual(rango[self.fecha], [5, 3])


class EmbarcacionNoDisponibleUnicidadTests(TransactionTestCase):
    """Aparte y con TransactionTestCase: un IntegrityError deja inutilizable la
    transaccion que envuelve a un TestCase normal."""

    def test_una_panga_no_se_puede_marcar_dos_veces_el_mismo_dia(self):
        fecha = date.today() + timedelta(days=10)
        grande = Embarcacion.objects.create(
            nombre='Lupita', clase=Embarcacion.Clase.GRANDE, capacidad_maxima=5
        )
        EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande)
        with self.assertRaises(IntegrityError):
            EmbarcacionNoDisponible.objects.create(fecha=fecha, embarcacion=grande)
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && python manage.py test apps.fleet -v 2`
Esperado: FAIL — `ImportError: cannot import name 'EmbarcacionNoDisponible'`.

- [ ] **Step 3: Implementa el modelo y las funciones**

En `backend/apps/fleet/models.py`, agrega a la cabecera:

```python
from collections import defaultdict
from datetime import timedelta
```

y al final del archivo:

```python
class EmbarcacionNoDisponible(models.Model):
    """Una panga que no puede salir un dia concreto: mantenimiento, motor, lo que sea.

    Se registra **que falta**, no cuantas hay. Un conteo ("hoy hay 7") es un dato
    que nadie puede auditar despues; "la Lupita esta en mantenimiento el jueves"
    si. Sin registro para una fecha, ese dia esta la flota activa completa.

    No se confunde con `CupoDiario` (en `apps/bookings`), que es un tope de viajes
    que decide el negocio: son dos cosas distintas y meterlas en un solo numero
    las volveria imposibles de separar. Un dia puede tener las 10 pangas y un
    `CupoDiario` de 6 porque no hay capitanes; o el tope de 10 y solo 7 pangas a
    flote.
    """

    fecha = models.DateField()
    embarcacion = models.ForeignKey(
        # PROTECT: si esta panga tiene historial de bajas, borrarla dejaria
        # registros huerfanos. Para sacarla de la flota se desmarca `activa`.
        Embarcacion, on_delete=models.PROTECT, related_name='no_disponibles',
    )
    motivo = models.CharField(
        max_length=200, blank=True,
        help_text='Mantenimiento, motor descompuesto, prestada. Opcional.',
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='embarcaciones_dadas_de_baja',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fecha', 'embarcacion')
        ordering = ['-fecha', 'embarcacion__nombre']
        verbose_name = 'embarcacion no disponible'
        verbose_name_plural = 'embarcaciones no disponibles'

    def __str__(self):
        return f'{self.embarcacion.nombre} fuera el {self.fecha}'


def capacidades_por_fecha(desde, hasta):
    """Capacidad de cada panga que puede salir, por dia, de mayor a menor.

    `{fecha: [5, 3, 3, ...]}` con una entrada por cada dia del rango, incluidos
    los dias en que no falta ninguna.

    Son **dos consultas para todo el rango**, no una por dia: de aqui cuelga la
    busqueda de los proximos 90 dias del checkout, y esa busqueda ya murio una vez
    por hacer una peticion por dia (ver bookings.proxima_fecha_disponible).

    La flota no sabe nada de reservas a proposito: esto responde que hay a flote,
    no que esta vendido.
    """
    activas = list(Embarcacion.objects.filter(activa=True).values_list('id', 'capacidad_maxima'))

    fuera = defaultdict(set)
    for fecha, embarcacion_id in EmbarcacionNoDisponible.objects.filter(
        fecha__range=(desde, hasta)
    ).values_list('fecha', 'embarcacion_id'):
        fuera[fecha].add(embarcacion_id)

    dias = (hasta - desde).days + 1
    return {
        fecha: sorted(
            (capacidad for pk, capacidad in activas if pk not in fuera[fecha]), reverse=True
        )
        for fecha in (desde + timedelta(days=i) for i in range(dias))
    }


def capacidades_disponibles(fecha):
    """Las capacidades a flote ese dia, de mayor a menor.

    Es el caso de un dia de `capacidades_por_fecha`, y se implementa asi para que
    la ruta de una fecha y la de 90 dias no puedan discrepar nunca.
    """
    return capacidades_por_fecha(fecha, fecha)[fecha]
```

En `backend/apps/fleet/admin.py`, amplía el import y registra el modelo:

```python
from .models import Capitan, Embarcacion, EmbarcacionNoDisponible, Tarifa


@admin.register(EmbarcacionNoDisponible)
class EmbarcacionNoDisponibleAdmin(ModelAdmin):
    """Aqui se marca que una panga no sale un dia. Mientras no exista la agenda
    operativa, este es el unico lugar para hacerlo."""

    list_display = ['fecha', 'embarcacion', 'motivo', 'registrado_por']
    list_filter = ['fecha', 'embarcacion']
    autocomplete_fields = ['embarcacion']
    readonly_fields = ['registrado_por', 'creado_en']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)
```

- [ ] **Step 4: Genera la migración y corre los tests**

Run: `cd backend && python manage.py makemigrations fleet -n embarcacionnodisponible && python manage.py test apps.fleet -v 2`
Esperado: la migración crea el modelo con su `unique_together`; PASS en todos los tests de `fleet`.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/fleet/
git commit -m "feat(flota): registrar que pangas no salen un dia y responder cuales quedan"
```

---

## Task 3: Los tests tienen flota

**Files:**
- Modify: `backend/apps/testing.py`
- Modify: `backend/apps/bookings/tests.py:35-57`, `backend/apps/bookings/tests_concurrencia.py:62-70`
- Modify: `backend/apps/finance/tests.py:24`, `backend/apps/notifications/tests.py:20`, `backend/apps/payments/tests.py:85`

**Interfaces:**
- Consumes: `Embarcacion` (Task 1).
- Produces: `apps.testing.crear_flota()` — idempotente, crea la flota real (8 pangas de 3, 2 de 5) y devuelve la lista de `Embarcacion`.

**Por qué esta tarea existe:** a partir de la Task 5 la validación de cupo le pregunta a la flota. Con el catálogo `Embarcacion` vacío no cabe ningún grupo, así que **cada test que crea una reserva fallaría**. Esta tarea va antes y por sí sola no cambia ningún comportamiento.

- [ ] **Step 1: Escribe el helper**

En `backend/apps/testing.py`, al final:

```python
from apps.fleet.models import Embarcacion

# La flota real del negocio: 8 pangas de hasta 3 personas y 2 de hasta 5.
FLOTA_REAL = [(8, 3), (2, 5)]


def crear_flota(composicion=FLOTA_REAL):
    """Da de alta la flota en la base de pruebas. Idempotente.

    Hace falta en cualquier test que cree una reserva: desde que el cupo es
    consciente del tamaño del grupo, sin pangas en la base no cabe nadie y la
    validacion rechaza todo. Es el mismo fallo seguro que en produccion — solo
    que ahi la flota se captura una vez y aqui hay que sembrarla.
    """
    if Embarcacion.objects.exists():
        return list(Embarcacion.objects.all())

    pangas = []
    for cuantas, capacidad in composicion:
        clase = Embarcacion.Clase.CHICA if capacidad <= 3 else Embarcacion.Clase.GRANDE
        for i in range(cuantas):
            pangas.append(Embarcacion(
                nombre=f'Panga {capacidad}-{i + 1}', clase=clase, capacidad_maxima=capacidad,
            ))
    return Embarcacion.objects.bulk_create(pangas)
```

- [ ] **Step 2: Siembra la flota en cada helper que crea reservas**

En `backend/apps/bookings/tests.py`, cambia el import y los dos helpers:

```python
from apps.testing import ApiTestCase, crear_flota


def datos_reserva(**overrides):
    # Hay tests que llaman Reserva(**datos_reserva()).full_clean() directo, y el
    # motor de cupo le pregunta a la flota: sin pangas no cabe nadie.
    crear_flota()
    base = {
        ...  # el resto sin cambios
    }


def crear_reserva(**overrides):
    reserva = Reserva(**datos_reserva(**overrides))
    reserva.full_clean()
    reserva.save()
    return reserva
```

Agrega `crear_flota()` como primera línea del helper `crear_reserva` en:
- `backend/apps/finance/tests.py:24`
- `backend/apps/notifications/tests.py:20`
- `backend/apps/payments/tests.py:85`

y como primera línea del `setUp` de cada clase en `backend/apps/bookings/tests_concurrencia.py`:

```python
    def setUp(self):
        crear_flota()
        self.fecha = date.today() + timedelta(days=10)
```

con `from apps.testing import crear_flota` en los cuatro archivos.

- [ ] **Step 3: Corre toda la suite y verifica que sigue verde**

Run: `cd backend && python manage.py test -v 1`
Esperado: PASS, el mismo número de tests que antes. Esta tarea no cambia comportamiento.

- [ ] **Step 4: Commit**

```bash
git add backend/apps/testing.py backend/apps/bookings/tests.py backend/apps/bookings/tests_concurrencia.py backend/apps/finance/tests.py backend/apps/notifications/tests.py backend/apps/payments/tests.py
git commit -m "test: sembrar la flota real en los tests que crean reservas"
```

---

## Task 4: El criterio de si cabe un grupo más

**Files:**
- Modify: `backend/apps/bookings/models.py` (después de `cupo_maximo_del_dia`, línea ~80)
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: nada — son funciones puras, sin base de datos.
- Produces:
  - `MOTIVO_LLENO = 'lleno'`, `MOTIVO_SIN_PANGA = 'sin_panga'`
  - `caben(grupos, capacidades) -> bool` — **ambas listas ordenadas de mayor a menor**.
  - `motivo_sin_lugar(personas, grupos, capacidades, tope) -> str | None` — `None` si cabe; si no, `MOTIVO_LLENO` o `MOTIVO_SIN_PANGA`. `grupos` son los ya vendidos (sin el nuevo); `capacidades` viene ordenada de mayor a menor.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/bookings/tests.py`, amplía el import de `.models`:

```python
from .models import (
    CUPO_MAXIMO_DEFAULT,
    MAX_PERSONAS,
    MOTIVO_LLENO,
    MOTIVO_SIN_PANGA,
    caben,
    motivo_sin_lugar,
    proxima_fecha_disponible,
    HORAS_PARA_CONSIDERAR_ABANDONADO,
    CheckoutAbandonado,
    CupoDiario,
    Reserva,
    Vendedora,
)
```

y agrega al final del archivo:

```python
class CabenTests(TestCase):
    """El criterio que decide si se cobra o no. Exacto, no heuristica."""

    FLOTA = [5, 5, 3, 3, 3, 3, 3, 3, 3, 3]

    def test_sin_grupos_siempre_cabe(self):
        self.assertTrue(caben([], self.FLOTA))

    def test_mas_grupos_que_pangas_no_cabe(self):
        self.assertFalse(caben([2] * 11, self.FLOTA))

    def test_tres_grupos_de_cuatro_no_caben_en_dos_pangas_grandes(self):
        self.assertFalse(caben([4, 4, 4], self.FLOTA))

    def test_dos_de_cuatro_y_ocho_de_tres_si_caben(self):
        """El caso apretado que si es operable: no puede rechazarse."""
        self.assertTrue(caben([4, 4, 3, 3, 3, 3, 3, 3, 3, 3], self.FLOTA))

    def test_un_grupo_mas_grande_que_la_panga_mas_grande_no_cabe(self):
        self.assertFalse(caben([6], [5]))

    def test_no_depende_del_orden_de_llegada(self):
        """Se emparejan de mayor a menor, asi que el resultado es el mismo
        vengan como vengan."""
        grupos = [4, 2, 4, 3]
        self.assertEqual(
            caben(sorted(grupos, reverse=True), self.FLOTA),
            caben(sorted(list(reversed(grupos)), reverse=True), self.FLOTA),
        )


class MotivoSinLugarTests(TestCase):
    FLOTA = [5, 5, 3, 3, 3, 3, 3, 3, 3, 3]

    def test_si_cabe_no_hay_motivo(self):
        self.assertIsNone(motivo_sin_lugar(2, [], self.FLOTA, tope=10))

    def test_el_tope_de_viajes_manda_sobre_el_de_pangas(self):
        """Si el dia esta lleno a secas, ese es el mensaje util."""
        self.assertEqual(motivo_sin_lugar(4, [2] * 10, self.FLOTA, tope=10), MOTIVO_LLENO)

    def test_sin_panga_para_ese_grupo(self):
        self.assertEqual(motivo_sin_lugar(4, [4, 4], self.FLOTA, tope=10), MOTIVO_SIN_PANGA)

    def test_un_grupo_chico_si_entra_el_mismo_dia(self):
        """Se acabaron las grandes, no el dia."""
        self.assertIsNone(motivo_sin_lugar(2, [4, 4], self.FLOTA, tope=10))
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && python manage.py test apps.bookings.tests.CabenTests apps.bookings.tests.MotivoSinLugarTests -v 2`
Esperado: FAIL — `ImportError: cannot import name 'caben'`.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, justo después de `cupo_maximo_del_dia`:

```python
# Por que no se puede vender un lugar. Viajan al frontend en la respuesta de
# /api/cupo/, porque "ese dia esta lleno" y "no queda panga para tu grupo" son
# dos cosas distintas para el cliente que las lee.
MOTIVO_LLENO = 'lleno'
MOTIVO_SIN_PANGA = 'sin_panga'


def caben(grupos, capacidades):
    """¿Hay forma de darle a cada grupo una panga donde quepa?

    Las dos listas llegan ordenadas **de mayor a menor**.

    Se emparejan de mayor a menor: el grupo mas grande con la panga mas grande.
    Si a algun grupo le toca una panga mas chica que el, no hay reparto posible —
    y no lo hay con ningun otro orden, porque cualquier reparto valido tendria que
    darle a ese grupo una panga al menos igual de grande, y todas las de arriba ya
    estan ocupadas por grupos aun mayores.

    Con 10 pangas el costo es irrelevante, pero importa que el criterio sea exacto
    y no una heuristica: de esto depende si se cobra o no.
    """
    if len(grupos) > len(capacidades):
        return False
    return all(g <= c for g, c in zip(grupos, capacidades))


def motivo_sin_lugar(personas, grupos, capacidades, tope):
    """Por que no entra un grupo de `personas` mas, o None si si entra.

    `grupos` son los tamaños ya vendidos de ese dia, sin el nuevo. `capacidades`
    viene ordenada de mayor a menor. `tope` es el maximo de viajes del dia.

    Es el nucleo puro del cupo: no toca la base. Lo llaman la validacion al
    guardar, el endpoint /api/cupo/, la busqueda de la proxima fecha y el comando
    revisar_cupo — los cuatro tienen que decidir igual, y por eso deciden aqui.

    El orden de las dos comprobaciones importa: si el dia esta lleno a secas, ese
    es el mensaje util, no el de las pangas.
    """
    if len(grupos) + 1 > tope:
        return MOTIVO_LLENO
    if not caben(sorted([*grupos, personas], reverse=True), capacidades):
        return MOTIVO_SIN_PANGA
    return None
```

- [ ] **Step 4: Corre los tests y verifica que pasan**

Run: `cd backend && python manage.py test apps.bookings.tests.CabenTests apps.bookings.tests.MotivoSinLugarTests -v 2`
Esperado: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/tests.py
git commit -m "feat(cupo): criterio exacto de si un grupo mas cabe en la flota del dia"
```

---

## Task 5: La validación al guardar mira el tamaño del grupo

**Files:**
- Modify: `backend/apps/bookings/models.py:152-165` (`validar_cupo_diario`), `backend/apps/bookings/models.py:387-390` (`Reserva.clean`)
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `motivo_sin_lugar`, `MOTIVO_LLENO`, `MOTIVO_SIN_PANGA` (Task 4); `capacidades_disponibles` (Task 2); `crear_flota` (Task 3).
- Produces:
  - `evaluar_cupo(fecha, personas, excluir_pk=None) -> str | None` — **no toma el lock**, solo consulta.
  - `validar_cupo_diario(fecha, personas, excluir_pk=None)` — toma el lock, llama a `evaluar_cupo`, levanta `ValidationError` con el mensaje del motivo.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/bookings/tests.py`, amplía el import de fleet:

```python
from apps.fleet.models import Embarcacion, EmbarcacionNoDisponible
```

y agrega al final:

```python
class CupoPorTamanoDelGrupoTests(TestCase):
    """Un dia puede tener lugares libres y aun asi no poder recibir a un grupo de
    4: solo dos pangas de la flota lo llevan."""

    def setUp(self):
        crear_flota()
        self.fecha = date.today() + timedelta(days=10)

    def _vender(self, personas):
        return crear_reserva(
            fecha=self.fecha, numero_personas=personas, estado=Reserva.Estado.PAGADA
        )

    def test_un_tercer_grupo_de_cuatro_se_rechaza(self):
        self._vender(4)
        self._vender(4)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(fecha=self.fecha, numero_personas=4,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('No queda panga', str(ctx.exception))

    def test_un_grupo_chico_el_mismo_dia_si_se_acepta(self):
        """El dia no esta lleno, solo se acabaron las pangas grandes."""
        self._vender(4)
        self._vender(4)
        Reserva(**datos_reserva(fecha=self.fecha, numero_personas=2,
                                estado=Reserva.Estado.PAGADA)).full_clean()

    def test_un_dia_lleno_a_secas_da_el_mensaje_del_tope_de_viajes(self):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            self._vender(2)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(fecha=self.fecha, numero_personas=2,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('maximo de viajes', str(ctx.exception))

    def test_el_cupo_cerrado_a_mano_manda_sobre_la_flota(self):
        CupoDiario.objects.create(fecha=self.fecha, cupo_maximo=3)
        for _ in range(3):
            self._vender(2)
        with self.assertRaises(ValidationError) as ctx:
            Reserva(**datos_reserva(fecha=self.fecha, numero_personas=2,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
        self.assertIn('maximo de viajes', str(ctx.exception))

    def test_editar_una_reserva_no_la_cuenta_contra_si_misma(self):
        self._vender(4)
        reserva = self._vender(4)
        reserva.nombre_cliente = 'Ana Ruiz Corregido'
        reserva.full_clean()

    def test_una_reserva_cancelada_libera_su_panga(self):
        self._vender(4)
        cancelada = self._vender(4)
        cancelada.estado = Reserva.Estado.CANCELADA
        cancelada.save()

        Reserva(**datos_reserva(fecha=self.fecha, numero_personas=4,
                                estado=Reserva.Estado.PAGADA)).full_clean()

    def test_una_panga_marcada_fuera_reduce_el_cupo_de_ese_dia(self):
        grande = Embarcacion.objects.filter(capacidad_maxima=5).first()
        EmbarcacionNoDisponible.objects.create(
            fecha=self.fecha, embarcacion=grande, motivo='Motor'
        )
        self._vender(4)
        with self.assertRaises(ValidationError):
            Reserva(**datos_reserva(fecha=self.fecha, numero_personas=4,
                                    estado=Reserva.Estado.PAGADA)).full_clean()
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && python manage.py test apps.bookings.tests.CupoPorTamanoDelGrupoTests -v 2`
Esperado: FAIL — hoy se aceptan los tres grupos de 4.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, amplía el import de fleet:

```python
from apps.fleet.models import Capitan, Embarcacion, capacidades_disponibles
```

y reemplaza `validar_cupo_diario` completa por estas dos funciones:

```python
def evaluar_cupo(fecha, personas, excluir_pk=None):
    """Por que no entra un grupo de `personas` ese dia, o None si si entra.

    Solo consulta: **no toma el lock**. La usa `/api/cupo/`, que es una lectura
    informativa, y `validar_cupo_diario`, que si lo toma antes de llamar aqui.
    """
    ocupadas = Reserva.objects.filter(fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO)
    if excluir_pk is not None:
        ocupadas = ocupadas.exclude(pk=excluir_pk)

    return motivo_sin_lugar(
        personas,
        list(ocupadas.values_list('numero_personas', flat=True)),
        capacidades_disponibles(fecha),
        cupo_maximo_del_dia(fecha),
    )


def validar_cupo_diario(fecha, personas, excluir_pk=None):
    """Motor unico de validacion de cupo. Debe usarse tanto para el flujo de pago
    de la web como para la creacion/edicion manual de Reserva (ver backend/CLAUDE.md).

    Dos motivos con dos mensajes distintos, porque son dos problemas distintos
    para quien los lee: el dia se lleno, o el dia tiene espacio pero ya no hay
    panga donde quepa ese grupo.
    """
    # Antes de contar, no despues: ver bloquear_cupo_del_dia. Ahora el lock ademas
    # cubre el ultimo lugar *de ese tamaño*, no solo el ultimo lugar.
    bloquear_cupo_del_dia(fecha)

    motivo = evaluar_cupo(fecha, personas, excluir_pk=excluir_pk)
    if motivo == MOTIVO_LLENO:
        raise ValidationError(
            f'No hay cupo disponible para el {fecha}: se alcanzo el maximo de viajes del dia.'
        )
    if motivo == MOTIVO_SIN_PANGA:
        raise ValidationError(
            f'No queda panga para un grupo de {personas} personas el {fecha}. '
            f'Las de mayor capacidad ya estan comprometidas.'
        )
```

y en `Reserva.clean`:

```python
        if self.estado in ESTADOS_QUE_OCUPAN_CUPO:
            validar_cupo_diario(self.fecha, self.numero_personas, excluir_pk=self.pk)
```

- [ ] **Step 4: Corre toda la suite del backend**

Run: `cd backend && python manage.py test -v 1`
Esperado: PASS. Si falla algo en `payments`, `finance` o `notifications`, es que a ese helper le faltó `crear_flota()` en la Task 3.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/tests.py
git commit -m "feat(cupo): rechazar el grupo que ya no tiene panga donde quepa"
```

---

## Task 6: La próxima fecha disponible sabe de qué tamaño es el grupo

**Files:**
- Modify: `backend/apps/bookings/models.py:96-125` (`proxima_fecha_disponible`)
- Test: `backend/apps/bookings/tests.py:766-805` (`ProximaFechaDisponibleTests`)

**Interfaces:**
- Consumes: `motivo_sin_lugar` (Task 4), `capacidades_por_fecha` (Task 2).
- Produces: `proxima_fecha_disponible(desde, personas, dias=DIAS_BUSQUEDA_DISPONIBILIDAD) -> date | None`. **`personas` es obligatorio y posicional.** Cuatro consultas totales, independientes de `dias`.

- [ ] **Step 1: Escribe los tests que fallan**

En `ProximaFechaDisponibleTests`, pásale `2` como segundo argumento a las cuatro llamadas que ya existen, agrega un `setUp` que siembre la flota (dos de esos tests no crean ninguna reserva, así que hoy no hay quien la siembre por ellos y sin pangas no cabría nadie), reemplaza el test de consultas y agrega el nuevo:

```python
    def setUp(self):
        crear_flota()

    def test_no_hace_una_consulta_por_dia(self):
        """El punto entero del cambio: el costo no crece con la ventana.

        Cuatro consultas fijas: reservas del rango, CupoDiario del rango, y las
        dos de la flota (pangas activas y las marcadas fuera).
        """
        desde = date.today() + timedelta(days=10)
        with self.assertNumQueries(4):
            proxima_fecha_disponible(desde, 2, dias=90)

    def test_salta_los_dias_sin_panga_para_ese_grupo(self):
        """El dia tiene lugares libres, pero no para un grupo de 4."""
        primero = date.today() + timedelta(days=10)
        crear_reserva(fecha=primero, numero_personas=4, estado=Reserva.Estado.PAGADA)
        crear_reserva(fecha=primero, numero_personas=4, estado=Reserva.Estado.PAGADA)

        self.assertEqual(proxima_fecha_disponible(primero, 4), primero + timedelta(days=1))
        self.assertEqual(proxima_fecha_disponible(primero, 2), primero)
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && python manage.py test apps.bookings.tests.ProximaFechaDisponibleTests -v 2`
Esperado: FAIL — `proxima_fecha_disponible() takes 1 positional argument but 2 were given`.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/models.py`, agrega `from collections import defaultdict` a la cabecera, `capacidades_por_fecha` al import de `apps.fleet.models`, y reemplaza `proxima_fecha_disponible` completa:

```python
def proxima_fecha_disponible(desde, personas, dias=DIAS_BUSQUEDA_DISPONIBILIDAD):
    """Primera fecha donde cabe un grupo de `personas`, o None si no hay en `dias`.

    Se resuelve con **cuatro consultas**, no una por dia: reservas del rango,
    CupoDiario del rango, y las dos de la flota. Antes esta busqueda vivia en el
    navegador (`checkout-view.tsx`) y hacia una peticion por cada dia que probaba:
    hasta 90 seguidas, que con el limite de 60/min por IP terminaban en un 429 que
    el frontend se tragaba en silencio. La ayuda de "te muevo al siguiente dia con
    espacio" dejaba de funcionar justo en temporada alta, que es cuando hace falta.
    El costo no puede volver a crecer con la ventana.
    """
    hasta = desde + timedelta(days=dias - 1)

    grupos_por_fecha = defaultdict(list)
    for fecha, personas_de_esa in Reserva.objects.filter(
        fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO
    ).values_list('fecha', 'numero_personas'):
        grupos_por_fecha[fecha].append(personas_de_esa)

    topes = dict(
        CupoDiario.objects.filter(fecha__range=(desde, hasta)).values_list('fecha', 'cupo_maximo')
    )
    capacidades = capacidades_por_fecha(desde, hasta)

    for i in range(dias):
        fecha = desde + timedelta(days=i)
        motivo = motivo_sin_lugar(
            personas,
            grupos_por_fecha[fecha],
            capacidades[fecha],
            topes.get(fecha, CUPO_MAXIMO_DEFAULT),
        )
        if motivo is None:
            return fecha
    return None
```

- [ ] **Step 4: Corre los tests**

Run: `cd backend && python manage.py test apps.bookings -v 1`
Esperado: PASS salvo los tests de `/api/cupo/`, porque `apps/bookings/views.py` todavía llama a `proxima_fecha_disponible(fecha)` con un solo argumento. Pasa `1` provisionalmente en la vista para dejar la suite verde; queda correcto en la Task 7.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/models.py backend/apps/bookings/views.py backend/apps/bookings/tests.py
git commit -m "feat(cupo): la proxima fecha disponible depende del tamaño del grupo"
```

---

## Task 7: `/api/cupo/` responde por qué no se puede

**Files:**
- Modify: `backend/apps/bookings/views.py:11-45`
- Modify: `backend/apps/bookings/serializers.py:9-19`
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `evaluar_cupo`, `proxima_fecha_disponible`, `MOTIVO_LLENO`, `MOTIVO_SIN_PANGA`.
- Produces: `GET /api/cupo/?fecha=YYYY-MM-DD&personas=N` → `{fecha, cupo_maximo, ocupadas, disponible, proxima_disponible, motivo_no_disponible}`. `personas` opcional, default 1. `motivo_no_disponible` es `'lleno'`, `'sin_panga'` o `null`.

- [ ] **Step 1: Escribe los tests que fallan**

En `backend/apps/bookings/tests.py`, al final:

```python
class CupoApiPorTamanoTests(ApiTestCase):
    def setUp(self):
        crear_flota()
        self.fecha = date.today() + timedelta(days=10)

    def test_sin_personas_responde_como_antes(self):
        """Compatibilidad: nada que llame a la API vieja se puede romper."""
        cuerpo = self.client.get(f'/api/cupo/?fecha={self.fecha}').json()
        self.assertTrue(cuerpo['disponible'])
        self.assertIsNone(cuerpo['motivo_no_disponible'])
        self.assertEqual(cuerpo['cupo_maximo'], CUPO_MAXIMO_DEFAULT)

    def test_un_grupo_de_cuatro_sin_pangas_grandes_libres(self):
        crear_reserva(fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)
        crear_reserva(fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)

        grande = self.client.get(f'/api/cupo/?fecha={self.fecha}&personas=4').json()
        self.assertFalse(grande['disponible'])
        self.assertEqual(grande['motivo_no_disponible'], MOTIVO_SIN_PANGA)
        self.assertEqual(grande['proxima_disponible'], str(self.fecha + timedelta(days=1)))

        chico = self.client.get(f'/api/cupo/?fecha={self.fecha}&personas=2').json()
        self.assertTrue(chico['disponible'])
        self.assertIsNone(chico['motivo_no_disponible'])

    def test_un_dia_lleno_dice_lleno(self):
        for _ in range(CUPO_MAXIMO_DEFAULT):
            crear_reserva(fecha=self.fecha, numero_personas=2, estado=Reserva.Estado.PAGADA)

        cuerpo = self.client.get(f'/api/cupo/?fecha={self.fecha}&personas=2').json()
        self.assertEqual(cuerpo['motivo_no_disponible'], MOTIVO_LLENO)

    def test_personas_que_no_es_numero_da_400(self):
        respuesta = self.client.get(f'/api/cupo/?fecha={self.fecha}&personas=cuatro')
        self.assertEqual(respuesta.status_code, 400)

    def test_personas_fuera_del_rango_da_400(self):
        for valor in (0, MAX_PERSONAS + 1):
            with self.subTest(personas=valor):
                respuesta = self.client.get(f'/api/cupo/?fecha={self.fecha}&personas={valor}')
                self.assertEqual(respuesta.status_code, 400)
```

- [ ] **Step 2: Corre los tests y verifica que fallan**

Run: `cd backend && python manage.py test apps.bookings.tests.CupoApiPorTamanoTests -v 2`
Esperado: FAIL — `KeyError: 'motivo_no_disponible'`.

- [ ] **Step 3: Implementa**

En `backend/apps/bookings/serializers.py`, `CupoSerializer`:

```python
class CupoSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    cupo_maximo = serializers.IntegerField()
    ocupadas = serializers.IntegerField()
    disponible = serializers.BooleanField()
    # Primera fecha con espacio PARA ESE GRUPO a partir de la pedida. Evita que el
    # navegador tenga que preguntar dia por dia (ver models.proxima_fecha_disponible).
    proxima_disponible = serializers.DateField(allow_null=True)
    # 'lleno' | 'sin_panga' | null. Sin esto el frontend no puede decir la verdad
    # de por que no se puede: "ese dia esta lleno" y "el dia tiene espacio pero ya
    # no hay panga para tu grupo" son mensajes distintos para el cliente.
    motivo_no_disponible = serializers.CharField(allow_null=True)
```

En `backend/apps/bookings/views.py`, reemplaza el import y la vista:

```python
from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    MAX_PERSONAS,
    MIN_PERSONAS,
    Reserva,
    cupo_maximo_del_dia,
    evaluar_cupo,
    proxima_fecha_disponible,
)


class CupoDisponibleView(APIView):
    """Cupo restante para una fecha y un tamaño de grupo, para que el checkout
    avise antes de pagar (la validacion real y definitiva ocurre al confirmar el
    pago, ver apps/payments)."""

    throttle_scope = 'consulta'

    def get(self, request):
        fecha = request.query_params.get('fecha')
        if not fecha:
            return Response({'detail': 'Falta el parametro fecha.'}, status=400)

        try:
            fecha = date.fromisoformat(fecha)
        except ValueError:
            return Response({'detail': 'fecha debe tener el formato YYYY-MM-DD.'}, status=400)

        # Opcional con default 1 a proposito: una peticion sin `personas` tiene que
        # responder lo mismo que antes de que el cupo supiera de tamaños.
        try:
            personas = int(request.query_params.get('personas', MIN_PERSONAS))
        except (TypeError, ValueError):
            return Response({'detail': 'personas debe ser un numero entero.'}, status=400)
        if not (MIN_PERSONAS <= personas <= MAX_PERSONAS):
            return Response(
                {'detail': f'personas debe estar entre {MIN_PERSONAS} y {MAX_PERSONAS}.'},
                status=400,
            )

        motivo = evaluar_cupo(fecha, personas)
        data = {
            'fecha': fecha,
            'cupo_maximo': cupo_maximo_del_dia(fecha),
            'ocupadas': Reserva.objects.filter(
                fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO
            ).count(),
            'disponible': motivo is None,
            # Se responde siempre, tambien cuando el dia pedido si tiene espacio:
            # asi el navegador nunca necesita una segunda vuelta.
            'proxima_disponible': proxima_fecha_disponible(fecha, personas),
            'motivo_no_disponible': motivo,
        }
        return Response(CupoSerializer(data).data)
```

- [ ] **Step 4: Corre toda la suite del backend**

Run: `cd backend && python manage.py test -v 1`
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/views.py backend/apps/bookings/serializers.py backend/apps/bookings/tests.py
git commit -m "feat(api): /api/cupo/ responde por tamaño de grupo y dice por que no se puede"
```

---

## Task 8: `revisar_cupo`, para los días ya vendidos que no cierran

**Files:**
- Create: `backend/apps/bookings/management/commands/revisar_cupo.py`
- Test: `backend/apps/bookings/tests.py`

**Interfaces:**
- Consumes: `caben`, `cupo_maximo_del_dia`, `ESTADOS_QUE_OCUPAN_CUPO`, `capacidades_por_fecha`.
- Produces: `python manage.py revisar_cupo [--dias 90]`, que escribe en stdout una línea por día no operable y nada si todos cierran.

**Por qué:** la validación corre al guardar, así que una fila vendida antes de este cambio sobrevive intacta. Puede haber días ya cobrados que la flota real no puede operar; hay que encontrarlos antes de que llegue la fecha.

- [ ] **Step 1: Escribe el test que falla**

En `backend/apps/bookings/tests.py`, al final:

```python
class RevisarCupoTests(TestCase):
    def setUp(self):
        crear_flota()
        self.fecha = date.today() + timedelta(days=10)

    def _salida(self, **opciones):
        salida = StringIO()
        call_command('revisar_cupo', stdout=salida, **opciones)
        return salida.getvalue()

    def test_no_reporta_nada_cuando_todos_los_dias_cierran(self):
        crear_reserva(fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA)
        self.assertNotIn(str(self.fecha), self._salida())

    def test_encuentra_un_dia_vendido_que_no_es_operable(self):
        """Tres grupos de 4 con solo dos pangas grandes: se vendio antes de que el
        motor supiera de tamaños y hay que resolverlo a mano.

        Se usa Reserva.objects.create sin full_clean a proposito: es exactamente
        la fila que este comando existe para encontrar.
        """
        for _ in range(3):
            Reserva.objects.create(**datos_reserva(
                fecha=self.fecha, numero_personas=4, estado=Reserva.Estado.PAGADA
            ))

        salida = self._salida()
        self.assertIn(str(self.fecha), salida)
        self.assertIn('4, 4, 4', salida)
```

- [ ] **Step 2: Corre el test y verifica que falla**

Run: `cd backend && python manage.py test apps.bookings.tests.RevisarCupoTests -v 2`
Esperado: FAIL — `Unknown command: 'revisar_cupo'`.

- [ ] **Step 3: Implementa**

Crea `backend/apps/bookings/management/commands/revisar_cupo.py`:

```python
"""Los dias ya vendidos que la flota real no puede operar.

El motor de cupo valida al guardar, asi que una reserva que entro antes de que el
cupo supiera de tamaños de grupo sobrevive intacta. Puede haber un dia con tres
grupos de 4 y solo dos pangas que los lleven: nadie se entera hasta que el tercer
cliente llega al muelle.

Este comando no arregla nada a proposito — a quien se le mueve la fecha lo decide
una persona, no el sistema. Solo enseña los dias que no cierran.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bookings.models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    Reserva,
    caben,
    cupo_maximo_del_dia,
)
from apps.fleet.models import capacidades_por_fecha

DIAS_POR_DEFECTO = 90


class Command(BaseCommand):
    help = 'Lista los dias ya vendidos que no se pueden operar con la flota real.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=DIAS_POR_DEFECTO,
            help=f'Cuantos dias hacia adelante revisar. Por defecto {DIAS_POR_DEFECTO}.',
        )

    def handle(self, *args, **options):
        desde = timezone.localdate()
        hasta = desde + timedelta(days=options['dias'] - 1)

        grupos_por_fecha = {}
        for fecha, personas in Reserva.objects.filter(
            fecha__range=(desde, hasta), estado__in=ESTADOS_QUE_OCUPAN_CUPO
        ).values_list('fecha', 'numero_personas'):
            grupos_por_fecha.setdefault(fecha, []).append(personas)

        capacidades = capacidades_por_fecha(desde, hasta)

        problemas = 0
        for fecha in sorted(grupos_por_fecha):
            grupos = sorted(grupos_por_fecha[fecha], reverse=True)
            if len(grupos) <= cupo_maximo_del_dia(fecha) and caben(grupos, capacidades[fecha]):
                continue

            problemas += 1
            self.stdout.write(
                f'{fecha}: {len(grupos)} viajes vendidos '
                f'({", ".join(str(g) for g in grupos)} personas) '
                f'y solo {len(capacidades[fecha])} pangas a flote '
                f'({", ".join(str(c) for c in capacidades[fecha])}). No cierra.'
            )

        if problemas:
            self.stdout.write(f'{problemas} dia(s) por resolver a mano.')
```

- [ ] **Step 4: Corre los tests y verifica que pasan**

Run: `cd backend && python manage.py test apps.bookings.tests.RevisarCupoTests -v 2`
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/apps/bookings/management/commands/revisar_cupo.py backend/apps/bookings/tests.py
git commit -m "feat(cupo): comando revisar_cupo para los dias vendidos que no cierran"
```

---

## Task 9: El checkout pregunta por su grupo y dice la verdad

**Files:**
- Modify: `frontend/src/lib/api.ts:24-34`, `frontend/src/lib/api.ts:104`
- Modify: `frontend/src/components/checkout-view.tsx:152-180`
- Modify: `frontend/src/app/[lang]/dictionaries/es.json:422`, `frontend/src/app/[lang]/dictionaries/en.json:422`

**Interfaces:**
- Consumes: el contrato de `/api/cupo/` de la Task 7.
- Produces: `getCupo(fecha: string, personas: number)`; `Cupo.motivo_no_disponible: 'lleno' | 'sin_panga' | null`; clave `checkout.noBoatForGroupNotice` (nueva) junto a `checkout.dayFullNotice` (ya existe) en las dos dictionaries.

- [ ] **Step 1: Actualiza el cliente de la API**

En `frontend/src/lib/api.ts`, el tipo `Cupo`:

```ts
export type Cupo = {
  fecha: string;
  cupo_maximo: number;
  ocupadas: number;
  disponible: boolean;
  // Primera fecha con espacio PARA ESE GRUPO a partir de la pedida, o null si no
  // hay ninguna en los proximos 90 dias. La calcula el backend en cuatro
  // consultas: antes el navegador la buscaba preguntando dia por dia, hasta 90
  // peticiones seguidas que agotaban el limite de 60/min y morian en un 429
  // silencioso.
  proxima_disponible: string | null;
  // Por que no se puede. 'lleno' = se acabaron los viajes del dia. 'sin_panga' =
  // el dia tiene espacio, pero ya no queda embarcacion donde quepa este grupo:
  // solo dos de la flota llevan mas de 3 personas.
  motivo_no_disponible: 'lleno' | 'sin_panga' | null;
};
```

y la función:

```ts
export const getCupo = (fecha: string, personas: number) =>
  request<Cupo>(`/api/cupo/?fecha=${fecha}&personas=${personas}`);
```

- [ ] **Step 2: Agrega la copia nueva a las dos dictionaries**

En `frontend/src/app/[lang]/dictionaries/es.json`, justo después de `"dayFullNotice"`:

```json
    "noBoatForGroupNotice": "Ese día todavía tiene espacio, pero ya no queda una panga para un grupo de {people} personas: solo dos de la flota llevan más de 3. Te asignamos automáticamente el {date}, la fecha más próxima con una disponible.",
```

En `frontend/src/app/[lang]/dictionaries/en.json`, en el mismo lugar:

```json
    "noBoatForGroupNotice": "That day still has room, but no boat left for a group of {people}: only two in the fleet carry more than 3. We've automatically moved you to {date}, the next date with one available.",
```

- [ ] **Step 3: Reconsulta al cambiar el número de personas y elige el mensaje**

En `frontend/src/components/checkout-view.tsx`, reemplaza el efecto de cupo completo:

```tsx
  // El cupo real se valida en el backend (al pagar), esto solo es feedback
  // adelantado: si el dia elegido ya no admite a este grupo, reasigna
  // automaticamente al dia mas proximo con espacio y avisa. Nunca bloquea el
  // flujo (ver docs/contexto-negocio.md — el checkout no debe poner trabas).
  //
  // Depende tambien de `people`: un dia puede tener lugares libres y aun asi no
  // poder recibir a un grupo de 4, porque solo dos pangas de la flota lo llevan.
  // Sin esa dependencia, subir el numero de personas dejaria al cliente en un dia
  // que ya no le sirve.
  useEffect(() => {
    const checkId = ++cupoCheckId.current;

    (async () => {
      let cupo;
      try {
        cupo = await getCupo(day, people);
      } catch {
        // Sin respuesta no se avisa nada: es ayuda adelantada, el cupo real lo
        // valida el backend al cobrar. Nunca debe trabar el checkout.
        return;
      }
      if (cupoCheckId.current !== checkId) return;
      if (cupo.disponible || !cupo.proxima_disponible) return;

      setDay(cupo.proxima_disponible);
      // Dos mensajes distintos porque son dos problemas distintos: al cliente de
      // 4 personas hay que decirle que el dia si tiene espacio pero no para su
      // grupo — si no, ve lugares libres y no entiende por que no puede.
      const plantilla =
        cupo.motivo_no_disponible === 'sin_panga'
          ? checkout.noBoatForGroupNotice
          : checkout.dayFullNotice;
      setDayFullNotice(
        plantilla
          .replace('{date}', formatDay(fromLocalISODate(cupo.proxima_disponible), lang))
          .replace('{people}', String(people))
      );
    })();
  }, [day, people, lang, checkout.dayFullNotice, checkout.noBoatForGroupNotice]);
```

- [ ] **Step 4: Verifica tipos y lint**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Esperado: sin errores. Si `tsc` se queja de que `noBoatForGroupNotice` no existe, es que falta la clave en una de las dos dictionaries (el tipo se infiere de una de ellas).

- [ ] **Step 5: Compila**

Run: `cd frontend && npm run build`
Esperado: build exitoso.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/checkout-view.tsx "frontend/src/app/[lang]/dictionaries/es.json" "frontend/src/app/[lang]/dictionaries/en.json"
git commit -m "feat(checkout): consultar el cupo por tamaño de grupo y decir por que no cabe"
```

---

## Task 10: La documentación deja de mentir

**Files:**
- Modify: `backend/CLAUDE.md:55`, `backend/CLAUDE.md:198-205`
- Modify: `docs/contexto-negocio.md` (sección Embarcaciones)

- [ ] **Step 1: Actualiza `backend/CLAUDE.md`**

Reemplaza la sección "Cupo diario":

```markdown
## Cupo diario

Motor unico en `apps/bookings/models.py`: `validar_cupo_diario(fecha, personas, excluir_pk=None)`,
llamado desde `Reserva.clean()`. Decide dos cosas y las distingue en el mensaje:

1. **Tope de viajes del dia** — `CupoDiario` de esa fecha, o `CUPO_MAXIMO_DEFAULT`.
2. **Que exista una panga donde quepa ese grupo** — `caben(grupos, capacidades)`
   empareja de mayor a menor los grupos ya vendidos mas el nuevo contra las
   capacidades a flote (`fleet.capacidades_disponibles(fecha)`). Un dia puede tener
   lugares libres y aun asi no admitir un grupo de 4: solo dos pangas de la flota
   llevan mas de 3 personas.

Los dos numeros son independientes a proposito: `CupoDiario` es un tope que decide
el negocio (por ejemplo, faltan capitanes) y `fleet.EmbarcacionNoDisponible` es que
panga fisicamente no sale ese dia.

El nucleo (`caben`, `motivo_sin_lugar`) es puro y no toca la base: lo comparten la
validacion, `/api/cupo/`, `proxima_fecha_disponible` y el comando `revisar_cupo`,
para que los cuatro no puedan decidir distinto.

Solo cuentan contra el cupo los estados en `ESTADOS_QUE_OCUPAN_CUPO`: una reserva
`pendiente_pago` no bloquea a otros clientes. Override manual de cupo por dia:
modelo `CupoDiario`.
```

En la lista de endpoints (línea ~55):

```markdown
- `GET /api/cupo/?fecha=YYYY-MM-DD&personas=N` — si cabe un grupo de N ese dia,
  solo informativo. `personas` es opcional (default 1). Responde ademas
  `motivo_no_disponible`: `'lleno'` (se acabaron los viajes del dia) o
  `'sin_panga'` (queda dia pero no embarcacion para ese grupo).
```

Y junto a los otros comandos de management:

```markdown
- `python manage.py revisar_cupo [--dias 90]` — dias ya vendidos que la flota real
  no puede operar. Las reservas anteriores al cupo por tamaño sobrevivieron
  intactas: la validacion corre al guardar.
```

- [ ] **Step 2: Actualiza `docs/contexto-negocio.md`**

En la sección de Embarcaciones, agrega:

```markdown
La flota es un techo fijo: **maximo 10 pangas, 8 de capacidad 3 y 2 de capacidad
5**. Algunos dias hay menos (mantenimiento, motor descompuesto), nunca mas. Esa
ausencia se captura en el admin, en "embarcaciones no disponibles": se registra
que panga falta un dia concreto, no cuantas quedan.

El cupo del dia no es un solo numero. Son dos condiciones: el tope de viajes que
decide el negocio (`CupoDiario`) y que exista una panga donde quepa cada grupo. Un
martes con dos viajes de 4 personas todavia tiene ocho lugares libres y aun asi no
puede recibir a un tercer grupo de 4.
```

- [ ] **Step 3: Commit**

```bash
git add backend/CLAUDE.md docs/contexto-negocio.md
git commit -m "docs: el cupo ahora depende del tamaño del grupo y de la flota del dia"
```

---

## Antes de desplegar (paso manual, bloqueante)

**Dar de alta las 10 pangas con su capacidad en el admin, antes de que este código llegue a producción.** Sin catálogo `Embarcacion` completo, `capacidades_disponibles` devuelve una lista corta y el sitio **deja de vender**. Es un fallo seguro y no silencioso —que es lo correcto— pero es un fallo.

Después del despliegue, correr una vez:

```bash
python manage.py revisar_cupo --dias 90
```

para encontrar los días ya vendidos que la flota real no puede operar y resolverlos a mano antes de que llegue la fecha.

## Fuera de alcance (confirmado en el spec)

- La agenda operativa (pieza 4): esto decide qué se puede *vender*, la agenda reparte lo ya vendido.
- Asignar automáticamente qué panga le toca a cada viaje.
- La capacidad cómoda (2 en las chicas): manda `capacidad_maxima`.
- Los capitanes no entran en el cálculo del cupo.
