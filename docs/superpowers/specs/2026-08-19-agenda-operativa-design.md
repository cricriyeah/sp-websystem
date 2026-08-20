# Agenda operativa

Fecha: 2026-08-19
Última pieza de la cola de trabajo. Las anteriores —tope de 5 personas, capacidad
real de la flota y cupo por tamaño de grupo— ya están en `main` y desplegadas.

## El problema

El sistema sabe vender un viaje y sabe cobrarlo. No sabe repartirlo.

Hoy, para asignar la panga y el capitán de un viaje, hay que entrar al listado de
Reservas, abrir cada reserva, cambiar dos campos y guardar. Una por una. Con ocho
o diez viajes en un fin de semana eso son veinte o treinta clics para un trabajo
que en la cabeza de quien lo hace es una sola decisión: *qué panga le toca a cada
quién mañana*.

El listado de Reservas tampoco ayuda a tomar esa decisión. Muestra todas las
reservas de todos los estados, con las columnas del cobro, del deslinde y de la
atribución de venta. Nada de eso importa a las 8 de la noche cuando lo único que
falta es decidir quién sale en la Lupita.

## Alcance

**Entra:**

- Una pantalla que liste los viajes que hay que repartir y deje asignar panga y
  capitán sin entrar a cada uno.
- Que poner la panga mueva el estado solo.
- Que el sistema impida darle la misma panga —o el mismo capitán— a dos viajes
  del mismo día.
- Que se vea de lejos lo que está mal: un viaje asignado sin capitán, y uno cuya
  fecha ya pasó y sigue sin repartir.

**No entra, a propósito:**

- **Asignar automáticamente.** El sistema garantiza que el reparto es posible
  (eso lo hace el motor de cupo, desde la venta); cuál panga le toca a quién lo
  decide una persona, que sabe cosas que el sistema no —quién viene con niños,
  qué capitán se lleva bien con qué cliente.
- **Los capitanes en el motor de cupo.** Un día puede tener 10 pangas y 6
  capitanes, y el cupo seguirá sin saberlo. La agenda hace cumplir "un capitán,
  un viaje por día" al asignar; el *cupo* no lo mira al vender. Es el mismo hueco
  que ya se declaró en el spec del cupo y sigue abierto a propósito.
- **Reprogramar desde la agenda.** Cambiar la fecha de un viaje tiene su propia
  regla (48 horas de anticipación) y su propia pantalla. La agenda reparte lo que
  ya está vendido para el día que está vendido.
- **Notificar al cliente su panga o su capitán.** No se le promete una panga
  concreta y no hay por qué empezar a hacerlo.

## Diseño

### 1. El modelo proxy (`bookings.Agenda`)

Proxy sobre `Reserva`, el mismo patrón que ya usa `CheckoutAbandonado`: es la
misma fila vista con otro filtro y otras columnas, no un modelo nuevo. Si un
viaje se cancela, desaparece de la agenda solo.

```python
class Agenda(Reserva):
    class Meta:
        proxy = True
        ordering = ['fecha', 'hora']
        verbose_name = 'agenda'
        verbose_name_plural = 'agenda'
```

Orden por fecha y hora ascendente: lo que sale primero, primero. Es lo contrario
del listado de Reservas (`-fecha`), que es un historial y por eso enseña lo más
reciente arriba.

El orden tiene un efecto que conviene: los viajes atrasados, cuando los haya,
quedan hasta arriba de la lista por ser los más viejos. Lo que está mal aparece
primero sin que nadie tenga que ordenarlo.

Lista **solo** `pagada` y `asignada`. Una cancelada no se reparte; una completada
ya salió; una `pendiente_pago` no es una reserva todavía y vive en la pantalla de
checkouts abandonados.

### 2. La transición de estado

Vive en `Reserva.save()`, no en el admin, para que valga igual desde el shell o
desde cualquier pantalla futura:

- `pagada` + tiene embarcación → `asignada`
- `asignada` + se le quita la embarcación → `pagada`

Ningún otro estado se toca. `completada` y `cancelada` quedan donde están aunque
se les mueva la panga: son estados finales que decide una persona, no un efecto
secundario de editar un campo.

