# Capacidad real de la flota y cupo consciente del tamaño del grupo

Fecha: 2026-08-17
Piezas 2 y 3 de la cola de trabajo acordada. La pieza 1 (bajar el tope de
personas de 6 a 5) ya salió en el commit `29478f8`.

## El problema

El sistema vende viajes contando **cuántos** caben en un día, nunca **de qué
tamaño**. El cupo es un solo número: 10 viajes, o lo que diga el `CupoDiario` de
esa fecha.

La flota real no funciona así. Son 10 pangas como máximo: **8 de capacidad 3 y 2
de capacidad 5**. Un grupo de 4 o 5 personas solo cabe en dos de ellas.

De ahí sale una sobreventa que el motor de cupo actual no puede ver:

> Un martes ya tiene dos viajes de 4 personas. El cupo dice que quedan 8 lugares
> y es cierto — pero no para un tercer grupo de 4. Ese cliente reserva, paga, y
> el día del viaje no hay panga donde meterlo.

No es una condición de carrera ni un caso raro: es el comportamiento normal del
sistema. Ajustar el `CupoDiario` a mano no lo cubre, porque la web vende en
tiempo real, de madrugada, sin nadie mirando.

Hay un segundo hueco del mismo origen: algunos días hay **menos** pangas
disponibles (mantenimiento, motor descompuesto). Nunca más de 10 — la flota es
un techo fijo. Hoy no hay dónde registrar eso, así que el sistema sigue vendiendo
como si estuvieran las diez.

## Alcance

**Entra:**

- Representar la capacidad real de cada panga y poder dar una de baja.
- Registrar qué pangas no están disponibles un día concreto.
- Que el motor de cupo decida en función del tamaño del grupo.
- Que `/api/cupo/` y el checkout reaccionen a eso.

**No entra, a propósito:**

- **La agenda operativa** (pieza 4). Esta pieza decide qué se puede *vender*; la
  agenda reparte lo que ya se vendió. Mientras la agenda no exista, marcar una
  panga como no disponible se hace desde el admin del modelo nuevo.
- **Asignar automáticamente qué panga le toca a cada viaje.** El sistema
  garantiza que *existe* un reparto posible; cuál es lo decide una persona.
- **La capacidad cómoda.** De "8 de 2 a 3 personas" se toma el **3** como el
  número que manda. El 2 es criterio de venta —a quién le das cuál— y no una
  regla que deba impedir un cobro. Supuesto explícito; si el 2 debe limitar algo,
  es un cambio aparte.
- **Precio por clase de panga.** La tarifa es única y no varía (ver
  `docs/contexto-negocio.md`).

## Diseño

### 1. La flota (`fleet.Embarcacion`)

`capacidad_maxima` ya existe y ya es el número que manda. Dos cambios:

- **`activa = BooleanField(default=True)`** — baja larga (vendida, fuera de
  servicio indefinido). No se borra: `Reserva.embarcacion` es `PROTECT` y borrar
  dejaría viajes históricos sin panga. Mismo patrón que `Vendedora.activo`.
- **Las etiquetas de `Clase` pierden el número.** Hoy dicen
  `Chica (máx. 3 personas)` y `Grande (máx. 6 personas)`. La segunda es falsa, y
  el problema de fondo es que la capacidad está escrita en dos lugares que pueden
  discrepar. Quedan `Chica` y `Grande` — el nombre que usa el negocio, sin cifra.
  El número vive solo en `capacidad_maxima`.

`__str__` pasa a `Lupita (Grande, máx. 5)`, así el selector de la agenda muestra
la capacidad donde se necesita.

`Clase` **no se elimina**: el negocio piensa en chica y grande, y la copia del
sitio las nombra así. Solo deja de cargar un dato que no le toca.

### 2. Disponibilidad por día (`fleet.EmbarcacionNoDisponible`)

Modelo nuevo:

| Campo | Tipo | Nota |
|---|---|---|
| `fecha` | `DateField` | |
| `embarcacion` | `FK(Embarcacion, PROTECT)` | |
| `motivo` | `CharField(blank=True)` | "Mantenimiento", "motor" |
| `registrado_por` | `FK(User, SET_NULL, null=True)` | |
| `creado_en` | `DateTimeField(auto_now_add=True)` | |

`unique_together = ('fecha', 'embarcacion')`.

