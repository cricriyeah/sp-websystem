# ARCH: Notificaciones persistentes del backoffice

Fecha: 2026-10-26
Autor: architect (great_cto)
Estado: PROPUESTO — pendiente de luz verde del dueño antes de implementar
Lector objetivo: el senior-dev que implementará esto en Django/Unfold, sin contexto previo de la feature.

> Este documento es el contrato de diseño. No hay código de producto aquí. El
> senior-dev lo implementa tarea por tarea; qa verifica cada REQ-N; seguridad
> revisa RLS y el manejo de texto. Español de México en toda la interfaz.
> Esquinas rectas o círculo, sin sombras ni degradados (regla de marca del dueño).

---

## 1. Problema

Hoy el backoffice es mudo. Tres síntomas, en palabras del dueño:

1. **El éxito no se ve.** Al guardar una asignación de panga y capitán no aparece
   nada que diga "correo enviado, panga y capitán asignados".
2. **El fallo tampoco se ve.** Si el correo de asignación falla, no dice que falló
   ni por qué. (Esto se corrigió parcialmente con `AvisoDeAsignacionMixin`, pero
   solo como mensaje efímero verde/rojo y solo para asignación.)
3. **No hay memoria.** Si llega una reserva y nadie la vio, o si alguien hizo algo
   y no recuerda qué, no queda registro consultable. El toast de "reserva nueva"
   (`static/tenancy/avisos.js`) es efímero: se cierra y se perdió.

El admin de Django es HTML renderizado en el servidor sin conexión abierta con el
navegador (ya probado: no vale la pena WebSockets para este volumen — 4 empresas,
1-2 vendedoras cada una). Ya existe un sondeo cada 10 s para el toast de reservas
nuevas; se reutiliza.

## 2. Qué se construye (alcance)

- Un **registro persistente de notificaciones por empresa**: qué pasó, quién,
  cuándo, nivel (éxito/aviso/error), motivo si falló, enlace al objeto.
- Una **función única `avisar(request, nivel, texto, ...)`** que muestra el mensaje
  verde/ámbar/rojo de Django **y** guarda la notificación. Todos los procesos hoy
  callados la usan.
- Un **estado de lectura por persona** (no una marca compartida).
- Una **campana con contador de no leídas** en el header del backoffice, cuyo
  número viaja en la misma respuesta del sondeo de 10 s que ya existe.
- Una **pantalla de lista** con filtro por tipo/nivel y "marcar como leídas".
- **Retención 90 días** con un management command y su cron en Render.

### Non-goals (fuera de alcance, explícito)

- **No** notificaciones en tiempo real (nada de WebSockets/SSE/Channels/Redis). El
  retraso de hasta ~10 s del sondeo actual es aceptado.
- **No** notificaciones al cliente final (eso vive en `apps/notifications`, correo
  y WhatsApp; esta feature es solo interna del backoffice).
- **No** notificaciones push al navegador ni al teléfono del operador.
- **No** preferencias por usuario (qué tipos recibir): todos ven todo lo de su empresa.
- **No** un segundo canal de auditoría: el History nativo de Django sigue siendo la
  auditoría formal de cambios de reserva. Esto es un *feed operativo*, no un log legal.
- **No** marca de lectura compartida entre usuarios (descartado por el dueño).

## 3. Decisión de arquitectura y alternativas

### 3.1 Dónde viven el modelo y `avisar()` — en `apps/tenancy`

**Decisión:** `Notificacion`, `LecturaNotificacion`, `avisar()` y el command de
limpieza viven en **`apps/tenancy`**.

**Por qué.** Es una preocupación transversal, acotada por empresa (RLS), que deben
poder invocar `bookings`, `payments` y `finance`. `tenancy` es la app base: todos la
importan, ella no importa a ninguna app de producto. Esto evita import circular
(p. ej. si viviera en `bookings`, `payments→bookings` ya existe pero
`bookings`→`payments` no debe nacer). El modelo **no** tiene FK a `Reserva` (el
enlace al objeto es un string de URL, ver 4.1), así que no arrastra `bookings`.
Además `tenancy` ya tiene el guardarraíl de RLS (`tests_rls.py`,
`test_guardarrail_toda_tabla_con_empresa_tiene_politica`), que **exige automáticamente**
una política a cualquier tabla nueva con `empresa_id`.

**Alternativas consideradas:**

- **App nueva `apps/avisos` (o `apps/notificaciones`)** — rechazada. (a) Choca de
  nombre: ya existe `apps/bookings/avisos.py` y la app `apps/notifications`
  (correos al cliente); tener `notifications` y `notificaciones` a una letra de
  distancia es una trampa de lectura. (b) Scaffolding extra (AppConfig,
  INSTALLED_APPS, migraciones 0001, duplicar el guardarraíl de RLS) sin beneficio
  de aislamiento real: la feature ya depende de `tenancy` para Empresa/scope/RLS.
- **En `apps/bookings`** — rechazada. `avisar()` sería importado por `payments` y
  `finance` (ya dependen de bookings, ok) pero el día que `bookings` necesite
  notificar algo que nazca en `payments` aparece el riesgo de ciclo. `tenancy` no
  tiene ese riesgo por construcción.

### 3.2 Cómo persiste `avisar()` — escritura **en línea** en la transacción y el alcance actuales

Esta es la decisión más delicada y la que más fácil se implementa mal. (Triage
escéptico aplicado abajo, §3.3.)

**Decisión:** `avisar()` escribe la `Notificacion` **sincrónicamente, dentro de la
transacción y el alcance de empresa que estén activos en ese momento** — NO usa
`transaction.on_commit` por su cuenta.

**Consecuencias (correctas):**