**Poner la panga basta para dar el viaje por asignado; el capitán no se exige.**
Es una decisión tomada con el riesgo a la vista: puede llegar la mañana de la
salida con un viaje en `asignada` y sin capitán. La compensación acordada es que
eso se marque en rojo y sea imposible de no ver (ver sección 4).

### 3. Una salida por panga y por capitán al día

Regla nueva del negocio: una panga hace **un solo viaje por día**, y un capitán
también. Las salidas son de 5 a 7am y el viaje dura de 6 a 7 horas, así que
escalonar dos salidas con la misma panga no existe.

Va en `Reserva.clean()`, junto al resto de las reglas del negocio, para que la
bloquee también el admin normal y el shell — no solo la agenda.

Cuentan los estados que ya ocupan cupo (`ESTADOS_QUE_OCUPAN_CUPO`: `pagada`,
`asignada`, `completada`). Una reserva cancelada suelta su panga y su capitán.

Dos mensajes distintos, porque son dos problemas distintos para quien los lee:

> La Lupita ya tiene un viaje el 20/09. Una panga hace una sola salida por día.

> Juan Pérez ya tiene un viaje el 20/09. Un capitán hace una sola salida por día.

**Esto contradice el código y la documentación actuales.** `backend/CLAUDE.md`
dice hoy: *"La doble asignacion de panga/capitan no se valida a proposito: la
vendedora puede querer sacar dos viajes con la misma panga escalonando la salida.
Es criterio suyo, no del sistema."* Esa nota queda falsa y se corrige en la misma
tarea que introduce la validación.

La regla ya está medio vigente sin que nadie la escribiera: el motor de cupo
exige `len(grupos) <= len(capacidades)`, o sea, ya vende como si cada panga
hiciera una sola salida diaria. La agenda no la estrena, la hace cumplir del otro
lado.

### 4. La pantalla

**Columnas:** fecha, hora, cliente, personas, embarcación, capitán, aviso.

Embarcación y capitán se editan en el propio listado (`list_editable`), que es el
punto entero de la pantalla. El nombre del cliente es la liga a la reserva
completa, para cuando haga falta ver el teléfono o los extras.

El selector de embarcación muestra `Lupita (Grande, máx. 5)` — el `__str__` que
se cambió en la pieza del cupo justamente para esto. Con la capacidad enfrente no
hay que acordarse de cuál panga lleva cuántos.

**La columna de aviso, en rojo:**

- **SIN CAPITÁN** — el viaje está `asignada` y no tiene capitán.
- **ATRASADO** — la fecha ya pasó y el viaje sigue en `pagada`. Es un viaje
  cobrado que nadie repartió.

Un viaje en `pagada`, sin panga y con fecha futura **no** se marca. Eso no es un
error: es el trabajo pendiente, y es exactamente a lo que se viene a esta
pantalla. Marcarlo en rojo volvería roja toda la agenda y el rojo dejaría de
significar algo.

### 5. Los dos modos son un filtro

Un `SimpleListFilter` llamado **Cuándo**, con dos opciones:

- **Mañana** — cerrar el día. Los viajes de mañana y nada más. Es el modo de la
  tarde-noche anterior: si la salida es a las 6am, a esa hora ya nadie está
  asignando pangas.
- **Próximos 7 días** — repartir la semana. De hoy a siete días, **más** los
  viajes ya pasados que siguen en `pagada` sin panga. Es el modo por defecto.

Los atrasados entran a propósito. Un viaje que se cobró, ya pasó y nadie repartió
es un error que hay que ver; esconderlo no lo arregla, solo garantiza que nadie
se entere.

Son dos presets del mismo filtro y no dos pantallas: la diferencia entre "cerrar
el día" y "repartir la semana" es qué días miras, nada más.

### 6. Permisos

Un modelo proxy tiene sus propios permisos en Django, así que hay que dárselos a
la vendedora en `setup_roles` o la agenda simplemente no le aparece:

```python
('bookings', 'agenda', ['change', 'view']),
```

Sin `add` ni `delete`: una reserva se crea vendiendo y se cancela, no se borra ni
se inventa desde aquí.

**Y un hueco heredado que se cierra aquí.** La pieza del cupo agregó
`fleet.EmbarcacionNoDisponible` —el registro de qué panga no sale un día— pero no
le dio permiso a la vendedora. Hoy solo un jefe puede marcar que la Lupita está
en mantenimiento el jueves, y eso es trabajo diario de ella:

```python
('fleet', 'embarcacionnodisponible', ['add', 'change', 'delete', 'view']),
```

Con `delete`, que es la excepción razonable: si marcó una panga fuera por error,
o el motor se arregló antes de lo previsto, tiene que poder deshacerlo. No es un
registro histórico, es el estado de un día.

## Lo que la pantalla no va a hacer bien, y se acepta

**El guardado es todo o nada.** El listado editable de Django manda todas las
filas tocadas en un solo envío. Si una falla la validación —asignar la misma
panga dos veces, por ejemplo— no se guarda ninguna y Django marca cuál falló.
No es el comportamiento ideal, pero cambiarlo significa escribir la pantalla a
mano, que es justo lo que este diseño evita.

**No hay vista de calendario.** Es una tabla ordenada por fecha y hora, con los
días uno tras otro. Para diez viajes en una semana, una tabla se lee más rápido
que una cuadrícula.

## Datos que ya existen

Nada que migrar y nada que auditar. El sitio no se ha lanzado: todo lo que hay en
producción son pruebas. Si esto se implementara después del lanzamiento habría
que revisar los viajes ya asignados en busca de pangas repetidas el mismo día,
porque la validación corre al guardar y una fila vieja sobrevive intacta — hoy
ese trabajo no aplica.

## Pruebas

Modelo y estado:

1. La agenda lista `pagada` y `asignada`.
2. La agenda no lista `pendiente_pago`, `cancelada` ni `completada`.
3. Poner la embarcación en una reserva `pagada` la deja `asignada`.
4. Quitarle la embarcación a una `asignada` la regresa a `pagada`.
5. El capitán solo no cambia el estado: sin panga sigue `pagada`.
6. Una `completada` con embarcación no se mueve de estado.
7. Una `cancelada` con embarcación no se mueve de estado.

La regla de una salida por día:

8. La misma embarcación en dos viajes del mismo día se rechaza, con el mensaje
   de la panga.
9. El mismo capitán en dos viajes del mismo día se rechaza, con el mensaje del
   capitán.
10. La misma embarcación en dos días distintos se acepta.
11. Una reserva cancelada suelta su embarcación: otro viaje del mismo día la
    puede usar.
12. Editar una reserva ya asignada no se cuenta contra sí misma.
13. La regla aplica también desde el admin de Reservas, no solo desde la agenda.

Los modos:

14. El modo *Mañana* trae los viajes de mañana y no los de hoy ni los de pasado
    mañana.
15. El modo *Próximos 7 días* trae los de la semana.
16. El modo *Próximos 7 días* trae además un viaje atrasado que sigue en
    `pagada`.
17. El modo *Próximos 7 días* **no** trae un viaje atrasado que ya está
    `asignada`: ese se repartió, aunque haya pasado.

Los avisos:

18. Un viaje `asignada` sin capitán sale marcado.
19. Un viaje `asignada` con capitán no sale marcado.
20. Un viaje `pagada` con fecha pasada sale marcado como atrasado.
21. Un viaje `pagada` con fecha futura no sale marcado.

Permisos:

22. La vendedora entra a la agenda y puede editar.
23. La vendedora no puede agregar ni borrar desde la agenda.
24. La vendedora puede marcar una embarcación como no disponible.

## Riesgos y lo que queda abierto

- **Un viaje puede salir sin capitán.** Es el riesgo aceptado a cambio de que
  poner la panga baste para dar el viaje por asignado. El aviso en rojo es toda
  la mitigación que hay.
- **El cupo sigue sin saber de capitanes.** Se pueden vender diez viajes un día
  en que solo hay seis capitanes disponibles, y nadie se entera hasta que se
  reparte. Modelar la disponibilidad de capitanes sería el mismo patrón que ya
  tienen las pangas (`EmbarcacionNoDisponible`), y queda para cuando el negocio
  diga que hace falta.
- **El guardado todo-o-nada** puede frustrar en una tanda grande. Si resulta
  molesto en la práctica, la salida no es parchar el listado sino reconsiderar la
  pantalla, que es una decisión más grande que esta.