Se registra **qué falta**, no cuántas hay. Es dato real y verificable ("la Lupita
está en mantenimiento el jueves") en vez de un conteo abstracto que nadie puede
auditar después. Sin registro para una fecha, está la flota activa completa.

Esto deja `CupoDiario` como lo que ya es: un tope de viajes que el negocio
decide, independiente de la disponibilidad física. Son dos cosas distintas y
meterlas en un solo número las volvería imposibles de separar. Un día puede tener
las 10 pangas y un `CupoDiario` de 6 porque no hay capitanes; o el tope default
de 10 y solo 7 pangas a flote.

### 3. El motor de cupo

En `apps/fleet/models.py`, porque es una pregunta sobre la flota y nada más:

```python
def capacidades_disponibles(fecha):
    """Capacidad de cada panga que puede salir ese día, de mayor a menor."""
```

Pangas `activa=True` menos las registradas como no disponibles esa fecha.

`bookings` ya depende de `fleet` (la FK de `Reserva.embarcacion`) y `fleet` no
depende de `bookings`, así que la dirección del import no crea ciclo. Lo que sí
importa es que la flota no aprenda nada de reservas: `capacidades_disponibles`
responde qué hay a flote, no qué está vendido.

En `apps/bookings/models.py`, junto al motor que ya existe:

```python
def caben(grupos, capacidades):
    """¿Hay forma de darle a cada grupo una panga donde quepa?

    Se emparejan de mayor a menor: el grupo más grande con la panga más grande.
    Si a algún grupo le toca una panga más chica que él, no hay reparto posible —
    y no lo hay con ningún otro orden, porque cualquier reparto válido tendría que
    darle a ese grupo una panga al menos igual de grande, y todas las de arriba ya
    están ocupadas por grupos aún mayores.
    """
    if len(grupos) > len(capacidades):
        return False
    return all(g <= c for g, c in zip(grupos, capacidades))
```

Las dos listas llegan ordenadas de mayor a menor. Con 10 pangas el costo es
irrelevante, pero importa que el criterio sea **exacto y no una heurística**:
decide si se cobra o no.

Con la flota actual, esto se lee como "máximo 2 grupos de 4 o 5, máximo 10 en
total" — sin que ninguno de esos dos números esté escrito en el código. Comprar
una panga de 8 no obliga a tocar nada.

`validar_cupo_diario(fecha, personas, excluir_pk=None)` gana el parámetro
`personas` y hace dos comprobaciones con mensajes distintos, porque son dos
problemas distintos para quien los lee:

1. **Tope de viajes** — `len(grupos) > cupo_maximo_del_dia(fecha)` →
   *"No hay cupo disponible para el 20/09: se alcanzó el máximo de viajes del día."*
   (el mensaje de hoy, sin cambios)
2. **No hay panga para ese grupo** — `not caben(...)` →
   *"No queda panga para un grupo de 4 personas el 20/09. Las de mayor capacidad ya están comprometidas."*

El orden importa: si el día está lleno a secas, ese es el mensaje útil.

`bloquear_cupo_del_dia(fecha)` se sigue tomando **antes de contar**, igual que
hoy. La protección contra dos clientes pagando el último lugar a la vez no
cambia; ahora además cubre el último lugar *de ese tamaño*.

`Reserva.clean()` pasa `self.numero_personas`. Sigue siendo el único punto de
entrada: web, admin y shell validan igual.

### 4. `proxima_fecha_disponible`

Hoy busca el primer día de los próximos 90 con `ocupadas < tope`, en **dos
consultas totales**. Esa propiedad no se puede perder: la versión anterior
preguntaba día por día, hasta 90 peticiones seguidas que morían en el throttle de
60/min justo en temporada alta.

Pasa a `proxima_fecha_disponible(desde, personas, dias=90)` y sigue en un número
fijo de consultas — cuatro:

1. Reservas que ocupan cupo en el rango, con `fecha` y `numero_personas`.
2. `CupoDiario` del rango.
3. `EmbarcacionNoDisponible` del rango, con su `embarcacion`.
4. Las pangas activas y su capacidad.

Con eso en memoria, el bucle de 90 días arma los grupos y las capacidades de cada
fecha y llama a `caben`. Cero consultas dentro del bucle.

### 5. API y frontend

`GET /api/cupo/?fecha=YYYY-MM-DD&personas=N`

- `personas` es **opcional, default 1**: sin él la respuesta es la de hoy y nada
  que llame a la API vieja se rompe.
- `disponible` pasa a significar "cabe un grupo de N ese día".
- `proxima_disponible` pasa a ser "el próximo día donde cabe un grupo de N".
- Se agrega `motivo_no_disponible`: `'lleno'` (tope de viajes) o `'sin_panga'`
  (no queda panga de ese tamaño), o `null`. Sin esto el frontend no puede decir
  la verdad de por qué no se puede.

Frontend:

- `getCupo(fecha)` → `getCupo(fecha, personas)`.
- El checkout ya consulta el cupo y ya mueve al cliente a la próxima fecha con
  espacio. Lo que cambia es que ahora **también hay que volver a consultar cuando
  el cliente cambia el número de personas**, no solo la fecha.
- Copia nueva en las dos dictionaries: el mensaje de "no queda panga para tu
  grupo" no puede ser el mismo que "ese día ya está lleno". Al cliente de 4
  personas hay que decirle que el día sí tiene espacio pero no para su grupo — si
  no, va a ver lugares libres y no entender por qué no puede.

## Datos que ya existen

- `Embarcacion.activa` con default `True`: las filas actuales quedan activas. Sin
  riesgo.
- Las etiquetas de `Clase` cambian sin tocar datos (`AlterField` sobre `choices`).
  Los valores guardados siguen siendo `chica` y `grande`.
- **La flota hay que capturarla.** El sistema no sabe hoy cuántas pangas hay: si
  el catálogo `Embarcacion` está vacío o incompleto, `capacidades_disponibles`
  devuelve una lista corta y el sitio **deja de vender**. Es un fallo seguro y no
  silencioso, que es lo correcto, pero hay que dar de alta las 10 pangas con su
  capacidad **antes** de desplegar.
- Puede haber días ya vendidos que no son operables con la flota real. La
  validación corre al guardar, así que esas reservas sobreviven intactas. Se
  agrega `manage.py revisar_cupo [--dias 90]` (en `apps/bookings`, junto a
  `conciliar_pagos`), que lista los días donde el reparto no cierra, para
  resolverlos a mano antes de que llegue la fecha.

## Pruebas

Motor:

1. `caben` con lista vacía de grupos: cabe.
2. Más grupos que pangas: no cabe.
3. Tres grupos de 4 con dos pangas de 5 y ocho de 3: no cabe.
4. Dos grupos de 4 y ocho de 3 con la flota completa: cabe (el caso apretado que
   sí es operable).
5. Un grupo de 6 con una panga de 5: no cabe.
6. `caben` no depende del orden de llegada: los mismos grupos en otro orden dan el
   mismo resultado.
7. `capacidades_disponibles` excluye las inactivas.
8. `capacidades_disponibles` excluye las marcadas no disponibles **solo ese día**,
   y las devuelve el día siguiente.

Validación:

9. Reservar un tercer grupo de 4 el mismo día se rechaza, con el mensaje de
   `sin_panga` y no el de día lleno.
10. Un grupo de 2 el mismo día **sí** se acepta: el día no está lleno, solo se
    acabaron las pangas grandes.
11. Un día lleno a secas da el mensaje de tope de viajes, no el de panga.
12. Un `CupoDiario` de 3 corta a los 3 viajes aunque haya 10 pangas.
13. Editar una reserva ya guardada no se cuenta a sí misma (`excluir_pk`).
14. Una reserva cancelada libera su panga.

API y frontend:

15. `/api/cupo/` sin `personas` responde igual que antes.
16. `/api/cupo/?personas=4` marca `disponible: false` y `motivo_no_disponible:
    'sin_panga'` en un día con las dos grandes tomadas, y `true` para `personas=2`
    en ese mismo día.
17. `proxima_disponible` con `personas=4` salta los días sin panga grande.
18. `proxima_fecha_disponible` sobre 90 días no crece en número de consultas
    (`assertNumQueries`). Es el test que protege el arreglo del throttle.

Comando:

19. `revisar_cupo` encuentra un día ya vendido que no es operable y no reporta
    nada cuando todos cierran.

## Riesgos y lo que queda abierto

- **La flota hay que capturarla antes de desplegar**, o el sitio deja de vender.
  Es el único paso manual de esta pieza y es bloqueante.
- **La capacidad cómoda (2 en las chicas) no se modela.** Supuesto declarado
  arriba. Si resulta que vender 3 personas en una panga chica es incómodo de
  verdad, el arreglo no es un número nuevo sino bajar `capacidad_maxima` a 2.
- **Los capitanes no entran en el cálculo.** Un día puede tener 10 pangas y 6
  capitanes. Hoy nada lo mira. La regla de "un capitán, un viaje por día" está
  acordada para la pieza 4 (agenda), pero el *cupo* seguirá sin saber de
  capitanes hasta que se decida modelarlo — mismo patrón que las pangas, y mismo
  hueco mientras tanto.
- **Registrar pangas no disponibles vive en el admin crudo** hasta que exista la
  agenda. Funciona, pero no es cómodo.