- En un guardado del admin, la escritura ocurre dentro del `atomic` que el
  middleware ya abrió (`EmpresaScopeMiddleware` → `scope.con_empresa`). El `SET
  LOCAL app.current_empresa_id` está activo, así que la política RLS `WITH CHECK`
  pasa (la notificación lleva la misma empresa del alcance). Si la acción
  **hace commit**, la notificación de éxito persiste con ella; si la acción **hace
  rollback** (p. ej. `CupoAgotadoAlGuardar`), la notificación de éxito se deshace
  también — correcto: no se afirma un éxito que no ocurrió.
- En los disparadores post-commit que ya existen (el correo de asignación en
  `signals._mandar`, la confirmación en `transferencia._avisar_al_cliente`, el
  webhook de pago), el llamador **ya corre dentro de su propio
  `scope.con_empresa(empresa)`** (reabierto con el `empresa_id` capturado como
  entero). Ahí la escritura en línea también pasa RLS sin trabajo extra.

**Por qué NO `transaction.on_commit` dentro de `avisar()`:** el sistema ya
documenta (en `scope.py` y `signals.py`) que `SET LOCAL` muere en el COMMIT y que
los callbacks de `on_commit` corren cuando el alcance ya se está desarmando; un
`INSERT` ahí, sin reabrir `con_empresa`, cae en la rama no-op de `_con_alcance`,
no emite `SET LOCAL`, y RLS lo rechaza con **cero filas en silencio** (el bug N1
original). Meter esa maquinaria dentro de `avisar()` — que se llamará desde ~8
sitios — multiplica la superficie de ese error. La escritura en línea lo evita por
completo para el camino común.

**Regla para el senior-dev (dónde llamar `avisar()`):**
- Éxito → después de que la mutación tuvo éxito (en `save_model` tras
  `super().save_model(...)`, o en la acción tras mutar). Persiste al commit.
- Fallo que fue atrapado y revirtió un savepoint → en el `except`, **fuera** del
  savepoint fallido (mismo punto donde ya se muestra el mensaje rojo). Persiste.
- Disparador sin pantalla (webhook, señal, hilo) → usa el primitivo
  `registrar_notificacion(empresa, ...)` **dentro** del `con_empresa(empresa)` que
  ya tienes abierto (ver 4.3). No pases `request`.

### 3.3 Triage escéptico de 3.2 (trade-off vinculante: en línea vs on_commit)

- **Ronda 1 (¿es real la premisa del landmine RLS?).** VÁLIDO. Verificado en
  `apps/tenancy/scope.py` L24-33 (docstring N1) y `apps/bookings/signals.py`
  L75-80: el `on_commit` captura `empresa_id` entero y reabre `con_empresa` justo
  por esto. El riesgo de cero-filas-en-silencio existe y está documentado en el
  propio repo.
- **Ronda 2 (¿la escritura en línea sí pasa RLS en el admin?).** VÁLIDO.
  `EmpresaScopeMiddleware.__call__` (L32-34) envuelve todo el request en
  `resolver_membresia_o_403` → `con_empresa`/`como_operador_plataforma`, que emite
  el `SET LOCAL`. Un `INSERT` con `empresa = empresa_actual(request)` satisface
  `WITH CHECK (empresa_id = current_setting(...) OR operador='on')`.
- **Ronda 3 (¿qué no vimos?).** El caso del rollback: una notificación de éxito
  escrita en línea y luego revertida. Concluimos que ese comportamiento es
  **deseado**, no un defecto (no persistir éxitos que no ocurrieron). El único
  hueco real —"quiero registrar el fallo aunque la acción revierta"— se cubre
  llamando `avisar()` en el `except`, fuera del savepoint.
- **Árbitro:** VÁLIDO, confianza 100% (3/3). La escritura en línea es correcta y
  más simple; `on_commit` se mantiene SOLO donde ya vive (los envíos de correo
  post-commit), y esos llamadores invocan `registrar_notificacion` desde su
  `con_empresa` ya abierto.

## 4. Modelo de datos

Ambos modelos llevan `empresa_id` y, por tanto, **el guardarraíl
`test_guardarrail_toda_tabla_con_empresa_tiene_politica` exigirá su política RLS**
automáticamente (ver §5). No hay dinero en columnas (los montos aparecen solo como
texto), así que la regla de centavos-enteros no aplica. Timestamps tz-aware por
`USE_TZ`. No son entidades importables desde un incumbente → `source_ref` /
`import_batch_id` de `migration-ready-schema` no aplican (motivo: feed interno
generado por el propio sistema).

### 4.1 `Notificacion`

```python
class Notificacion(models.Model):
    class Nivel(models.TextChoices):
        EXITO = 'exito', 'Éxito'
        AVISO = 'aviso', 'Aviso'
        ERROR = 'error', 'Error'

    class Tipo(models.TextChoices):
        ASIGNACION    = 'asignacion',    'Asignación de panga/capitán'
        RESERVA_NUEVA = 'reserva_nueva', 'Reserva nueva pagada'
        TRANSFERENCIA = 'transferencia', 'Pago por transferencia'
        COBRO_EFECTIVO= 'cobro_efectivo','Cobro en efectivo'
        REEMBOLSO     = 'reembolso',     'Reembolso'
        CANCELACION   = 'cancelacion',   'Cancelación'
        CAMBIO_FECHA  = 'cambio_fecha',  'Cambio de fecha'
        OTRO          = 'otro',          'Otro'

    empresa      = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='notificaciones')
    nivel        = models.CharField(max_length=10, choices=Nivel.choices)
    tipo         = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRO)
    texto        = models.CharField(max_length=300)          # qué pasó — TEXTO PLANO
    motivo       = models.CharField(max_length=300, blank=True, default='')  # por qué falló (opcional)
    enlace_url   = models.CharField(max_length=300, blank=True, default='')  # ruta relativa del admin
    enlace_texto = models.CharField(max_length=40,  blank=True, default='')  # p. ej. "Ver reserva"
    actor        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')  # None = sistema/webhook
    creado_en    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en', '-pk']
        verbose_name = 'notificación'
        verbose_name_plural = 'notificaciones'
        indexes = [
            models.Index(fields=['empresa', 'creado_en'], name='notif_empresa_creado'),
            models.Index(fields=['empresa', 'tipo'],       name='notif_empresa_tipo'),
        ]
```

Decisiones de campo:
- **`enlace_url` es un string, no una FK ni `GenericForeignKey`.** Razón: el objeto
  enlazado puede borrarse (una reserva se cancela, no se borra, pero un día podría);
  un string degrada de forma elegante (enlace muerto, no un 500), evita el costo de
  un GFK bajo RLS, y es exactamente lo que ya hace el toast (`reverse('admin:...')`).
- **`texto` y `motivo` separados.** `texto` = qué pasó ("No se pudo enviar el correo
  de asignación"); `motivo` = por qué ("Resend respondió 402"). El mensaje de Django
  concatena ambos; la lista puede mostrar el motivo en segunda línea atenuada.
- **`actor` con `SET_NULL`.** Si se borra la cuenta, la notificación sobrevive sin
  dueño en vez de arrastrar el borrado. `None` = evento del sistema (webhook de Stripe).
- **`texto` como `CharField(300)`** y no `TextField`: acota el tamaño del feed y es
  más que suficiente para una frase.

### 4.2 `LecturaNotificacion` (lectura por persona)

```python
class LecturaNotificacion(models.Model):
    empresa      = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name='+')  # denormalizada para RLS
    notificacion = models.ForeignKey(Notificacion, on_delete=models.CASCADE, related_name='lecturas')
    usuario      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    leida_en     = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['notificacion', 'usuario'], name='lectura_unica_por_usuario'),
        ]
        indexes = [
            models.Index(fields=['usuario', 'notificacion'], name='lectura_usuario_notif'),
        ]
```

**Por qué una tabla de lecturas por fila y no una marca de agua (high-water mark):**
el dueño pidió explícitamente "tabla de lecturas por usuario, no una marca
compartida". Además, con filtro por tipo en la lista, "marcar como leídas" debe
poder marcar **exactamente las filas mostradas** (p. ej. solo los errores); una
marca de agua por usuario (`leido_hasta=timestamp`) no puede representar eso. El
costo O(usuarios × notificaciones) está acotado por la retención de 90 días y el
volumen minúsculo (≈4-8 usuarios). Las filas de lectura **se borran en cascada** con
su notificación, así que no sobreviven al purgado.

- `empresa` denormalizada: así aplica la política RLS estándar `tenancy_alcance`
  (idéntica a `MovimientoDinero`), y el guardarraíl la exige igual. Se setea desde
  `notificacion.empresa` al escribir.
- `UniqueConstraint(notificacion, usuario)`: "marcar como leídas" usa
  `bulk_create(..., ignore_conflicts=True)` → idempotente, dos clics no duplican.

### 4.3 API interna — `apps/tenancy/notificaciones.py`

```python
import logging
from django.contrib import messages
from django.db.models import Exists, OuterRef
from . import scope
from .models import Notificacion, LecturaNotificacion

logger = logging.getLogger(__name__)

_NIVEL_A_MESSAGE = {
    Notificacion.Nivel.EXITO: messages.SUCCESS,
    Notificacion.Nivel.AVISO: messages.WARNING,
    Notificacion.Nivel.ERROR: messages.ERROR,
}

def registrar_notificacion(empresa, nivel, texto, *, tipo=Notificacion.Tipo.OTRO,
                           motivo='', actor=None, enlace_url='', enlace_texto=''):
    """Guarda UNA Notificacion en la transacción y el alcance actuales.
    NUNCA lanza: si el guardado falla (RLS sin alcance, error de base), lo
    registra y regresa None. La acción del usuario jamás se rompe por esto."""
    if empresa is None:
        logger.warning('Notificacion sin empresa, no se guarda: %s', texto)
        return None
    try:
        return Notificacion.objects.create(
            empresa=empresa, nivel=nivel, texto=texto, tipo=tipo, motivo=motivo,
            actor=actor, enlace_url=enlace_url, enlace_texto=enlace_texto)
    except Exception:
        logger.exception('No se pudo guardar la notificacion: %s', texto)
        return None

def avisar(request, nivel, texto, *, empresa=None, tipo=Notificacion.Tipo.OTRO,
           motivo='', enlace_url='', enlace_texto=''):
    """Muestra el mensaje verde/ámbar/rojo de Django Y guarda la Notificacion.
    Tolera request=None (flujos sin pantalla): entonces solo guarda.
    NUNCA rompe la acción del usuario."""
    mensaje = f'{texto} {motivo}'.strip() if motivo else texto
    if request is not None and hasattr(request, '_messages'):
        messages.add_message(request, _NIVEL_A_MESSAGE[nivel], mensaje)
    if empresa is None and request is not None:
        empresa = scope.empresa_actual(request)
    actor = getattr(request, 'user', None)
    if actor is not None and getattr(actor, 'is_anonymous', True):
        actor = None
    return registrar_notificacion(empresa, nivel, texto, tipo=tipo, motivo=motivo,
                                  actor=actor, enlace_url=enlace_url, enlace_texto=enlace_texto)

def contar_no_leidas(request, tope=99):
    """No leídas del usuario en el alcance actual (su empresa; todas para el
    operador, por RLS bypass). Devuelve como mucho tope+1 para pintar '99+'."""
    user = getattr(request, 'user', None)
    if user is None or user.is_anonymous or not user.has_perm('tenancy.view_notificacion'):
        return 0
    ya_leida = LecturaNotificacion.objects.filter(notificacion=OuterRef('pk'), usuario=user)
    qs = Notificacion.objects.annotate(_leida=Exists(ya_leida)).filter(_leida=False)
    return qs[: tope + 1].count()

def marcar_leidas(usuario, notificaciones):
    """Crea la lectura de `usuario` para cada notificación del iterable.
    Idempotente (ignore_conflicts). Corre dentro del alcance de empresa del request."""
    filas = [LecturaNotificacion(empresa=n.empresa, notificacion=n, usuario=usuario)
             for n in notificaciones]
    LecturaNotificacion.objects.bulk_create(filas, ignore_conflicts=True)
```

**Qué pasa si falla el guardado:** `registrar_notificacion` atrapa `Exception`, lo
manda a `logger.exception` (y de ahí a Sentry si está configurado) y regresa `None`.
La acción del usuario (asignar, cobrar, reembolsar) **no se ve afectada**: el mensaje
de Django ya se mostró y la mutación ya ocurrió. Un feed caído nunca tumba una venta.

## 5. Migraciones y RLS

Dos migraciones en `apps/tenancy` (última actual: `0009`):

- **`0010_notificacion.py`** — `CreateModel` de `Notificacion` y
  `LecturaNotificacion` con sus índices y la `UniqueConstraint`. Sin data migration.
- **`0011_rls_notificacion.py`** — política RLS para `tenancy_notificacion` y
  `tenancy_lecturanotificacion`, copiando **verbatim** el patrón de
  `bookings/migrations/0065_rls_movimientodinero.py`:

```python
TABLAS_CON_EMPRESA_ID = ['tenancy_notificacion', 'tenancy_lecturanotificacion']

SQL_POLITICA = """
ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenancy_alcance ON {tabla}
FOR ALL
USING (
  empresa_id = NULLIF(current_setting('app.current_empresa_id', true), '')::int
  OR current_setting('app.operador_plataforma', true) = 'on'
);
"""
# reversa idéntica a 0065 (DROP POLICY + NO FORCE + DISABLE), con guardia vendor != 'postgresql'.
```

- `RunPython(aplicar, revertir)` con la guardia `if schema_editor.connection.vendor
  != 'postgresql': return`.
- **No hay data migration que cree filas**, así que no hace falta
  `alcance_operador_migracion`. (Si en el futuro se backfillea, sí haría falta.)
- El guardarraíl `test_guardarrail_toda_tabla_con_empresa_tiene_politica` en
  `apps/tenancy/tests_rls.py` detectará las dos tablas nuevas (tienen `empresa_id`) y
  **fallará** hasta que `0011` exista. Es la red que garantiza que no se olvide RLS.

**Índices y por qué:**
- `notif_empresa_creado (empresa, creado_en)`: ordena la lista (`-creado_en`) dentro
  de la empresa y acota el `DELETE` de retención por `creado_en`.
- `notif_empresa_tipo (empresa, tipo)`: filtro por tipo en la lista.
- `lectura_usuario_notif (usuario, notificacion)` + `UniqueConstraint`: el `Exists`
  del contador y el `bulk_create` idempotente.

## 6. Contador de no leídas y campana

### 6.1 Cálculo

`contar_no_leidas(request)` (ver 4.3): notificaciones del alcance actual que **no**
tienen una fila de `LecturaNotificacion` para `request.user`, con `Exists`/`OuterRef`
(no `exclude(...)`, que puede duplicar joins). RLS ya acota por empresa; para el
operador abarca todas (bypass). Se corta en `tope+1` (99) para pintar "99+" sin
contar miles. Con el volumen real es una consulta trivial cada 10 s por usuario.

### 6.2 Por dónde viaja (sin endpoint nuevo)

El sondeo que ya existe —`GET /admin/avisos/reservas-nuevas/`
(`apps/bookings/avisos.py`, cada 10 s desde `tenancy/avisos.js`)— **agrega un campo**
`no_leidas` a su JSON. `bookings/avisos.py` importa
`apps.tenancy.notificaciones.contar_no_leidas` (bookings→tenancy, sin ciclo). El
objeto ya está acotado por `scope.empresa_actual(request)`, así que el conteo respeta
la empresa. Si el usuario no tiene `view_notificacion`, `contar_no_leidas` devuelve 0.

```jsonc
// respuesta extendida de /admin/avisos/reservas-nuevas/
{ "desde": "...", "total": 0, "reservas": [], "no_leidas": 7 }
```

### 6.3 Campana en el header de Unfold (inyectada por JS)

**Decisión:** la campana la inyecta `tenancy/avisos.js` en el DOM (un `<a>` con un
badge), igual que ya inyecta las tarjetas del toast. **No** se sobreescriben
plantillas de Unfold.

**Por qué no override de plantilla:** la memoria del proyecto ("Trampas del admin
Unfold") documenta que clases Tailwind inexistentes fallan en silencio y que un link
mal puesto puede tumbar el admin. El enfoque JS + CSS propio (clases en
`avisos.css`, no Tailwind inventado) es el mismo patrón ya probado del toast y es
robusto: si no encuentra el header, cae a posición fija arriba a la derecha.

- La campana es un enlace a la pantalla de lista (`admin:tenancy_notificacion_changelist`).
- El badge muestra `no_leidas` (o "99+"); se oculta cuando es 0.
- Se actualiza en cada ciclo del sondeo (reusa el `fetch` existente; sin red extra).
- Clases nuevas en `avisos.css`: `.aviso-campana`, `.aviso-campana__badge`.
  Esquinas: el badge es un círculo/píldora (permitido); la campana sin sombra ni
  degradado. El senior-dev verifica el render contra el CSS compilado de Unfold.

## 7. Pantalla de lista

**Decisión:** un `ModelAdmin` de solo lectura (`NotificacionAdmin`) con
`EmpresaScopedAdminMixin`, no una vista custom.

**Por qué:** reutiliza el acotado por empresa, el filtrado y el layout de Unfold que
ya usan `MovimientoDinero` y `EventoRecuperacion`; menos código, menos superficie de
error. "Marcar como leídas" no cambia la `Notificacion` (no requiere permiso de
change sobre ella) — escribe `LecturaNotificacion` del propio usuario.

- `admin.register(Notificacion)` con `EmpresaScopedAdminMixin, ModelAdmin`.
- **Solo lectura:** `has_add_permission = has_change_permission = has_delete_permission
  = False` para todos (las filas las crea `avisar()`, las borra el cron). El operador
  tampoco crea/edita a mano.
- `list_display`: nivel (con color/ícono), tipo, texto, actor, creado_en, un enlace
  "Abrir" si hay `enlace_url`, y una columna "Leída" (✔ si existe lectura del usuario).
- `list_filter`: `tipo`, `nivel`. (Filtro por fecha opcional vía `DateFieldListFilter`
  sobre `creado_en`.)
- **Acción "Marcar como leídas"** sobre las filas seleccionadas →
  `marcar_leidas(request.user, queryset)`. Como respeta el filtro activo, marca
  exactamente lo mostrado/seleccionado.
- **Botón "Marcar todas como leídas"** en el changelist (vista custom en
  `get_urls`, patrón de `pagar_transferencia_view`), que llama `marcar_leidas` sobre
  el queryset no leído del alcance actual.
- **Entrada en el menú** `UNFOLD['SIDEBAR']` (grupo "Operación"):
  `{'title': 'Notificaciones', 'icon': 'notifications',
    'link': reverse_lazy('admin:tenancy_notificacion_changelist'),
    'permission': lambda r: r.user.has_perm('tenancy.view_notificacion')}`.

**Riesgo de HTML en `texto` (seguridad):** `texto`/`motivo` contienen datos que
escribe el cliente (p. ej. `nombre_cliente`). Se guardan en crudo y se muestran con
el autoescape del admin de Django / `format_html` con argumentos. **Nunca**
`mark_safe(texto)` ni `format_html` interpolando el texto sin placeholder. Es la
misma disciplina que el toast (`textContent`, nunca `innerHTML`).

## 8. Catálogo de eventos

`quién ve` = siempre los usuarios de la empresa dueña (por RLS) + el operador de
plataforma; es decir, cualquiera con `tenancy.view_notificacion`. El `enlace` apunta
al change del objeto (reserva) salvo nota.

| tipo | cuándo | nivel | texto (ejemplo) | motivo | disparador (archivo · momento) |
|---|---|---|---|---|---|
| `asignacion` | panga+capitán puestos y correo enviado | éxito | "Panga y capitán asignados. Correo enviado a {correo}." | — | `bookings/signals.py::_mandar` · post-commit, dentro de su `con_empresa` → `registrar_notificacion` |
| `asignacion` | el correo de asignación falló | error | "No se pudo enviar el correo de asignación a {cliente}." | `{motivo_fallo_aviso}` | `bookings/signals.py::_mandar` (rama fallo) |
| `asignacion` | panga sin capitán aún | aviso | "Panga asignada. El correo sale cuando pongas capitán." | — | `bookings/admin.py::AvisoDeAsignacionMixin` · `avisar(request, ...)` |
| `reserva_nueva` | reserva pasó a pagada por tarjeta | éxito | "Nueva reserva pagada: {cliente} · {producto} · {fecha}." | — | `payments/services.py::aplicar_pago_exitoso` · dentro de su `con_empresa` → `registrar_notificacion` |
| `reserva_nueva` | marcada pagada por transferencia | éxito | "Reserva pagada por transferencia: {cliente}." | — | `bookings/transferencia.py` · post-commit `con_empresa` → `registrar_notificacion` |
| `transferencia` | registro de transferencia desde la pantalla | éxito/error | "Transferencia registrada: {monto}." / "No se pudo registrar: …" | error | `bookings/admin.py::ReservaAdmin.pagar_transferencia_view` · `avisar(request, ...)` |
| `cobro_efectivo` | liquidación en efectivo registrada | éxito | "Cobro en efectivo: {monto}. Saldo {saldo}." | — | `bookings` acción/`cobros.py` (save_model) · `avisar(request, ...)` |
| `cambio_fecha` | cambió la fecha de salida | aviso | "Cambiaste la fecha de {cliente} a {fecha}. Al cliente no le llega aviso." | — | `bookings/admin.py::ReservaAdmin.save_model` · `avisar(request, ...)` |
| `cancelacion` | cancelada por mal clima (reembolso) | aviso | "Reserva cancelada (reembolso): {cliente}." | — | `bookings/admin.py` acción cancelar · `avisar(request, ...)` en el 2º POST |
| `reembolso` | reembolso aplicado (webhook) | aviso | "Reembolso registrado: {monto} · {cliente}." | — | `payments/services.py::aplicar_reembolso` · `con_empresa` → `registrar_notificacion` |
| `reembolso` | el reembolso falló | error | "El reembolso de {cliente} falló." | detalle de Stripe | `payments/services.py` (rama `FALLO_REEMBOLSO`) |

**Idempotencia / no duplicar:** los disparadores post-commit que ya se sellan una
sola vez (asignación con `aviso_asignacion_enviado_en`, transferencia con su sello,
reembolso fallido con `alerta_reembolso_fallido_en`) generan **una** notificación
porque corren una sola vez. El webhook de Stripe corre en `select_for_update`: una
entrega duplicada del mismo evento no vuelve a pasar a `pagada`, así que no duplica la
notificación de "reserva nueva pagada". No se agrega dedup extra en la tabla.

**Relación con el toast de reservas nuevas:** el toast (efímero, atención inmediata)
y la notificación `reserva_nueva` (persistente) son superficies distintas y
deliberadamente ambas existen (lo pidió el dueño: "que aparezca un aviso" **y** "se
queda guardado"). No se cuentan dos veces: el contador cuenta solo `Notificacion`.

## 9. Permisos

- Modelo nuevo `tenancy.notificacion` → permiso `view_notificacion`. Se agrega a
  `PERMISOS_VENDEDORA` en `bookings/management/commands/setup_roles.py` como
  `('tenancy', 'notificacion', ['view'])`; Jefe y Operador lo heredan (sus listas
  extienden la de Vendedora). **Sin** add/change/delete para nadie (coherente con el
  admin de solo lectura).
- `LecturaNotificacion` **no** se da de alta en roles ni en el admin: el usuario
  nunca la ve ni la edita directamente; solo la escribe "marcar como leídas" para sí
  mismo. No necesita permiso de modelo (la acción se gatea con `view_notificacion`).
- "Marcar como leídas" / "Marcar todas" solo escriben la lectura del propio
  `request.user`; no tocan a otros usuarios ni otras empresas (RLS + filtro por
  `usuario`).
- Operador de plataforma: ve y marca sobre todas las empresas (RLS bypass).
- Recordatorio del repo: los grupos `Jefe`/`Vendedora` se derivan de
  `MembresiaEmpresa` por señal; `setup_roles` es idempotente. Hay que **correr
  `manage.py setup_roles`** tras migrar para que el permiso llegue a los grupos
  (paso de despliegue, §13).

## 10. Retención (90 días)

- Command `apps/tenancy/management/commands/limpiar_notificaciones.py`, espejo de
  `limpiar_eventos_recuperacion.py`: `--dias` (default 90), rechaza `--dias < 1`
  (`CommandError`), borra `Notificacion.objects.filter(creado_en__lt=corte)`.
  `LecturaNotificacion` cae en cascada (FK `CASCADE`).
- **RLS crítico — el command corre con el rol `NOBYPASSRLS` y SIN alcance.** Un
  `.delete()` sin alcance ve **cero filas** (la política exige `app.current_empresa_id`
  o `operador='on'`) y **borraría nada en silencio**. Por eso el `handle` envuelve el
  borrado en `with scope.como_operador_plataforma():` para abarcar **todas** las
  empresas, incluidas las pausadas (`activo=False`). (Se descarta el patrón
  `for empresa in Empresa.objects.filter(activo=True)` de `limpiar_checkouts` porque
  dejaría crecer sin fin las notificaciones de empresas pausadas — fuga de retención.)
  `EventoRecuperacion` no tenía este problema porque está fuera de RLS; `Notificacion`
  **sí** está en RLS, así que el alcance de operador es obligatorio. Esto **debe**
  tener una prueba (ver §12).
- Cron en `render.yaml` (nuevo servicio `type: cron`), copiando el bloque de
  `limpiar-recuperacion`. Horario propuesto `15 9 * * *` (diario, 09:15 UTC ≈ 02:15
  America/Mazatlan, fuera de horario) para no empalmar con checkouts (`30 9`) ni
  recuperación (`45 9 1 * *`). Diario y no mensual porque mantiene el conteo del
  sondeo barato; el `DELETE` es trivial. `startCommand: python manage.py
  limpiar_notificaciones --dias 90`, `fromGroup: pescadeportiva-secrets`.

## 11. Riesgos y mitigaciones

| # | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| R1 | Escritura de notificación dentro de la transacción del admin que luego revierte | media | **Deseado:** la notificación de éxito comparte el commit/rollback de la acción. Para registrar un fallo que revirtió, llamar `avisar()` en el `except`, fuera del savepoint (§3.2). Prueba en §12. |
| R2 | RLS al escribir desde hilos/señales/webhook (cero filas en silencio por `SET LOCAL` muerto) | **alta** | `registrar_notificacion` se llama **dentro** del `con_empresa(empresa)` que esos disparadores ya reabren (`signals._mandar`, `transferencia._avisar_al_cliente`, webhook). No usar `on_commit` dentro de `avisar()`. Prueba de aislamiento en Postgres (§12). |
| R3 | El command de retención borra nada en silencio por RLS | **alta** | `como_operador_plataforma()` en el `handle`; prueba que verifica que borra filas de >1 empresa. |
| R4 | HTML/script en `texto`/`motivo` (nombre del cliente) | media | Texto plano en la base; autoescape del admin / `format_html` con placeholders; **nunca** `mark_safe`. Mismo patrón que el toast (`textContent`). Revisión de seguridad. |
| R5 | El guardado de la notificación tumba la acción del usuario | **alta** | `registrar_notificacion` atrapa `Exception`, loguea y regresa `None`. La mutación y el mensaje de Django ya ocurrieron. Prueba que simula fallo de base. |
| R6 | El contador cada 10 s pesa en la base | baja | Consulta `Exists` con índice, cortada a 99, volumen minúsculo. Viaja en el sondeo que ya existe (sin red nueva). |
| R7 | Override de plantilla de Unfold rompe el admin (clases Tailwind inexistentes) | media | Campana inyectada por JS con CSS propio; sin tocar plantillas. Verificar contra el CSS compilado de Unfold (memoria "Trampas del admin Unfold"). |
| R8 | Fuga tenant→tenant (una empresa ve notificaciones de otra) | **alta** | RLS `tenancy_alcance` en ambas tablas + guardarraíl `tests_rls.py` que falla si falta la política + prueba explícita de dos empresas que no se ven. |
| R9 | `LecturaNotificacion` crece sin límite | baja | CASCADE desde `Notificacion`; el purgado de 90 días la arrastra. |

## 12. Plan de pruebas

Todas corren con el runner del repo; las de RLS/carreras **solo** valen en Postgres
(puerto 5434, `DJANGO_SETTINGS_MODULE=config.settings.ci`, rol `ci_rls`).

**Unidad / comportamiento (`apps/tenancy/tests_notificaciones.py`):**
1. `avisar(request, EXITO, ...)` crea una `Notificacion` con empresa, actor, tipo y
   enlace correctos y agrega un `messages.SUCCESS`.
2. `avisar(request=None, ...)` (flujo sin pantalla) crea la notificación y **no**
   intenta mensajes; con `empresa=` explícita.
3. `registrar_notificacion` con `empresa=None` → no crea, loguea, regresa `None`.
4. **R5:** si `Notificacion.objects.create` lanza (mock), `avisar` no propaga; la
   acción simulada continúa.
5. `contar_no_leidas`: 0 sin permiso; cuenta correcta; corta en 99+ ; baja al marcar.
6. `marcar_leidas` es idempotente (dos veces no duplica; respeta `UniqueConstraint`).
7. Acción del admin "Marcar como leídas" respeta el filtro por tipo (marca solo lo
   filtrado).
8. HTML en `texto` (nombre con `<script>`) se muestra escapado en el changelist.

**RLS / tenancy (Postgres, en `tests_rls.py` o `tests_notificaciones_rls.py`):**
9. El guardarraíl `test_guardarrail_...` pasa con las dos tablas nuevas (prueba de
   que `0011` existe y cubre ambas).
10. **R8:** empresa A no ve notificaciones de empresa B por el ORM bajo alcance.
11. **R2:** `registrar_notificacion` dentro de `con_empresa(A)` escribe; sin alcance
    (NOBYPASSRLS) el `create` es rechazado y `registrar_notificacion` regresa `None`
    sin lanzar (fail-safe), no un 500.
12. El operador (bypass) ve/cuenta notificaciones de todas las empresas.

**Retención:**
13. **R3:** `limpiar_notificaciones --dias 90` borra filas viejas de **dos** empresas
    distintas (prueba que se corre bajo `como_operador_plataforma`); deja las
    recientes; `--dias 0` → `CommandError`; cascada borra las lecturas.

**Integración de disparadores (reutilizar suites existentes):**
14. Asignar panga+capitán genera `Notificacion(tipo=asignacion, nivel=exito)` cuando
    el correo sale, y `nivel=error` con `motivo` cuando `enviar_correo_asignacion`
    devuelve falso (extiende `tests_aviso_mensajes.py` / `tests_agenda.py`).
15. Marcar pagada por transferencia genera `reserva_nueva` (extiende
    `tests_transferencia.py`).
16. El webhook de pago exitoso genera `reserva_nueva` dentro del alcance de la empresa
    de la reserva (extiende `apps/payments/tests.py`).

**No correr la suite completa** en esta máquina (RAM limitada): acotar a
`apps.tenancy` y a los archivos tocados.

## 13. Pasos de despliegue (orden)

1. `migrate` (0010, 0011) — crea tablas + RLS.
2. `manage.py setup_roles` — reparte `view_notificacion` a los grupos (sin esto, la
   campana y la lista no aparecen para vendedoras/jefes).
3. `collectstatic` — publica el `avisos.js`/`avisos.css` actualizados (whitenoise).
4. Adoptar el bloque de cron nuevo en el Blueprint de Render (o agregar la variable y
   el servicio a mano si el servicio no se sincroniza desde `render.yaml`).

Rollback: (a) compute — revertir el deploy anterior (instantáneo en Render). (b)
esquema — `migrate tenancy 0009` revierte `0011` (DROP POLICY) y `0010` (DROP TABLE);
las dos migraciones son reversibles y no hay data migration que deshacer. El feed se
apaga sin afectar reservas ni pagos (ninguna ruta de dinero depende de él).

## 14. Reseña Well-Architected (breve)

1. **Excelencia operativa** — PASA. Observabilidad: la propia feature *es* el canal
   de visibilidad operativa; los fallos de guardado van a `logger.exception` → Sentry.
   Deploy documentado (§13), rollback probado por reversibilidad de migraciones.
2. **Seguridad** — PASA con riesgos listados. Frontera de confianza:
   `texto`/`motivo` traen datos del cliente → texto plano + autoescape (R4). Authz:
   RLS en ambas tablas + guardarraíl + `view_notificacion` (R8). Sin secretos nuevos.
   Clasificación: PII ligera (nombre de cliente en el texto); retención 90 días.
3. **Confiabilidad** — PASA. El feed es best-effort y **no** bloqueante (R5): un fallo
   de guardado nunca tumba una venta. Idempotencia: `UniqueConstraint` en lecturas +
   disparadores sellados una sola vez. Sin dependencia externa nueva.
4. **Rendimiento** — PASA. Contador: `Exists` indexado, cortado a 99, sobre el
   sondeo ya existente (sin red extra). SLO implícito: el sondeo tolera hasta ~10 s.
5. **Costo** — PASA. Sin componentes cloud nuevos; un cron `starter` más en Render
   (costo marginal). Retención de 90 días acota el crecimiento de la tabla.
6. **Sostenibilidad** — PASA. Purgado automático de datos viejos; sin recursos idle
   nuevos; consultas O(log n) por índice.

## 15. Estimación de costo

**Sin componentes cloud nuevos.** Se agrega un servicio `cron` en Render (plan
starter) para el purgado — costo marginal dentro del plan existente. Sin delta de
LLM ni de terceros. (Estimación gruesa, tier base, una región.)

## 16. Lista de archivos que tocará el senior-dev

**Nuevos:**
- `backend/apps/tenancy/notificaciones.py` — `avisar`, `registrar_notificacion`,
  `contar_no_leidas`, `marcar_leidas`.
- `backend/apps/tenancy/migrations/0010_notificacion.py` — CreateModel ×2 + índices.
- `backend/apps/tenancy/migrations/0011_rls_notificacion.py` — política RLS ×2.
- `backend/apps/tenancy/management/commands/limpiar_notificaciones.py` — purgado 90d.
- `backend/apps/tenancy/tests_notificaciones.py` — unidad/comportamiento.
- `backend/apps/tenancy/tests_notificaciones_rls.py` — RLS/retención en Postgres
  (o agregar a `tests_rls.py`).

**Modificados:**
- `backend/apps/tenancy/models.py` — `Notificacion`, `LecturaNotificacion`.
- `backend/apps/tenancy/admin.py` — `NotificacionAdmin` (solo lectura) + acción y
  botón "marcar como leídas" (vista en `get_urls`).
- `backend/apps/bookings/avisos.py` — agregar `no_leidas` al JSON (importa
  `apps.tenancy.notificaciones.contar_no_leidas`).
- `backend/apps/tenancy/static/tenancy/avisos.js` — inyectar la campana + badge,
  leer `no_leidas` del sondeo existente.
- `backend/apps/tenancy/static/tenancy/avisos.css` — `.aviso-campana*` (sin sombra/
  degradado; círculo/píldora para el badge).
- `backend/config/settings/base.py` — ítem "Notificaciones" en `UNFOLD['SIDEBAR']`.
- `backend/apps/bookings/management/commands/setup_roles.py` — `('tenancy',
  'notificacion', ['view'])` en `PERMISOS_VENDEDORA`.
- `backend/apps/bookings/signals.py` — `registrar_notificacion` en `_mandar`
  (éxito y fallo del correo de asignación), dentro del `con_empresa` ya abierto.
- `backend/apps/bookings/transferencia.py` — `registrar_notificacion` al confirmar
  (reserva_nueva por transferencia), en el `con_empresa` post-commit.
- `backend/apps/bookings/admin.py` — `avisar(request, ...)` en `AvisoDeAsignacionMixin`,
  `pagar_transferencia_view`, acción de cancelar, cobro en efectivo y `save_model`
  (cambio de fecha).
- `backend/apps/payments/services.py` — `registrar_notificacion` en
  `aplicar_pago_exitoso` (reserva_nueva) y `aplicar_reembolso` (reembolso), dentro de
  su `con_empresa`.
- `render.yaml` — cron `pescadeportiva-limpiar-notificaciones`.
- `backend/CLAUDE.md` — sección nueva "Notificaciones persistentes del backoffice"
  (patrón `avisar`, RLS, retención) para que no se re-derive.

## 17. Requirements Checklist

> Derivado del pedido del dueño. qa-engineer verifica cada ítem.

- [ ] REQ-1: Al asignar panga y capitán aparece un aviso de éxito ("panga y capitán
  asignados, correo enviado") y queda guardado como notificación.
- [ ] REQ-2: Si el envío del correo de asignación falla, aparece un aviso de error
  **con el motivo** y queda guardado (nivel error + `motivo`).
- [ ] REQ-3: Cuando llega una reserva nueva pagada (tarjeta o transferencia) se genera
  una notificación persistente, además del toast efímero existente.
- [ ] REQ-4: Hay una campana en el backoffice con el contador de no leídas, que se
  actualiza con el sondeo de 10 s existente.
- [ ] REQ-5: Hay una pantalla de lista de notificaciones con filtro por tipo y nivel,
  y "marcar como leídas".
- [ ] REQ-6: El estado de leída es por persona (lo que una vendedora marca leído no lo
  marca para otra).
- [ ] REQ-7: Una empresa solo ve sus notificaciones; el operador de plataforma ve
  todas (RLS verificado en Postgres).
- [ ] REQ-8: Un fallo al guardar la notificación nunca rompe la acción del usuario
  (asignar/cobrar/reembolsar siguen funcionando).
- [ ] REQ-9: Las notificaciones de más de 90 días se purgan por cron, en todas las
  empresas, sin dejar lecturas huérfanas.
- [ ] REQ-10: `avisar()` es la única función que muestra el mensaje de Django y guarda
  la notificación; los flujos hoy callados la usan.

## 18. Safeguards (no negociables)

- [ ] **Aislamiento tenant (integridad/seguridad):** `tenancy_notificacion` y
  `tenancy_lecturanotificacion` tienen política `tenancy_alcance`; el guardarraíl de
  `tests_rls.py` pasa; prueba explícita de dos empresas que no se ven.
- [ ] **No bloqueante (integridad de la operación):** `registrar_notificacion` atrapa
  toda excepción y jamás propaga; cubierto por prueba.
- [ ] **RLS en disparadores diferidos:** la escritura desde señales/webhook ocurre
  dentro de un `con_empresa` activo; nada de `on_commit` crudo en `avisar()`.
- [ ] **Retención con alcance de operador:** el command corre bajo
  `como_operador_plataforma()`; prueba que borra en >1 empresa.
- [ ] **Sin HTML inyectable:** `texto`/`motivo` en texto plano, mostrados con
  autoescape; nunca `mark_safe`.

---

DONE: ARCH-notificaciones-backoffice.md escrito — modelo, RLS, API de avisar(),
catálogo de eventos, contador, campana/lista, permisos, retención, riesgos, plan de
pruebas y lista de archivos. 10 REQ y 5 safeguards.
  artifact: docs/architecture/ARCH-notificaciones-backoffice.md
  next: luz verde del dueño sobre la decisión 3.1 (app) y 3.2 (escritura en línea) antes de que senior-dev implemente.
