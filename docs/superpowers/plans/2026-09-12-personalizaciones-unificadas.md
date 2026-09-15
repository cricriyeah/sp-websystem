# Personalizaciones unificadas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar los dos catálogos paralelos de extras/personalizaciones del checkout (`fleet.ExtrasItem`/`bookings.ReservaExtra` legacy-pesca, y `fleet.Personalizacion`/`fleet.ServicioPersonalizacion` de paquetes) en un solo catálogo con checks y tres subtipos de input (`input_texto`, `input_numero`, `input_seleccion`), y retirar `fleet.Tarifa` haciendo que pesca simple se resuelva siempre contra un `Servicio` real.

**Architecture:** Staged: primero se generaliza el catálogo nuevo (`Personalizacion`/`ServicioPersonalizacion`/`ReservaPersonalizacion` renombrado) para que funcione también sobre reservas de servicio suelto (no solo paquete), dejando intacto el catálogo legacy de pesca. Después se retira `fleet.Tarifa` (pesca simple pasa a resolverse contra el `Servicio` "pesca-deportiva" que ya existe). Al final, una migración de datos copia el catálogo real de `ExtrasItem` al catálogo unificado y se dropean `ExtrasItem`/`ReservaExtra`/`Tarifa`, quedando un solo camino para todo tipo de reserva. Cada tarea deja la suite en verde.

**Tech Stack:** Django 6.0.8 + DRF 3.18.0 (versiones comprobadas en backend/requirements.txt), Next.js 16.3.0 (App Router) + TypeScript (frontend/package.json), Postgres con RLS (políticas `tenancy_alcance`), SQLite para desarrollo.

**Spec:** `docs/superpowers/specs/2026-09-11-personalizaciones-unificadas-design.md` (HEAD `4d5bef3`, ya pasó 2 rondas de critic adversarial grounded en código).

## Global Constraints

- Proyecto sin lanzar: no hay reservas/pagos reales que preservar, ni resguardo de compatibilidad hacia atrás — ver spec, encabezado.
- Toda data migration que escriba sobre una tabla con RLS va envuelta en `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):` (ver `backend/CLAUDE.md`).
- Suite completa (`manage.py test apps config`) en SQLite y Postgres antes de cerrar la implementación, más `lint`/`tsc --noEmit`/`build` en frontend. La elaboración de este documento no equivale a ejecutar esas pruebas.
- **Despliegue coordinado:** la frase de la spec «frontend primero» aplica a un frontend puente que solo cambia el default a Servicio, conservando extras y contratos antiguos; NO al frontend final. Preparar primero la migración aditiva Tarifa→Servicio sobre backend compatible, desplegar el puente y verificar pesca con extras. Para el contrato final incompatible, suspender temporalmente el checkout del ambiente de pruebas, desplegar backend y frontend finales, ejecutar smoke con Stripe de prueba y reabrir. Nunca servir UI final contra backend antiguo ni activar el candado servicio-o-paquete antes del puente. Este ajuste técnico corrige una incompatibilidad comprobada en `ReservaCheckoutSerializer.validate`; no cambia decisiones de negocio ni autoriza un despliegue durante la escritura del plan.
- Cada tarea deja la suite en verde Y no puede cobrar de más ni de menos por el mismo concepto. Donde dos mecanismos de cobro podrían coexistir brevemente (auto-inclusión de `precio_paquete_total` vs. selección explícita del cliente), la tarea que quita el mecanismo viejo va en el MISMO task que el que lo hace innecesario (frontend mandando la selección completa) — nunca separados por un límite de tarea.
- El rename de un modelo (Tarea 2) es atómico: TODOS los archivos que importan el nombre viejo o leen el `related_name` viejo se actualizan en la misma tarea, sin excepción — un rename parcial dejaría un `ImportError` o (peor, silencioso) un `hasattr()` que devuelve `False` y deja de cobrar algo.

---

## File Map

| Archivo | Responsabilidad | Tarea |
|---|---|---|
| `backend/apps/fleet/migrations/0030_personalizacion_tipo_interaccion.py` | Migración: agrega `tipo_interaccion`, `opciones_seleccion`, `aviso_reforzado` a `Personalizacion` | 1 |
| `backend/apps/fleet/models.py` | `Personalizacion.clean()` nuevo; `ServicioPersonalizacion.clean()` redefinido | 1 |
| `backend/apps/fleet/tests.py` | Tests de `clean()` de `Personalizacion`/`ServicioPersonalizacion` (nuevos); más adelante borra `TarifaTests`/`TarifaApiTests` y arregla `EmpresaFKTests`; más adelante aún, reescribe los tests de `ExtrasItem` contra el catálogo unificado | 1, 10, 11 |
| `backend/apps/bookings/migrations/0045_rename_reservapersonalizacion.py` | `RenameModel` `ReservaPaquetePersonalizacion`→`ReservaPersonalizacion` + `AlterField` related_name a `personalizaciones_seleccionadas`; agrega `respuesta`/`precio_unitario` (sin poblar todavía) | 2 |
| `backend/apps/bookings/models.py` | `ReservaPersonalizacion` (renombrado): `respuesta`, `precio_unitario`, `subtotal`, `clean()`; más adelante agrega la regla `Reserva.clean()` servicio-o-paquete; más adelante aún borra la clase `ReservaExtra` | 2, 9, 11 |
| `backend/apps/bookings/serializers.py` | **Rename mecánico únicamente**; tarea 3 habilita contrato nuevo solo para servicio suelto no-pesca (pesca explícita sigue legacy y rechaza payload nuevo); tarea 5 habilita paquete con selección completa; tarea 11 habilita pesca y retira extras. Validación y persistencia atómicas con respuesta | 2, 3, 5, 11 |
| `backend/apps/payments/views.py` | **Rename mecánico únicamente** en `_post` (quita el `hasattr` guard, usa `personalizaciones_seleccionadas` directo, sin cambiar el alcance paquete-only); luego congela `ReservaPersonalizacion` para servicio suelto no-pesca; luego también para paquete (cutover) + quita rama `Tarifa`; luego retira `_resolver_extras`/carve-out pesca y usa el camino único; `EstadoReservaView`: `extras`→`personalizaciones` | 2, 3, 5, 10, 11 |
| `backend/apps/bookings/tests_checkout_paquete.py` | Referencias al modelo renombrado (mecánico); luego agrega el caso RLS de servicio suelto | 2, 4 |
| `backend/apps/bookings/tests_checkout_serializer.py` | Referencias al modelo renombrado (mecánico) | 2 |
| `backend/apps/tenancy/tests_rls.py` | Whitelist hardcodeada: renombra `bookings_reservapaquetepersonalizacion`→`bookings_reservapersonalizacion`; luego, al dropear `ExtrasItem`/`ReservaExtra`, quita `bookings_reservaextra` | 2, 11 |
| `backend/apps/fleet/serializers.py` | `ServicioPersonalizacionSerializer` gana `tipo_interaccion`/`opciones_seleccion`/`aviso_reforzado`; más adelante retira `TarifaSerializer`/`ExtrasItemSerializer` | 3, 10, 11 |
| `frontend/src/lib/api.ts` | `ServicioPersonalizacionCatalogo` gana 3 campos; luego retira `Tarifa`/`getTarifa`; luego retira `ExtraCatalogo`/`getExtras` y cambia `EstadoReserva*.extras`→`personalizaciones` | 3, 10, 11 |
| `backend/apps/payments/pricing.py` | Nueva función de cargo de personalizaciones (fórmula unificada correcta desde el inicio), aplicada solo a servicio suelto; luego `precio_paquete_total` la reusa y quita su auto-inclusión (cutover, junto con el frontend en la misma tarea) | 3, 5 |
| `frontend/src/components/checkout-view.tsx` | Tarea 3 activa check+input exclusivamente para servicio suelto no-pesca; pesca explícita conserva extras legacy y paquete conserva contrato antiguo. Tarea 5 corta paquete simultáneamente con pricing y serializer; tarea 8 poda tarifa; tarea 11 corta pesca y retira extras legacy. Recuperación aditiva desde tarea 3 | 3, 5, 8, 11 |
| `frontend/src/components/amenities-reminder.tsx` | Generaliza `ExtraPendiente`/`tipo==='licencia'` sobre un ítem genérico con `avisoReforzado`; `checkout-view.tsx` es quien arma ese arreglo para los 3 orígenes (legacy pesca vía adaptador, servicio suelto, paquete) | 3 |
| `frontend/src/lib/pricing-paquete.ts` | Quita `esIncluida`/doble factor `mult*cant`; adopta `cantidad_efectiva` (espejo exacto de `pricing.py`) | 5 |
| `backend/apps/fleet/migrations/0031_tarifa_a_servicio.py` | Migración de datos: por Empresa con `Tarifa`, crea/actualiza `Servicio` "pesca-deportiva" con `hora_apertura`/`hora_cierre` (`update()` explícito sobre el de sal-y-sol, que ya existe); backfill: toda `Reserva` sin `servicio` ni `paquete` pasa a apuntar a ese `Servicio` | 6 |
| `backend/apps/bookings/tests.py`, `tests_tenancy.py`, `tests_cupo_rango.py`, `tests_concurrencia.py`, `backend/apps/payments/tests.py`, `backend/apps/finance/tests.py`, `backend/apps/notifications/tests.py` | Fixture compartida de `Servicio` pesca con ventana horaria, en vez de `servicio=None` implícito | 7 |
| `frontend/src/app/[lang]/reservar/page.tsx` | Deja de llamar `getTarifa`; resuelve `getServicioDetalle('pesca-deportiva', ...)` como default | 8 |
| `backend/apps/bookings/models.py` / `admin.py` | Regla nueva `Reserva.clean()` (servicio o paquete obligatorio) + default de `servicio` en el formulario de alta manual | 9 |
| `backend/apps/fleet/views.py` | Retira `TarifaView` (Tarea 10) y `ExtrasPublicosView` (Tarea 11) | 10, 11 |
| `backend/apps/fleet/urls.py` | Retira ruta `tarifa/` (Tarea 10) y `extras/` (Tarea 11) | 10, 11 |
| `backend/apps/fleet/admin.py` | Retira `TarifaAdmin` (Tarea 10) y `ExtrasItemAdmin` (Tarea 11) | 10, 11 |
| `backend/config/settings/base.py` | Retira entrada del sidebar Unfold "Tarifa" (Tarea 10) y "Extras" (Tarea 11) — si no, el admin completo se cae (`reverse_lazy` sobre una URL que ya no existe, ver `backend/CLAUDE.md`) | 10, 11 |
| `backend/apps/fleet/management/commands/seed_local_demo.py` | Retira creación de `Tarifa` legacy | 10 |
| `backend/config/tests_health.py` | Retira import de `Tarifa`; reescribe el test que pega a `/api/<empresa>/tarifa/` | 10 |
| `backend/apps/payments/tests.py` | Reescribe los 6 sitios que crean `Tarifa` (líneas 227/543/606/1030/1225/1310 en HEAD actual) contra el `Servicio` de pesca | 10 |
| `backend/apps/fleet/migrations/0032_retirar_tarifa.py` | Dropea `fleet.Tarifa` | 10 |
| `backend/apps/fleet/migrations/0033_extrasitem_a_personalizacion.py` | Amplía nombre a 150 caracteres; cada `ExtrasItem` → `Personalizacion`/`ServicioPersonalizacion` equivalente | 11 |
| `backend/apps/bookings/migrations/0046_retirar_reservaextra.py` | Dropea `bookings.ReservaExtra` después de copiar catálogo en fleet.0033 | 11 |
| `backend/apps/fleet/migrations/0034_retirar_extrasitem.py` | Dropea `fleet.ExtrasItem` después de bookings.0046; cada DeleteModel pertenece a su app | 11 |
| `backend/apps/fleet/management/commands/seed_extras.py` | Reescrito contra `Personalizacion`/`ServicioPersonalizacion` | 11 |
| `backend/apps/bookings/admin.py` | `ReservaExtraInline` → `ReservaPersonalizacionInline` | 11 |
| `backend/apps/notifications/services.py` | `_cuerpo_html` deja de leer `extras_seleccionados` (rompe correo+WhatsApp en cuanto se dropea `ReservaExtra` — hallazgo bloqueante del critic) | 11 |
| `backend/apps/notifications/tests.py` | Test nuevo: correo de confirmación con personalizaciones tipo check | 11 |
| `backend/apps/bookings/tests.py`, `backend/apps/payments/tests.py`, `backend/apps/bookings/tests_tenancy.py`, `backend/apps/fleet/tests.py` | Tests que hoy cubren `ExtrasItem`/`ReservaExtra` se reescriben contra el catálogo unificado | 11 |
| `backend/apps/testing.py` | Helper explícito `crear_servicio_pesca(empresa, **overrides)` para fixtures; no sembrar globalmente en todos los tests | 7 |
| `backend/apps/bookings/management/commands/setup_roles.py` | Permiso view de ReservaPersonalizacion al introducir inline; retirar permisos de Tarifa y ExtrasItem/ReservaExtra en el mismo task que sus modelos | 3, 10, 11 |
| `backend/apps/bookings/tests_personalizaciones.py` (nuevo) | Contratos de modelo y serializer, actualización/rollback y servicio suelto; admin y permisos | 2, 3, 5, 9, 11 |
| `backend/apps/payments/tests_personalizaciones.py` (nuevo) | Cantidad efectiva, snapshots, fallos Stripe y recuperación aditiva desde tarea 3 | 3, 5, 11 |
| `backend/apps/payments/tests_pricing_paquete.py` | Cambiar expectativas de auto-inclusión; `calcular_precio_paquete` sin selección devuelve ancla; selección explícita determina cargos | 5 |
| `backend/apps/fleet/tests_migrations_personalizaciones.py` (nuevo) | MigrationExecutor: instalación y actualización, alias DB, precios y ventanas preservados, drop ordenado | 1, 2, 6, 11 |
| `frontend/src/lib/personalizaciones.ts` (nuevo) | Funciones puras de selección inicial, cantidad, validación y subtotal, compartidas por checkout y pricing-paquete | 3, 5 |
| `frontend/tests/personalizaciones.test.cjs` (nuevo) | Pruebas Node de helpers compilados con TypeScript; no instala framework | 3, 5 |
| `frontend/src/app/[lang]/dictionaries/es.json`, `en.json` | Textos de input obligatorio/formato y aviso reforzado, ambas lenguas | 3 |
| `frontend/src/components/paquete-card.tsx` | Precio de catálogo es ancla sin selección, sin auto-inclusión indirecta | 5 |
| `backend/apps/fleet/admin.py` | Mostrar campos nuevos, conservar filtros por empresa y validar configuraciones de input; edición de catálogo no invalida asociaciones silenciosamente | 1 |
| `backend/apps/bookings/admin.py` | Inline readonly aditivo desde tarea 3, junto al legacy hasta tarea 11 | 3, 9, 11 |
| `backend/config/health.py`, `backend/CLAUDE.md`, `frontend/src/app/[lang]/reservar/loading.tsx` | Retirar documentación de Tarifa/auto-inclusión obsoleta; health sigue sin depender de catálogo configurado | 10, 11 |

### Precisiones del mapa y secuencia

- Migraciones exactas sobre HEAD `4d5bef3`: fleet `0030_personalizacion_tipo_interaccion`, bookings `0045_rename_reservapersonalizacion`, fleet `0031_tarifa_a_servicio`, fleet `0032_retirar_tarifa`, fleet `0033_extrasitem_a_personalizacion`, bookings `0046_retirar_reservaextra`, fleet `0034_retirar_extrasitem`. Si HEAD cambia, reconciliar las hojas reales antes de generar migraciones.
- Grafo: fleet.0029→fleet.0030; (bookings.0044,fleet.0030)→bookings.0045; (fleet.0030,bookings.0044)→fleet.0031→fleet.0032→fleet.0033; (bookings.0045,fleet.0033)→bookings.0046; (fleet.0033,bookings.0046)→fleet.0034. Ninguna dependencia inversa. El backend preparatorio conserva modelos/código antiguos y aplica únicamente `migrate fleet 0031`; NO `migrate` global, para no renombrar la tabla que todavía usa el backend antiguo. El rename se aplica con el backend final durante el cutover cerrado.
- `EstadoReservaView` agrega `personalizaciones` y frontend restaura respuestas desde tarea 3; conserva `extras` para pesca hasta tarea 11. El inline nuevo también entra en tarea 3. Así servicio suelto/paquete no pierden respuestas mientras se termina pesca.
- Tarea 1 convierte asociaciones check `obligatorio=True` en `preseleccionado=True, obligatorio=False` en la misma migración; conserva su cobro antiguo hasta tarea 5. No activar validación de selección explícita de paquete anticipadamente.
- La cantidad de una selección es demanda antes del pago y cantidad efectiva congelada después. Recalcular desde `numero_personas` cada intento para checks no editables; nunca volver a multiplicar una cantidad congelada. Inputs opcionales vacíos se omiten; número cero es respuesta válida; NaN/infinito son inválidos.
- No se modifica el flujo de Orden/paquete-checkout ni el de traslado-view/TrasladoCheckoutSerializer. Su regresión se verifica al cambiar helpers compartidos.

<!-- arch-critic: APPROVED -->

Revisión independiente completada el 2026-09-12, después de dos rondas de correcciones del mapa. Se usó el agente disponible de Codex; Claude Opus no está disponible en esta sesión. Esta aprobación cubre arquitectura, no ejecución ni resultados de pruebas.

## Ejecución local y criterio de cierre

Todos los paths son relativos a `.claude/worktrees/transporte-multi-empresa`. Conservar los cambios previos de `.great_cto/` y `frontend/next-env.d.ts`; no agregarlos a commits de esta pieza. Leer `CLAUDE.md`, `backend/CLAUDE.md`, `frontend/AGENTS.md`, `docs/contexto-negocio.md` y la spec antes de implementar. Las decisiones de la spec de septiembre prevalecen sobre notas históricas de negocio.

Comandos desde el directorio indicado; PowerShell, sin variables de conexión de producción:

```powershell
# Desde backend; ejecutar una vez antes de cambiar código y al cerrar cada tarea backend.
./venv/Scripts/python.exe manage.py test apps config --settings=config.settings.local
./venv/Scripts/python.exe manage.py check --settings=config.settings.local
./venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=config.settings.local
```

Si ese worktree no tiene venv, usar el Python del venv ya existente del repositorio (ruta absoluta), con el directorio de trabajo en este backend. No instalar dependencias distintas de requirements. Registrar fallos de baseline separadamente; no adjudicarlos al cambio ni esconderlos.

```powershell
# Desde frontend; al cerrar tareas que cambian frontend.
npm run lint
./node_modules/.bin/tsc.cmd --noEmit
npm run build
```

La suite PostgreSQL se ejecuta con `config.settings.ci` y rol NOSUPERUSER/NOBYPASSRLS según `backend/CLAUDE.md`; usar únicamente DB local de pruebas. Tarea 4 y cierre final requieren Postgres real, no aceptar skips de SQLite como evidencia RLS. Cada tarea sigue rojo→implementación→verde→revisión de diff→commit limitado a sus paths. Los snippets siguientes son las piezas de implementación y pruebas que se integran en los archivos señalados, conservando métodos existentes no afectados.

### Tarea 1: Modelo del catálogo y normalización del significado de obligatorio

**Archivos:** modificar `backend/apps/fleet/models.py`, `backend/apps/fleet/admin.py`, `backend/apps/fleet/tests.py`; crear `backend/apps/fleet/migrations/0030_personalizacion_tipo_interaccion.py` y comenzar `backend/apps/fleet/tests_migrations_personalizaciones.py`.

**Interfaces:** `Personalizacion.tipo_interaccion` tiene cuatro valores; `opciones_seleccion: list[str]`; `aviso_reforzado: bool`. `ServicioPersonalizacion.precio_en(moneda)` conserva firma. `clean()` genera `django.core.exceptions.ValidationError` con errores por campo. Ningún input cobra; `precio_usd=None` o cero es válido para input gratis.

- [x] **1. Escribir pruebas de configuración inválida** en una clase nueva de `fleet/tests.py`, basada en `EmpresaTestCase` (importar `Decimal` y `ValidationError`):

```python
class PersonalizacionInteraccionTests(EmpresaTestCase):
    def test_input_no_puede_cobrar_por_persona(self):
        p = Personalizacion(empresa=self.empresa, nombre='Nombre pasajero',
                            tipo_interaccion='input_texto', cobrar_por_persona=True)
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_opciones_son_lista_no_vacia_de_strings_no_vacios(self):
        for opciones in ([], 'A', [1], ['  '], ['A', 'A']):
            with self.subTest(opciones=opciones):
                p = Personalizacion(empresa=self.empresa, nombre='Menú',
                    tipo_interaccion='input_seleccion', opciones_seleccion=opciones)
                with self.assertRaises(ValidationError):
                    p.full_clean()

    def test_input_gratis_y_check_opcional(self):
        s = Servicio.objects.create(empresa=self.empresa, nombre='Servicio', slug='s')
        p = Personalizacion.objects.create(empresa=self.empresa, nombre='Pregunta',
                                           tipo_interaccion='input_texto')
        sp = ServicioPersonalizacion(servicio=s, personalizacion=p, obligatorio=True,
                                     precio=Decimal('0.00'), precio_usd=None)
        sp.full_clean()
        sp.precio = Decimal('1.00')
        with self.assertRaises(ValidationError):
            sp.full_clean()
```

Agregar casos concretos: check con obligatorio=True falla; input con preseleccionado=True falla; cantidad_editable sin cobrar_por_persona falla; input con aviso_reforzado falla; opciones en texto falla; asociación de otra Empresa sigue fallando. Usar `subTest` sobre esas combinaciones, con la misma construcción anterior.

- [x] **2. Ejecutar rojo:** `./venv/Scripts/python.exe manage.py test apps.fleet.tests.PersonalizacionInteraccionTests`. Debe fallar por campos nuevos ausentes; no por imports o entorno.
- [x] **3. Agregar campos y validación** (en `Personalizacion`; conservar unicidad, empresa, tipo libre):

```python
class TipoInteraccion(models.TextChoices):
    CHECK = 'check', 'Casilla'
    TEXTO = 'input_texto', 'Texto'
    NUMERO = 'input_numero', 'Número'
    SELECCION = 'input_seleccion', 'Selección'

tipo_interaccion = models.CharField(max_length=20, choices=TipoInteraccion.choices,
                                    default=TipoInteraccion.CHECK)
opciones_seleccion = models.JSONField(default=list, blank=True)
aviso_reforzado = models.BooleanField(default=False)

def clean(self):
    super().clean()
    errores = {}
    opciones = self.opciones_seleccion
    if self.tipo_interaccion == 'input_seleccion':
        if (not isinstance(opciones, list) or not opciones
                or any(not isinstance(o, str) or not o.strip() for o in opciones)):
            errores['opciones_seleccion'] = 'Usa una lista de opciones de texto no vacías.'
        elif len(set(opciones)) != len(opciones):
            errores['opciones_seleccion'] = 'No repitas opciones de selección.'
    elif opciones:
        errores['opciones_seleccion'] = 'Las opciones solo aplican a selección.'
    if self.tipo_interaccion != 'check':
        for campo in ('cobrar_por_persona', 'cantidad_editable', 'aviso_reforzado'):
            if getattr(self, campo):
                errores[campo] = 'Solo aplica a personalizaciones tipo check.'
    if self.cantidad_editable and not self.cobrar_por_persona:
        errores['cantidad_editable'] = 'Cantidad editable requiere cobrar por persona.'
    if errores:
        raise ValidationError(errores)
```

En `ServicioPersonalizacion.clean`, después del control de empresa existente y solo si `personalizacion_id` existe:

```python
p = self.personalizacion
if p.tipo_interaccion == 'check' and self.obligatorio:
    raise ValidationError({'obligatorio': 'Para un check usa preseleccionado.'})
if p.tipo_interaccion != 'check':
    errores = {}
    if self.preseleccionado:
        errores['preseleccionado'] = 'Solo aplica a checks.'
    if self.precio or self.precio_usd:
        errores['precio'] = 'Los inputs no pueden tener precio.'
    if errores:
        raise ValidationError(errores)
```

Al editar el tipo del catálogo existente, rechazar cambiarlo a input si alguna asociación sigue cobrando o preseleccionada: comprobar `self.en_servicios` cuando `self.pk` exista, y devolver error en `tipo_interaccion` indicando que se ajusten primero las asociaciones. No convertir silenciosamente importes. Incluir prueba con una Personalizacion ya persistida y SP con precio > 0. Mostrar `tipo_interaccion`/`aviso_reforzado` en list_display/list_filter de `PersonalizacionAdmin`; el formulario ya muestra los campos de modelo. Conservar `EmpresaScopedAdminMixin`.

- [x] **4. Generar migración y normalizar configuración existente:** `manage.py makemigrations fleet --name personalizacion_tipo_interaccion`. Tras los AddField incluir:

```python
def normalizar_checks(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion
    SP = apps.get_model('fleet', 'ServicioPersonalizacion')
    with alcance_operador_migracion(schema_editor.connection):
        SP.objects.using(schema_editor.connection.alias).filter(obligatorio=True).update(
            obligatorio=False, preseleccionado=True)
```

Usar `RunPython(normalizar_checks, migrations.RunPython.noop)`: no es posible distinguir luego las recomendadas antiguas de las convertidas. No declarar rollback de negocio reversible. Probar con modelo histórico anterior: check obligatorio mantiene precio y termina recomendado; catálogo vacío no recibe semillas. La auto-inclusión antigua aún incluye preseleccionado y por tanto conserva el total hasta tarea 5.

- [x] **5. Verde y commit:** pruebas nuevas, `apps.payments.tests_pricing_paquete`, suite backend y checks de migración. `git add` solo los cinco paths de esta tarea; `git commit -m "feat: definir tipos de personalizacion y validar catalogo"`.

### Tarea 2: Rename atómico y modelo de selección con respuesta y snapshot

**Archivos:** `backend/apps/bookings/models.py`, `serializers.py`, `tests_checkout_paquete.py`, `tests_checkout_serializer.py`, `backend/apps/payments/views.py`, `backend/apps/tenancy/tests_rls.py`; crear `backend/apps/bookings/tests_personalizaciones.py` y `backend/apps/bookings/migrations/0045_rename_reservapersonalizacion.py`.

**Interfaces:** `ReservaPersonalizacion(reserva, servicio_personalizacion, cantidad=1, respuesta='', precio_unitario=None)`; manager `Reserva.personalizaciones_seleccionadas`; `subtotal: Decimal | None`. La selección no cobra hasta tarea 3/5. `full_clean()` valida tipos; `.objects.create` no lo invoca automáticamente.

- [x] **1. Escribir test del nuevo modelo:** comenzar archivo de pruebas con imports y fixture explícita; se reutiliza esta base en las tareas siguientes.

```python
import uuid
from datetime import time, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.testing import EmpresaTestCase
from apps.fleet.models import Personalizacion, Servicio, ServicioPersonalizacion
from apps.bookings.models import Reserva, ReservaPersonalizacion

class PersonalizacionesModelTests(EmpresaTestCase):
    def setUp(self):
        self.servicio = Servicio.objects.create(empresa=self.empresa, nombre='Paseo',
            slug='paseo', tipo_servicio='otro', estrategia_cupo='bajo_demanda',
            estrategia_precio='tarifa_fija', precio_base=Decimal('1000.00'))
        self.p = Personalizacion.objects.create(empresa=self.empresa, nombre='Pregunta',
                                               tipo_interaccion='input_numero')
        self.sp = ServicioPersonalizacion.objects.create(servicio=self.servicio,
            personalizacion=self.p, precio=0, obligatorio=True)
        self.reserva = Reserva.objects.create(empresa=self.empresa, servicio=self.servicio,
            fecha=timezone.localdate() + timedelta(days=10), hora=time(6), numero_personas=3,
            nombre_cliente='Juan Perez', telefono_cliente='+5216121234567',
            correo_cliente='juan@example.com', moneda='MXN', deslinde_aceptado=True)

    def test_numero_cero_es_valido_e_input_no_tiene_subtotal(self):
        fila = ReservaPersonalizacion(reserva=self.reserva,
            servicio_personalizacion=self.sp, respuesta='0')
        fila.full_clean()
        self.assertIsNone(fila.subtotal)

    def test_numero_no_finito_es_invalido(self):
        for respuesta in ('NaN', 'Infinity', '-Infinity', 'abc'):
            with self.subTest(respuesta=respuesta):
                fila = ReservaPersonalizacion(reserva=self.reserva,
                    servicio_personalizacion=self.sp, respuesta=respuesta)
                with self.assertRaises(ValidationError):
                    fila.full_clean()

    def test_subtotal_check_congelado(self):
        self.p.tipo_interaccion = 'check'
        self.p.save(update_fields=['tipo_interaccion'])
        self.sp.obligatorio = False
        self.sp.save(update_fields=['obligatorio'])
        fila = ReservaPersonalizacion(reserva=self.reserva,
            servicio_personalizacion=self.sp, cantidad=2, precio_unitario=Decimal('450'))
        self.assertEqual(fila.subtotal, Decimal('900'))
```

- [x] **2. Ejecutar rojo:** `manage.py test apps.bookings.tests_personalizaciones` (nuevo import todavía no existe).
- [x] **3. Renombrar modelo y referencias en una sola edición**, excepto migraciones históricas. Conservar nombre de constraint `reservapaquetepers_unico` para no hacer cambios innecesarios. Agregar:

```python
respuesta = models.TextField(blank=True, default='')
precio_unitario = models.DecimalField(max_digits=10, decimal_places=2,
                                     null=True, blank=True)

@property
def subtotal(self):
    if (self.precio_unitario is None
            or self.servicio_personalizacion.personalizacion.tipo_interaccion != 'check'):
        return None
    return self.precio_unitario * self.cantidad

def clean(self):
    super().clean()
    if not self.servicio_personalizacion_id:
        return
    sp = self.servicio_personalizacion
    p = sp.personalizacion
    if self.reserva_id and (sp.servicio.empresa_id != self.reserva.empresa_id or p.empresa_id != self.reserva.empresa_id):
        raise ValidationError({'servicio_personalizacion': 'La personalización pertenece a otra empresa.'})
    if self.cantidad < 1:
        raise ValidationError({'cantidad': 'La cantidad mínima es 1.'})
    if p.tipo_interaccion == 'check':
        if self.respuesta:
            raise ValidationError({'respuesta': 'Un check no lleva respuesta.'})
        return
    if self.cantidad != 1:
        raise ValidationError({'cantidad': 'La cantidad no aplica a un input.'})
    if self.precio_unitario not in (None, Decimal('0')):
        raise ValidationError({'precio_unitario': 'Los inputs no cobran.'})
    if not self.respuesta.strip():
        if sp.obligatorio:
            raise ValidationError({'respuesta': 'Esta respuesta es obligatoria.'})
        return
    if p.tipo_interaccion == 'input_numero':
        try:
            valido = Decimal(self.respuesta).is_finite()
        except InvalidOperation:
            valido = False
        if not valido:
            raise ValidationError({'respuesta': 'Escribe un número válido.'})
    if p.tipo_interaccion == 'input_seleccion' and self.respuesta not in p.opciones_seleccion:
        raise ValidationError({'respuesta': 'Selecciona una opción válida.'})
```

Importar `InvalidOperation` con `Decimal`. No validar aquí cantidades máximas de check contra snapshot: se recortan al resolver cobro. Validar pertenencia al Servicio/Paquete en el serializer (tarea 3), no permitir IDs solo porque son de la misma Empresa.

- [x] **4. Crear migración explícita**, verificar que Django NO proponga DeleteModel/CreateModel:

```python
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('bookings', '0044_rls_orden_sin_current_query'),
                    ('fleet', '0030_personalizacion_tipo_interaccion')]
    operations = [
        migrations.RenameModel('ReservaPaquetePersonalizacion', 'ReservaPersonalizacion'),
        migrations.AlterField('reservapersonalizacion', 'reserva', models.ForeignKey(
            on_delete=django.db.models.deletion.CASCADE,
            related_name='personalizaciones_seleccionadas', to='bookings.reserva')),
        migrations.AddField('reservapersonalizacion', 'respuesta',
                            models.TextField(blank=True, default='')),
        migrations.AddField('reservapersonalizacion', 'precio_unitario',
            models.DecimalField(blank=True, null=True, max_digits=10, decimal_places=2)),
        migrations.AlterModelOptions('reservapersonalizacion', {
            'verbose_name': 'personalización de reserva',
            'verbose_name_plural': 'personalizaciones de reserva'}),
    ]
```

Actualizar verbose_name del modelo con los mismos textos. Agregar prueba MigrationExecutor que cree fila en estado anterior y verifique mismo PK/reserva/SP/cantidad tras rename. Mantener `precio_unitario=None`, no inventar snapshots históricos.

- [x] **5. Verde:** suite backend y búsqueda `rg -n "ReservaPaquetePersonalizacion|paquete_personalizaciones|bookings_reservapaquetepersonalizacion" backend/apps -g '!**/migrations/**'`. Solo pueden quedar nombres antiguos en pruebas explícitas de migración histórica, no en consumidores runtime. Commit `refactor: generalizar modelo de seleccion de personalizaciones` limitado a paths de tarea 2.

### Tarea 3: Servicio suelto no-pesca de extremo a extremo

**Archivos:** `backend/apps/bookings/serializers.py`, `admin.py`, `tests_personalizaciones.py`, `management/commands/setup_roles.py`; `backend/apps/fleet/serializers.py`; `backend/apps/payments/pricing.py`, `views.py`; crear `backend/apps/payments/tests_personalizaciones.py`; `frontend/src/lib/api.ts`, nuevo `frontend/src/lib/personalizaciones.ts`, nuevo `frontend/tests/personalizaciones.test.cjs`; `frontend/src/components/checkout-view.tsx`, `amenities-reminder.tsx`; ambos diccionarios `frontend/src/app/[lang]/dictionaries/{es,en}.json`.

**Consume:** modelo de tarea 2. **Produce:** payload `personalizaciones: [{id: number, cantidad?: number, respuesta?: string}]`, id de **ServicioPersonalizacion**, selección completa. Campo omitido significa `[]` en POST completo. `respuesta=''` para check. Servicio no-pesca usa mecanismo nuevo; pesca (incluido servicio explícito) y paquete aún conservan su camino anterior. Contrato de cálculo:

```python
def cantidad_efectiva(*, cobrar_por_persona, cantidad_editable, personas, cantidad=1):
    if not cobrar_por_persona:
        return 1
    if not cantidad_editable:
        return personas
    return max(1, min(cantidad, personas))

def cargo_personalizacion(precio, *, cobrar_por_persona, cantidad_editable,
                         personas, cantidad=1):
    if precio is None:
        return None
    return Decimal(precio) * cantidad_efectiva(cobrar_por_persona=cobrar_por_persona,
        cantidad_editable=cantidad_editable, personas=personas, cantidad=cantidad)
```

- [ ] **1. Escribir pruebas rojas de cantidad y API.** En `payments/tests_personalizaciones.py`:

```python
from decimal import Decimal
from django.test import SimpleTestCase
from apps.payments.pricing import cargo_personalizacion

class CantidadPersonalizacionTests(SimpleTestCase):
    def test_licencia_editable_no_multiplica_dos_veces(self):
        self.assertEqual(cargo_personalizacion(Decimal('450'), cobrar_por_persona=True,
            cantidad_editable=True, personas=5, cantidad=2), Decimal('900'))

    def test_grupo_completo_ignora_cantidad_del_cliente(self):
        self.assertEqual(cargo_personalizacion(Decimal('300'), cobrar_por_persona=True,
            cantidad_editable=False, personas=5, cantidad=1), Decimal('1500'))

    def test_plano_y_moneda_no_configurada(self):
        self.assertEqual(cargo_personalizacion(Decimal('200'), cobrar_por_persona=False,
            cantidad_editable=False, personas=5, cantidad=5), Decimal('200'))
        self.assertIsNone(cargo_personalizacion(None, cobrar_por_persona=False,
            cantidad_editable=False, personas=5))
```

En `bookings/tests_personalizaciones.py`, sobre la fixture `PersonalizacionesModelTests`, agregar una clase `PersonalizacionesSerializerTests` (o factorizar el setUp de esa clase en una base sin tests) con este test:

```python
from rest_framework.test import APIRequestFactory
from apps.bookings.serializers import ReservaCheckoutSerializer

def test_rechaza_input_obligatorio_ausente_y_acepta_cero(self):
    datos = dict(checkout_id=str(uuid.uuid4()), servicio=self.servicio.slug,
        fecha=self.reserva.fecha.isoformat(), hora='06:00', numero_personas=3,
        nombre_cliente='Juan Perez', telefono_cliente='+5216121234567',
        correo_cliente='juan@example.com', moneda='MXN',
        deslinde_aceptado=True, deslinde_nombre='Juan Perez', personalizaciones=[])
    contexto = {'empresa': self.empresa,
        'request': APIRequestFactory().post('/api/empresa-test/reservas/')}
    malo = ReservaCheckoutSerializer(data=datos, context=contexto)
    self.assertFalse(malo.is_valid())
    self.assertIn('personalizaciones', malo.errors)
    datos['personalizaciones'] = [{'id': self.sp.pk, 'respuesta': '0'}]
    bueno = ReservaCheckoutSerializer(data=datos, context=contexto)
    self.assertTrue(bueno.is_valid(), bueno.errors)
    guardada = bueno.save()
    self.assertEqual(guardada.personalizaciones_seleccionadas.get().respuesta, '0')
```

Cubrir además IDs repetidos/ajenos/inactivos, input selección fuera de lista, check con respuesta, cantidad input distinta de 1, recomendada desmarcada y actualización que borra selecciones. Asegurar que una actualización inválida no cambie ni la reserva ni sus filas. Pesca explícita debe rechazar nuevo payload durante esta fase y conservar el mismo monto de extras legacy; paquete conserva sus tests actuales.

- [ ] **2. Ejecutar rojo:** `manage.py test apps.payments.tests_personalizaciones apps.bookings.tests_personalizaciones`.
- [ ] **3. Integrar validación y persistencia.** Añadir al serializer de ítem `respuesta = serializers.CharField(required=False, allow_blank=True, default='', trim_whitespace=False)`. Conservar `cantidad` entera mínima 1. Resolver servicio/paquete como lo hace `validate()` hoy, incluyendo fallback de instance. Para el camino nuevo, construir un mapa único:

```python
# En validate(), inicialmente solo para servicio no-pesca sin paquete.
disponibles = {sp.pk: sp for sp in ServicioPersonalizacion.objects.filter(
    servicio=servicio, servicio__empresa=empresa, personalizacion__empresa=empresa,
    activo=True, personalizacion__activo=True,
).select_related('personalizacion', 'servicio')}
vistos = set()
for item in personalizaciones:
    sp = disponibles.get(item['id'])
    if sp is None or item['id'] in vistos:
        raise serializers.ValidationError({'personalizaciones': 'Selección inválida o repetida.'})
    vistos.add(sp.pk)
    self._validar_respuesta_personalizacion(sp, item)
for sp in disponibles.values():
    if (sp.personalizacion.tipo_interaccion != 'check' and sp.obligatorio
            and sp.pk not in vistos):
        raise serializers.ValidationError({'personalizaciones': f'Falta responder: {sp.personalizacion.nombre}.'})
```

Implementar la delegación a `clean()` de tarea 2 (la validación de contenido no requiere PK de Reserva); no duplicar reglas de respuesta:

```python
def _validar_respuesta_personalizacion(self, sp, item):
    fila = ReservaPersonalizacion(servicio_personalizacion=sp,
        cantidad=item.get('cantidad', 1), respuesta=item.get('respuesta', ''))
    try:
        fila.clean()
    except DjangoValidationError as exc:
        raise serializers.ValidationError({'personalizaciones': exc.messages})
```

Los inputs opcionales con respuesta vacía no se persisten; los obligatorios vacíos sí se rechazan.

En `_guardar`, envolver full_clean/save/sincronización en `transaction.atomic()` (el scope actual se conserva). `_sincronizar_personalizaciones` hace delete/recreate solo en reserva pendiente, ambos productos admitidos según fase; para cada fila nueva llamar `full_clean()` y `save()`. No habilitar aún checks recomendados de paquete ni payload nuevo de pesca.

- [ ] **4. Implementar resolución de cobro sin escribir antes de Stripe.** En `CrearPagoView` agregar `_resolver_personalizaciones(self, reserva)` que retorna `(cargo: Decimal, a_borrar: list, a_congelar: list[tuple[fila, Decimal, int]], error: str|None)`. Recorrer `personalizaciones_seleccionadas.select_related('servicio_personalizacion__personalizacion', 'servicio_personalizacion__servicio')`; eliminar del cálculo asociaciones desactivadas o ya no pertenecientes al producto; input no suma y tiene snapshot None; check activo sin moneda retorna error 503. Para cada check usar `cantidad_efectiva` y una única multiplicación. No ocultar un precio ausente con cero ni con MXN. Aplicar `sp.full_clean()`/validación de respuesta al resolver para detectar cambios de configuración desde el POST; si un input ahora obligatorio falta, devolver error antes de Stripe.

```python
# Dentro del resolver, después de validar pertenencia/activo/tipo.
precio = sp.precio_en(reserva.moneda)
if precio is None:
    return Decimal('0'), [], [], f'No hay precio de "{sp.personalizacion.nombre}" en {reserva.moneda}.'
cantidad = cantidad_efectiva(cobrar_por_persona=sp.personalizacion.cobrar_por_persona,
    cantidad_editable=sp.personalizacion.cantidad_editable,
    personas=reserva.numero_personas, cantidad=fila.cantidad)
cargo_total += precio * cantidad
a_congelar.append((fila, precio, cantidad))
```

Solo activar el resolver para `not reserva.paquete_id and reserva.servicio_id and reserva.servicio.tipo_servicio != 'pesca'`. Sumárselo a precio base antes de promoción y anticipo. Congelar tuplas en el `transaction.atomic()` existente **después** de `_intent_de` exitoso, junto con `reserva.precio_total`. No modificar `_intent_de`, claves idempotentes, Stripe por empresa ni ordenes. Reintento pendiente relee precio vigente; intent processing/succeeded rechaza antes de guardar snapshots. La lectura de reserva pagada siempre usa snapshot. Pruebas con cliente Stripe simulado siguiendo `payments/tests.py`: 1000 + 2×450 = 1900; promoción 10% = 1710; anticipo 30% = 513 (51300 centavos). Fallo Stripe 502 y rechazo 409 dejan snapshots previos intactos; cambio de precio 450→500 antes de reintento pendiente termina en 2000; cambio después de pagada deja monto de extras en 900.

- [ ] **5. Exponer catálogo, recuperación e inline de forma aditiva.** `ServicioPersonalizacionSerializer` añade tres campos read_only con source `personalizacion.tipo_interaccion`, `personalizacion.opciones_seleccion`, `personalizacion.aviso_reforzado`. En `EstadoReservaView`, agregar en ambas respuestas `personalizaciones` y conservar `extras`:

```python
# En rama pagada: incluir esta lista con clave 'personalizaciones' en Response.
personalizaciones_pagadas = [{
    'nombre': f.servicio_personalizacion.personalizacion.nombre,
    'tipo_interaccion': f.servicio_personalizacion.personalizacion.tipo_interaccion,
    'cantidad': f.cantidad, 'respuesta': f.respuesta,
    'monto': str(f.subtotal) if f.subtotal is not None else None,
} for f in reserva.personalizaciones_seleccionadas.select_related(
    'servicio_personalizacion__personalizacion')]
# En rama pendiente: incluir esta lista con clave 'personalizaciones' en Response.
personalizaciones_pendientes = [{'id': f.servicio_personalizacion_id,
    'cantidad': f.cantidad, 'respuesta': f.respuesta}
    for f in reserva.personalizaciones_seleccionadas.all()]
```

La ruta real en HEAD es `GET /api/<empresa>/reservas/estado/?checkout_id=...`, no `/estado-reserva/` citado informalmente en la spec. No crear una segunda ruta. Agregar `ReservaPersonalizacionInline` readonly con campos `servicio_personalizacion`, `cantidad`, `respuesta`, `precio_unitario`, `subtotal_mostrado`; mismos overrides has_add/has_delete y display que ReservaExtraInline. Añadir `('bookings', 'reservapersonalizacion', ['view'])` a PERMISOS_VENDEDORA; jefe/operador heredan. Tests: vendedora ve respuesta en detalle de su reserva, no edita precio ni catálogo ni ve empresa ajena. Agenda no recibe respuestas.

- [ ] **6. Crear helpers frontend puros y pruebas antes de conectar UI.** Contratos exactos de `personalizaciones.ts`: `TipoInteraccion`, `PersonalizacionUI`, `SeleccionPersonalizacion`; `seleccionInicial(catalogo)`, `cantidadEfectiva(p, personas, cantidad?)`, `erroresPersonalizaciones(catalogo, seleccion)`, `totalPersonalizaciones(catalogo, seleccion, personas, moneda)` (number|null). El tipo local es estructural, no importa api.ts, para compilar tests sin Next:

```ts
export type TipoInteraccion = 'check' | 'input_texto' | 'input_numero' | 'input_seleccion';
export type PersonalizacionUI = {
  id: number; nombre: string; tipo_interaccion: TipoInteraccion;
  opciones_seleccion: string[]; aviso_reforzado: boolean;
  obligatorio: boolean; preseleccionado: boolean;
  cobrar_por_persona: boolean; cantidad_editable: boolean;
  precio: string; precio_usd: string | null;
};
export type SeleccionPersonalizacion = { id: number; cantidad?: number; respuesta?: string };
export const seleccionInicial = (catalogo: PersonalizacionUI[]): SeleccionPersonalizacion[] =>
  catalogo.filter(p => p.tipo_interaccion === 'check' && p.preseleccionado)
    .map(p => ({ id: p.id, cantidad: 1 }));
export function cantidadEfectiva(p: PersonalizacionUI, personas: number, cantidad = 1) {
  return !p.cobrar_por_persona ? 1 : !p.cantidad_editable ? personas
    : Math.max(1, Math.min(cantidad, personas));
}
export function erroresPersonalizaciones(catalogo: PersonalizacionUI[], seleccion: SeleccionPersonalizacion[]) {
  const errores: Record<number, 'required' | 'number' | 'selection'> = {};
  const elegidas = new Map(seleccion.map(s => [s.id, s]));
  for (const p of catalogo) {
    if (p.tipo_interaccion === 'check') continue;
    const valor = elegidas.get(p.id)?.respuesta ?? '';
    if (!valor.trim()) { if (p.obligatorio) errores[p.id] = 'required'; continue; }
    if (p.tipo_interaccion === 'input_numero' &&
        (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(valor.trim()) || !Number.isFinite(Number(valor))))
      errores[p.id] = 'number';
    if (p.tipo_interaccion === 'input_seleccion' && !p.opciones_seleccion.includes(valor))
      errores[p.id] = 'selection';
  }
  return errores;
}
export function totalPersonalizaciones(catalogo: PersonalizacionUI[], seleccion: SeleccionPersonalizacion[],
                                      personas: number, moneda: 'MXN' | 'USD'): number | null {
  const elegidas = new Map(seleccion.map(s => [s.id, s]));
  let centavos = 0;
  for (const p of catalogo) {
    const s = elegidas.get(p.id);
    if (!s || p.tipo_interaccion !== 'check') continue;
    const precio = moneda === 'USD' ? p.precio_usd : p.precio;
    if (precio === null || !Number.isFinite(Number(precio))) return null;
    centavos += Math.round(Number(precio) * 100) * cantidadEfectiva(p, personas, s.cantidad);
  }
  return centavos / 100;
}
```

Para cantidad inicial de un check editable por persona, el checkout sustituye `cantidad:1` por `people`; la función no conoce personas intencionalmente. Al reducir people recortar selecciones editables; no volver a preseleccionar una recomendada desmarcada.

```js
// frontend/tests/personalizaciones.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const h = require(path.join(process.env.PERSONALIZACIONES_TEST_OUT, 'personalizaciones.js'));
const licencia = {id: 7, nombre: 'Licencia', tipo_interaccion: 'check', opciones_seleccion: [],
  aviso_reforzado: true, obligatorio: false, preseleccionado: true,
  cobrar_por_persona: true, cantidad_editable: true, precio: '450.00', precio_usd: null};
test('recomendada removible y cantidad efectiva', () => {
  assert.deepEqual(h.seleccionInicial([licencia]), [{id: 7, cantidad: 1}]);
  assert.equal(h.totalPersonalizaciones([licencia], [], 5, 'MXN'), 0);
  assert.equal(h.totalPersonalizaciones([licencia], [{id: 7, cantidad: 2}], 5, 'MXN'), 900);
  assert.equal(h.totalPersonalizaciones([licencia], [{id: 7}], 5, 'USD'), null);
});
test('input número cero, vacío y no finito', () => {
  const p = {...licencia, tipo_interaccion: 'input_numero', obligatorio: true};
  assert.deepEqual(h.erroresPersonalizaciones([p], [{id: 7, respuesta: '0'}]), {});
  assert.deepEqual(h.erroresPersonalizaciones([p], []), {7: 'required'});
  assert.deepEqual(h.erroresPersonalizaciones([p], [{id: 7, respuesta: 'Infinity'}]), {7: 'number'});
});
```

Comando desde frontend (rojo antes de implementar helper, verde después; repetir en tarea 5):

```powershell
$env:PERSONALIZACIONES_TEST_OUT = Join-Path $env:TEMP ('personalizaciones-tests-' + [guid]::NewGuid().ToString('N'))
./node_modules/.bin/tsc.cmd src/lib/personalizaciones.ts --outDir $env:PERSONALIZACIONES_TEST_OUT --module commonjs --target es2020 --strict --skipLibCheck
node --test tests/personalizaciones.test.cjs
```

- [ ] **7. Conectar checkout manteniendo frontera de fase.** Extender `ServicioPersonalizacionCatalogo` con esos tres campos y `ReservaInput.personalizaciones` con respuesta; importar `SeleccionPersonalizacion`. Mostrar catálogo nuevo únicamente cuando `servicio && servicio.tipo_servicio !== 'pesca' && !paquete`. Mantener lista antigua de paquete separada hasta tarea 5. Construir lista por id SP, inicializar recomendadas una sola vez al establecer identidad del producto y antes de recuperación; si el servidor recupera `personalizaciones: []`, **respetar lista vacía**. No usar `if (lista.length)` para decidir si restaurar.

Inputs usan value controlado y actualizan una entrada por id (sin duplicados), con `respuesta` string; `<input type="number" step="any">`, `<select>` con opción vacía y opciones del catálogo; check editable conserva controles +/- existentes, rango 1..people. Errores separados del contacto:

```tsx
const [erroresPersonalizacion, setErroresPersonalizacion] = useState<Record<number, string>>({});
// Dentro de la ruta existente que intenta crear reserva/pago, no al navegar pasos anteriores:
const errores = erroresPersonalizaciones(catalogoUnificado, personalizaciones);
setErroresPersonalizacion(errores);
const primero = catalogoUnificado.find(p => errores[p.id]);
if (primero) {
  document.getElementById(`personalizacion-${primero.id}`)?.focus();
  document.getElementById(`personalizacion-${primero.id}`)?.scrollIntoView({block: 'center'});
  return;
}
```

`catalogoUnificado` es la lista `ServicioPersonalizacionCatalogo[]` de la frontera de fase anterior. Los controles llevan id, label htmlFor, aria-invalid y aria-describedby hacia `error-personalizacion-${sp.id}`. Traducir códigos `required/number/selection` mediante `dict.checkout.personalizacionErrors` en ambos diccionarios: ES «Esta respuesta es obligatoria», «Escribe un número válido», «Selecciona una opción válida»; EN «This answer is required», «Enter a valid number», «Select a valid option». No bloquear el avance de pasos anteriores por `required` nativo; validar al pagar como indica la spec.

Generalizar `ExtraPendiente` conservando nombre público si facilita diff: reemplazar `tipo` por `avisoReforzado:boolean`. Las dos secciones del modal filtran por ese booleano; el adaptador legacy en checkout transforma `tipo==='licencia'` solamente mientras exista ExtrasItem. Para catálogo nuevo el booleano viene de API, y pendientes incluye solo checks `preseleccionado` que no están en selección. Usar icono Warning y copy reforzado ES «Has quitado una opción con una advertencia importante. Revisa sus condiciones antes de continuar.» / EN «You removed an option with an important warning. Review its conditions before continuing.»; conservar continuar sin seleccionar y volver a agregar. El callback de añadir distingue fuente legacy/nueva para evitar colisión de IDs; en esta fase cada checkout usa una sola fuente.

Añadir subtotal nuevo al resumen de servicio no-pesca; `null` deshabilita pago por moneda no configurada. Restaurar respuestas al recuperar pendiente y mostrar checks pagados desde `monto` congelado, no desde catálogo. No mostrar respuestas input en desglose monetario ni Agenda.

- [ ] **8. Verde y revisión:** backend completo, helpers Node, lint/tsc/build. Smoke local ES/EN servicio no-pesca con los tres inputs, respuesta obligatoria vacía y cero, recarga, modal normal/reforzado, stepper y cambio de grupo; pesca explícita sigue cobrando extras antiguos. Commit `feat: personalizaciones completas para servicio suelto` con paths explícitos de tarea 3.

### Tarea 4: Aislamiento PostgreSQL del modelo renombrado

**Archivos:** `backend/apps/bookings/tests_checkout_paquete.py`, `backend/apps/tenancy/tests_rls.py`, `backend/apps/fleet/tests_migrations_personalizaciones.py`.

**Consume:** tabla `bookings_reservapersonalizacion` tras RenameModel, política `tenancy_alcance` conservada. **Produce:** evidencia de aislamiento real del caso paquete existente y servicio suelto nuevo. No agregar un bypass RLS ni políticas duplicadas.

- [x] **1. Agregar caso de servicio suelto** a las pruebas RLS existentes de `tests_checkout_paquete.py` (TransactionTestCase con skipUnless PostgreSQL; crear datos dentro de scope de operador solo en setUp). Usar dos empresas, dos servicios y dos SP; la empresa B no ve filas A. El cuerpo de lectura bajo B debe ser:

```python
with scope.con_empresa(self.empresa_b):
    self.assertFalse(ReservaPersonalizacion.objects.filter(pk=fila_a.pk).exists())
    self.assertEqual(list(ReservaPersonalizacion.objects.values_list('pk', flat=True)), [fila_b.pk])
with connection.cursor() as cursor:
    cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
    self.assertEqual(cursor.fetchone(), (False, False))
    cursor.execute("SELECT policyname FROM pg_policies WHERE tablename=%s",
                   ['bookings_reservapersonalizacion'])
    self.assertIn(('tenancy_alcance',), cursor.fetchall())
```

Crear `fila_a`/`fila_b` con el modelo nuevo y reservas con servicio directo de su empresa; en el otro caso conservar reservas de paquete de la clase existente. Agregar intento INSERT bajo B con `reserva_id` A y `sp_id` A mediante `.objects.create` (sin full_clean): debe lanzar DatabaseError, capturado fuera de un `transaction.atomic()` anidado para no dejar transacción rota. Así la prueba demuestra RLS, no únicamente validación Python.

- [x] **2. Ejecutar caso en Postgres antes de modificar políticas.** En esta tarea de cobertura puede pasar desde el inicio: el RenameModel debe conservar RLS. No introducir deliberadamente un bug para obtener rojo. La prueba es la regresión que protege cambios posteriores. Si falla la policy o tabla, corregir únicamente migración de rename/whitelist; no ampliar alcance del rol.
- [x] **3. Verificar migración real conserva la política:** MigrationExecutor de bookings.0044 a bookings.0045, comparar existencia de política después y comprobar misma fila. `apps/tenancy/tests_rls.py` debe incluir nombre nuevo en whitelist, y seguir incluyendo `bookings_reservaextra` hasta tarea 11.
- [x] **4. Correr:** `manage.py test apps.bookings.tests_checkout_paquete apps.tenancy.tests_rls --settings=config.settings.ci` con DB local y rol indicado; todos los tests RLS ejecutados, sin skips PostgreSQL. Commit `test: proteger aislamiento de personalizaciones por empresa`.

### Tarea 5: Corte atómico del contrato de paquete

**Archivos:** `backend/apps/bookings/serializers.py`, `tests_checkout_serializer.py`, `tests_personalizaciones.py`; `backend/apps/payments/pricing.py`, `views.py`, `tests_pricing_paquete.py`, `tests_personalizaciones.py`; `frontend/src/components/checkout-view.tsx`, `paquete-card.tsx`; `frontend/src/lib/pricing-paquete.ts`, `frontend/tests/personalizaciones.test.cjs`.

**Consume:** selección completa y cargo/snapshot de tarea 3. **Produce:** `precio_paquete_total(paquete, *, personalizaciones_extra=None, personas=1, moneda='MXN') -> Decimal|None` conserva firma, pero `None`/`[]` significa ancla sin checks. `calcular_precio_paquete(paquete, moneda='MXN')` devuelve ancla. El precio del checkout incorpora únicamente selección explícita; la card sin selección muestra ancla. Orden cruza-empresa conserva precio_ancla fijo y reparto actual.

- [x] **1. Escribir pruebas rojas** en `tests_pricing_paquete.py` usando la fixture existente `CalcularPrecioPaqueteIntegrationTests` (crear p/sp específico en el test para no depender de nombres de fixtures antiguos):

```python
def test_recomendada_se_cobra_solo_si_viene_explicita(self):
    p = Personalizacion.objects.create(empresa=self.empresa, nombre='Licencia nueva',
        cobrar_por_persona=True, cantidad_editable=True)
    sp = ServicioPersonalizacion.objects.create(servicio=self.servicio_pesca,
        personalizacion=p, precio=Decimal('450'), preseleccionado=True)
    ancla = self.paquete.precio_ancla
    self.assertEqual(precio_paquete_total(self.paquete, personalizaciones_extra=[], personas=5), ancla)
    self.assertEqual(precio_paquete_total(self.paquete,
        personalizaciones_extra=[(sp.pk, 2)], personas=5), ancla + Decimal('900'))
    self.assertEqual(calcular_precio_paquete(self.paquete), ancla)
```

Convertir los tests viejos que exigían auto-inclusión a selección explícita y agregar caso desmarcada. No borrar escenarios de base/moneda/activo. Serializer de paquete: obligatorio input ausente falla, preseleccionado check explícito acepta y omitido acepta; SP de componente inactivo/otra empresa/repetido rechaza. Pago paquete ancla 6000 + licencia 900 = 6900, no 7800 ni 10500; snapshot 450×2; posterior cambio de catálogo no cambia estado pagado. Lista vacía recuperada sigue vacía tras recarga.

- [x] **2. Rojo:** `manage.py test apps.payments.tests_pricing_paquete apps.bookings.tests_checkout_serializer apps.payments.tests_personalizaciones`.
- [x] **3. Cambiar los tres consumidores juntos.** En `precio_paquete_total`, conservar normalización de `personalizaciones_extra` a dict y `precio_paquete` para cuantización. Cambiar bucle:

```python
total = Decimal(precio_ancla)
vistos = set()
for ps in paquete.servicios_asociados.filter(servicio__activo=True).select_related('servicio'):
    for sp in ps.servicio.servicio_personalizaciones.filter(
            activo=True, personalizacion__activo=True).select_related('personalizacion'):
        if sp.pk in vistos or sp.pk not in extras_map:
            continue
        vistos.add(sp.pk)
        p = sp.personalizacion
        if p.tipo_interaccion != 'check':
            continue
        cargo = cargo_personalizacion(sp.precio_en(moneda),
            cobrar_por_persona=p.cobrar_por_persona, cantidad_editable=p.cantidad_editable,
            personas=personas, cantidad=extras_map[sp.pk])
        if cargo is None:
            return None
        total += cargo
return precio_paquete(total)
```

En serializer usar el mismo conjunto activo para validación obligatorios y persistencia: `servicio_id__in` de componentes cuyo Servicio esté activo, `servicio__empresa=empresa` y `personalizacion__empresa=empresa`; no quitar control de empresa. Eliminar condición `sp.obligatorio or sp.preseleccionado` que rechazaba selección explícita. Para catálogo de paquete de la misma Empresa, todas las opciones aparecen y los inputs se validan igual que servicio suelto.

En `CrearPagoView` evitar sumar personalizaciones dos veces: rama paquete toma **solo** `reserva.paquete.precio_en(reserva.moneda)` como base (validar None), resolver `_resolver_personalizaciones` agrega cargo una sola vez al subtotal común. Extender pertenencia del resolver a componentes activos de paquete. Ya no llamar `precio_paquete_total` con selección y luego volver a sumar resolver. Mantener helper para otros consumidores y pruebas de cotización. Recuperación e inline de tarea 3 sirven sin segunda implementación.

- [x] **4. Unificar frontend de paquete.** `personalizacionesDisponibles` ya no filtra flags; `catalogoUnificado` se construye con `flatMap` de servicios y deduplicación por id SP. Inicialización/restauración de tarea 3 ahora aplica a paquete. Payload siempre manda lista completa, incluida `[]`. Reutilizar controls, modal, errores y stepper. Reemplazar cálculo interno de `calcularPrecioPaquete` por `totalPersonalizaciones` y ancla; conservar sus overloads y `esPaqueteCruzaEmpresa`/`formatearPrecio`. Cambiar `CalculoPrecioPaquete.totalPersonalizaciones` y `precioFinal` a `number|null` si moneda ausente; actualizar checkout/card para mostrar indisponibilidad y bloquear pago, no hacer fallback MXN. `paquete-card` sin selección usa ancla. Agregar test Node para input gratis aunque payload traiga cantidad y precio USD ausente; probar ancla + selección con helper compilado o prueba backend espejo. No cambiar el checkout de Orden.

- [x] **5. Verde:** suite backend completa (incluidos tests de Orden y traslado), helpers Node, lint/tsc/build. Smoke paquete: recomendado se puede quitar sin cargo, opcional inicialmente apagado, input requerido bloquea únicamente pago, recarga restaura texto y check desmarcado. Commit `feat: cobrar personalizaciones de paquete solo por seleccion explicita`.

### Tarea 6: Migrar configuración de pesca a Servicio sin perder precios

**Archivos:** crear `backend/apps/fleet/migrations/0031_tarifa_a_servicio.py`; ampliar `backend/apps/fleet/tests_migrations_personalizaciones.py`.

**Consume:** Tarifa por Empresa, Servicio existente o ausente, Reserva legacy. **Produce:** Servicio canónico con precios actuales MXN/USD, incluidas=3, ventana 05:00–07:00, estrategia por_grupo y referencias de reservas resueltas. Tarifa todavía existe. Las constantes se copian como valores históricos en migración (no imports de modelos runtime).

- [x] **1. Preparar test MigrationExecutor** en `TransactionTestCase`. Migrar primero al estado `fleet.0030`/`bookings.0044`, crear con `project_state(...).apps` una Empresa con Tarifa=5100, USD=300, recargo=600/USD=35 y Servicio previo con precio 1/ventana None; otra Empresa con Tarifa y sin Servicio. Ejecutar fleet.0031 y comprobar **también** actualización de precio de servicio existente, no solo defaults. Crear Reserva histórica sin producto y comprobar backfill; reserva de paquete no cambia. No importar Tarifa del modelo runtime en este test (se elimina en tarea 10).

Patrón del ejecutor y restauración (usar alias de connection y `alcance_operador_migracion` para fixtures históricas; restaurar incluso si una aserción falla):

```python
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

executor = MigrationExecutor(connection)
hojas = executor.loader.graph.leaf_nodes()
try:
    anterior = [('fleet', '0030_personalizacion_tipo_interaccion'),
                ('bookings', '0044_rls_orden_sin_current_query')]
    executor.migrate(anterior)
    historico = executor.loader.project_state(anterior).apps
    with alcance_operador_migracion(connection):
        SedeH = historico.get_model('tenancy', 'Sede')
        EmpresaH = historico.get_model('tenancy', 'Empresa')
        TarifaH = historico.get_model('fleet', 'Tarifa')
        ServicioH = historico.get_model('fleet', 'Servicio')
        sede = SedeH.objects.create(nombre='Sede migración', slug='sede-migracion')
        empresa = EmpresaH.objects.create(sede_id=sede.pk, nombre='Empresa migración', slug='empresa-migracion')
        empresa_id = empresa.pk
        TarifaH.objects.create(empresa_id=empresa_id, precio=Decimal('5100'),
            precio_usd=Decimal('300'), precio_persona_extra=Decimal('600'),
            precio_persona_extra_usd=Decimal('35'))
        ServicioH.objects.create(empresa_id=empresa_id, nombre='Pesca existente',
            slug='pesca-deportiva', tipo_servicio='pesca', precio_base=Decimal('1'),
            hora_apertura=None, hora_cierre=None)
    executor = MigrationExecutor(connection)
    executor.migrate([('fleet', '0031_tarifa_a_servicio')])
    actual = executor.loader.project_state([('fleet', '0031_tarifa_a_servicio')]).apps
    ServicioHistorico = actual.get_model('fleet', 'Servicio')
    with alcance_operador_migracion(connection):
        s = ServicioHistorico.objects.get(empresa_id=empresa_id, slug='pesca-deportiva')
        self.assertEqual(s.precio_base, Decimal('5100'))
        self.assertEqual((s.hora_apertura, s.hora_cierre), (time(5), time(7)))
finally:
    MigrationExecutor(connection).migrate(hojas)
```

`empresa_id` se obtiene de la Empresa histórica de la fixture; todos los modelos históricos se crean dentro del scope. No correr estos tests en paralelo contra la misma base. Agregar caso de empresa sin Tarifa con Reserva sin producto: falla explícitamente antes de inventar precio; ese dato de pruebas se corrige antes del drop, no se asigna a otra Empresa.

- [x] **2. Ejecutar rojo:** `manage.py test apps.fleet.tests_migrations_personalizaciones`; el target de migración todavía no existe.
- [x] **3. Crear migración aditiva** con dependencias `fleet.0030` y `bookings.0044` (no bookings.0045, ver despliegue):

```python
from datetime import time
from django.db import migrations

def migrar_tarifas(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion
    Tarifa = apps.get_model('fleet', 'Tarifa')
    Servicio = apps.get_model('fleet', 'Servicio')
    Reserva = apps.get_model('bookings', 'Reserva')
    db = schema_editor.connection.alias
    with alcance_operador_migracion(schema_editor.connection):
        for tarifa in Tarifa.objects.using(db).all().iterator():
            valores = dict(tipo_servicio='pesca', estrategia_cupo='por_recurso_dia',
                estrategia_precio='por_grupo', modo_ocupacion='exclusivo',
                precio_base=tarifa.precio, precio_base_usd=tarifa.precio_usd,
                precio_persona_extra=tarifa.precio_persona_extra,
                precio_persona_extra_usd=tarifa.precio_persona_extra_usd,
                personas_incluidas=3, hora_apertura=time(5), hora_cierre=time(7))
            existente = Servicio.objects.using(db).filter(
                empresa_id=tarifa.empresa_id, slug='pesca-deportiva').first()
            if existente and existente.tipo_servicio != 'pesca':
                raise RuntimeError(f'Slug pesca-deportiva ocupado por otro tipo en empresa {tarifa.empresa_id}')
            servicio, creado = Servicio.objects.using(db).get_or_create(
                empresa_id=tarifa.empresa_id, slug='pesca-deportiva',
                defaults=dict(nombre='Pesca Deportiva', activo=True, **valores))
            if not creado:
                Servicio.objects.using(db).filter(pk=servicio.pk).update(**valores)
            Reserva.objects.using(db).filter(empresa_id=tarifa.empresa_id,
                servicio_id__isnull=True, paquete_id__isnull=True).update(servicio_id=servicio.pk)
        for empresa_id in Reserva.objects.using(db).filter(
                servicio_id__isnull=True, paquete_id__isnull=True
                ).values_list('empresa_id', flat=True).distinct():
            servicio = Servicio.objects.using(db).filter(
                empresa_id=empresa_id, slug='pesca-deportiva', tipo_servicio='pesca').first()
            if servicio is None:
                raise RuntimeError(f'Falta configurar Servicio de pesca para empresa {empresa_id}')
            Reserva.objects.using(db).filter(empresa_id=empresa_id,
                servicio_id__isnull=True, paquete_id__isnull=True).update(servicio_id=servicio.pk)

class Migration(migrations.Migration):
    dependencies = [('fleet', '0030_personalizacion_tipo_interaccion'),
                    ('bookings', '0044_rls_orden_sin_current_query')]
    operations = [migrations.RunPython(migrar_tarifas, migrations.RunPython.noop)]
```

Conservar nombre/descripcion/activo del Servicio existente y sus asociaciones; no crear recursos duplicados ni alterar flota. La Tarifa es fuente actual de precio para pesca legacy, por eso se actualizan valores aunque Servicio exista desde 0018. No asignar todo `Reserva.servicio=None` a pesca: solo donde **también** paquete=None. No tocar reservas con servicio explícito ni componentes de Orden.

- [x] **4. Verde:** tests de migración en SQLite/Postgres, instalación limpia, suite backend. Verificar `migrate --plan` no exige bookings.0045 para aplicar fleet.0031 desde HEAD antiguo. Commit `feat: migrar tarifas de pesca a servicio canonico`.

### Tarea 7: Fixtures explícitas de pesca con ventana horaria

**Archivos:** `backend/apps/testing.py`, `backend/apps/bookings/tests.py`, `tests_tenancy.py`, `tests_cupo_rango.py`, `tests_concurrencia.py`, `backend/apps/payments/tests.py`, `backend/apps/finance/tests.py`, `backend/apps/notifications/tests.py` y cualquier test de esos módulos con construcción directa identificada por `rg`.

**Consume:** Servicio. **Produce:** `crear_servicio_pesca(empresa, **overrides) -> Servicio`, solo lo invocan los tests que lo necesitan, no siembra automáticamente en EmpresaTestCase. No usar una Empresa global para fixtures multiempresa.

- [x] **1. Conservar y ejecutar tests horarios/cupo antes de editar:** `manage.py test apps.bookings.tests apps.bookings.tests_cupo_rango apps.bookings.tests_concurrencia`. Tomar baseline de ventanas 04:59 inválida, 05:00 válida, 07:00 válida, 07:01 inválida.
- [x] **2. Agregar helper** en `apps/testing.py` (imports locales evitan modificar import graph innecesariamente):

```python
def crear_servicio_pesca(empresa, **overrides):
    from datetime import time
    from decimal import Decimal
    from apps.fleet.models import Servicio
    defaults = dict(nombre='Pesca Deportiva', tipo_servicio='pesca',
        estrategia_cupo='por_recurso_dia', estrategia_precio='por_grupo',
        modo_ocupacion='exclusivo', precio_base=Decimal('4500'),
        precio_base_usd=Decimal('260'), precio_persona_extra=Decimal('500'),
        precio_persona_extra_usd=Decimal('30'), personas_incluidas=3,
        hora_apertura=time(5), hora_cierre=time(7), activo=True)
    defaults.update(overrides)
    servicio, _ = Servicio.objects.get_or_create(empresa=empresa, slug='pesca-deportiva',
                                                 defaults=defaults)
    return servicio
```

Los precios por defecto del helper no sustituyen los montos explícitos de cada prueba. Si un escenario reutiliza Servicio con otros precios, asignar y guardar campos explícitamente (get_or_create no actualiza). En pruebas de cupo/finanzas crear una vez por setUp y pasar `servicio=self.servicio` a helpers `datos_reserva`/`crear_reserva`/`_datos`; cuando kwargs tenga `empresa`, usar el servicio de **esa** Empresa. En pruebas de API, `servicio` en payload es slug, no instancia. En pruebas paquete no enviar servicio simultáneamente. Añadir test del helper que conserva ventana y no duplica al llamarlo dos veces.

- [x] **3. Buscar construcciones restantes:** `rg -n "Reserva\(|Reserva.objects.create|datos_reserva|crear_reserva|def _datos" backend/apps -g 'tests*.py'`. Clasificar cada ocurrencia sin producto: caso negativo explícito queda; resto recibe fixture propia. Las pruebas de migración usan modelos históricos y mantienen casos sin producto intencionales. No retirar asserts de cupo ni rebajar fechas válidas para hacer pasar suite.
- [x] **4. Verde:** suite backend completa y concurrencia en Postgres. Commit `test: usar servicios explicitos en fixtures de pesca`.


### Tarea 8: Default de /reservar sobre Servicio

**Archivos:** `frontend/src/app/[lang]/reservar/page.tsx`, `frontend/src/components/checkout-view.tsx`. El retiro de exports muertos en api.ts se hace en tarea 10.

**Consume:** endpoint existente `getServicioDetalle(slug, empresaSlug)` y datos migrados tarea 6. **Produce:** `/reservar` sin producto envía `servicio:'pesca-deportiva'`; una URL de producto inválida muestra indisponibilidad, nunca cambia silenciosamente a pesca. UI legacy de extras permanece en pesca hasta tarea 11.

- [ ] **1. Comprobar comportamiento previo y caso esperado:** abrir `/es/reservar` y observar payload actual sin servicio. Preparar verificación de `/es/reservar?servicio=ausente&empresa=sal-y-sol` y `?paquete=ausente`: deben quedar sin producto, no ofrecer pesca por fallback. Verificar ES/EN.
- [ ] **2. Cambiar resolución del servidor:** quitar llamada/import de getTarifa y prop `tarifa` a CheckoutView. Sustituir bloque de resolución de servicio por:

```tsx
let servicio: ServicioCatalogo | null = null;
if (!paqueteSlug) {
  const slug = servicioSlug ?? 'pesca-deportiva';
  servicio = await getServicioDetalle(slug, empresaSlug).catch(() => null);
}
```

En props pasar `servicioId={servicio?.slug ?? null}` para no fingir producto resuelto con un slug inexistente; paquete inválido no provoca default. Quitar tarifa del tipo Props y destructuring de CheckoutView; `tieneProducto = Boolean(paquete || servicio)`. Mantener guardia de indisponibilidad si no hay producto resuelto.

- [ ] **3. Podar cálculos legacy de precio:** `usdDisponible` y `tourPrice` resuelven paquete/servicio, cierre defensivo null; recargo usa Servicio.precio_persona_extra/_usd y personas_incluidas, no constante cuando Servicio lo expone. Ejemplo de selección de moneda:

```tsx
const precioServicioRaw = servicio
  ? (moneda === 'USD' ? servicio.precio_base_usd : servicio.precio_base)
  : null;
const precioServicio = precioServicioRaw === null ? null : Number(precioServicioRaw);
```

No reemplazar la estrategia de hospedaje ni el precio de paquetes con esta expresión: integrarla en la rama existente de servicio y conservar cálculo de noches/estrategia. Mantener getExtras, selección/cantidad/modal legacy de pesca. `rg -n "tarifa" frontend/src/components/checkout-view.tsx` no debe dejar referencias a prop retirada.

- [ ] **4. Verde:** lint/tsc/build; smoke pesca sin parámetros y explícita con 3 y 5 personas, MXN/USD, brunch/licencia/carnada, recarga, servicio inválido y paquete inválido. Comparar total anterior con Tarifa de tarea 6 y actual con Servicio. Commit `refactor: resolver pesca predeterminada desde servicio`.

**Artefacto de despliegue puente:** este cambio de página/props/precio, aplicado sobre la UI anterior a tareas 3/5, es el frontend puente descrito en despliegue. No desplegar el HEAD final como si fuera ese puente; preparar un commit/release explícito con únicamente estos cambios compatibles si se ejecuta despliegue. El trabajo de este plan no publica nada.

### Tarea 9: Reserva exige producto y alta manual conserva default por Empresa

**Archivos:** `backend/apps/bookings/models.py`, `admin.py`, `tests_personalizaciones.py` y tests de admin existentes en `bookings/tests.py`.

**Consume:** fixtures tarea 7, resolución tarea 8. **Produce:** `Reserva.clean()` rechaza ambos campos vacíos; servicio/paquete siguen mutuamente excluyentes. Admin inicializa únicamente alta nueva sin producto y Empresa activa conocida.

- [ ] **1. Escribir rojo** sobre fixture de `PersonalizacionesModelTests`:

```python
def test_reserva_necesita_producto(self):
    self.reserva.servicio = None
    self.reserva.paquete = None
    with self.assertRaisesMessage(ValidationError, 'Selecciona un servicio o paquete'):
        self.reserva.full_clean()
```

Tests admin con RequestFactory y jefe/vendedora de EmpresaTestCase: GET add inicializa su pesca; Empresa B con mismo slug nunca se usa; formulario de edición no reemplaza servicio; paquete explícito en initial no se combina con pesca; operador sin Empresa no recibe default arbitrario.

- [ ] **2. Ejecutar rojo:** `manage.py test apps.bookings.tests_personalizaciones`.
- [ ] **3. Agregar al inicio de Reserva.clean después de super:**

```python
if not self.servicio_id and not self.paquete_id:
    raise ValidationError({'servicio': 'Selecciona un servicio o paquete.'})
if self.servicio_id and self.paquete_id:
    raise ValidationError({'paquete': 'No puedes seleccionar servicio y paquete a la vez.'})
```

Si ya hay exclusividad en `_validar_consistencia_de_empresa`, mantener una sola fuente de ese error. No modificar checks de cupo/ventana/deslinde/cambio de fecha. En ReservaAdmin:

```python
def get_changeform_initial_data(self, request):
    initial = super().get_changeform_initial_data(request)
    empresa = scope.empresa_actual(request)
    if empresa and not initial.get('servicio') and not initial.get('paquete'):
        servicio = Servicio.objects.filter(empresa=empresa, slug='pesca-deportiva',
                                           tipo_servicio='pesca', activo=True).first()
        if servicio:
            initial['servicio'] = servicio.pk
    return initial
```

Importar Servicio si no está; usar scope existente, no operador para saltar RLS. No rellenar servidor silenciosamente un POST inválido: el default pertenece al formulario de alta. La limpieza del help_text de Reserva.servicio se hace con AlterField en tarea 11, para mantener modelo/estado de migraciones iguales en cada gate.

- [ ] **4. Verde:** suite backend completa y formulario real de admin bajo vendedora/jefe. Commit `feat: exigir producto en reserva y facilitar alta de pesca`.

### Tarea 10: Retirar Tarifa y sus consumidores en un solo cambio

**Archivos:** `backend/apps/fleet/models.py`, `views.py`, `urls.py`, `serializers.py`, `admin.py`, `tests.py`, `management/commands/seed_local_demo.py`; crear `backend/apps/fleet/migrations/0032_retirar_tarifa.py`; `backend/apps/payments/views.py`, `tests.py`; `backend/apps/bookings/management/commands/setup_roles.py`; `backend/config/settings/base.py`, `health.py`, `tests_health.py`; `frontend/src/lib/api.ts`, `frontend/src/app/[lang]/reservar/loading.tsx`; `backend/CLAUDE.md`.

**Consume:** todas las reservas runtime tienen producto, Tarifa copiada en tarea 6. **Produce:** único precio base de pesca desde Servicio y estrategia PorGrupo. `TransporteTarifa`, `TarifaFija`, `tarifa_transporte.py` son otros conceptos y permanecen.

- [ ] **1. Cambiar pruebas de precio base antes de borrar:** donde `payments/tests.py` construya Tarifa, usar `crear_servicio_pesca` con exactamente los mismos cuatro precios y asociarlo a reserva. Mantener casos sin precio USD y sin recargo USD con más de 3 personas. Eliminar únicamente tests de CRUD/API del modelo retirado, reemplazando la cobertura negocio por endpoints de Servicio. Test health: `/healthz` debe seguir respondiendo 200 aunque no haya catálogo; NO introducir dependencia del Servicio en health. La función actual `config/health.py` ya es independiente de Tarifa, solo necesita limpiar comentario histórico.
- [ ] **2. Retirar consumidores y modelo juntos:** borrar import/clase Tarifa, TarifaView/TarifaSerializer/TarifaAdmin, ruta tarifa, menú Unfold y permiso `('fleet','tarifa',...)`. En CrearPagoView reemplazar rama fallback por guardia defensiva:

```python
# Cuerpo de la rama else de _post, que antes consultaba Tarifa:
return Response({'detail': 'La reserva no tiene servicio ni paquete configurado.'}, status=400)
```

Eliminar imports de `personas_extra`/`cargo_por_personas` de views si ya no se usan allí; los helpers siguen vivos en estrategias de precio. seed_local_demo crea Servicio directamente; conservar sus precios de demo y la regla de no sobreescribir credenciales/configuración existente. Eliminar `Tarifa`/`getTarifa` de api.ts; corregir comentarios en loading/CLAUDE.

- [ ] **3. Crear migración fleet.0032:**

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('fleet', '0031_tarifa_a_servicio')]
    operations = [migrations.DeleteModel(name='Tarifa')]
```

Quitar también `fleet_tarifa` del guardarraíl RLS si aparece como nombre explícito (la parte introspectiva ya no la encuentra). Las migraciones históricas de Tarifa permanecen intactas.
- [ ] **4. Verde y búsqueda:** `rg -n "\bTarifa\b|getTarifa|fleet_tarifa|['\"]tarifa['\"]" backend/apps backend/config frontend/src -g '!**/migrations/**'`. Las únicas referencias aceptables son pruebas de migración histórica/comentarios históricos deliberados; ningún import runtime/ruta/admin/permisos. Ejecutar instalación limpia + suite backend, lint/tsc/build, `manage.py setup_roles` en DB local y abrir admin para detectar reverse de menú inexistente. Commit `refactor: retirar tarifa legacy de pesca`.

### Tarea 11: Migrar extras, cortar pesca y cerrar catálogo único

**Archivos:** crear `backend/apps/fleet/migrations/0033_extrasitem_a_personalizacion.py`, `backend/apps/bookings/migrations/0046_retirar_reservaextra.py`, `backend/apps/fleet/migrations/0034_retirar_extrasitem.py`; `backend/apps/fleet/models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `tests.py`, `tests_migrations_personalizaciones.py`, `management/commands/seed_extras.py`; `backend/apps/bookings/models.py`, `serializers.py`, `admin.py`, `tests.py`, `tests_tenancy.py`, `tests_personalizaciones.py`, `management/commands/setup_roles.py`; `backend/apps/payments/pricing.py`, `views.py`, `tests.py`, `tests_personalizaciones.py`; `backend/apps/notifications/services.py`, `tests.py`; `backend/apps/tenancy/tests_rls.py`; `backend/config/settings/base.py`; `frontend/src/lib/api.ts`, `frontend/src/components/checkout-view.tsx`, `amenities-reminder.tsx`; `backend/CLAUDE.md`.

**Consume:** Servicio canónico, catálogo unificado, contrato nuevo operativo en otros servicios/paquetes. **Produce:** pesca usa exactamente el mismo payload/pricing/snapshot; ExtrasItem/ReservaExtra/getExtras desaparecen. `EstadoReserva*.personalizaciones` es la única selección devuelta. PuntoEncuentro y TransporteTarifa permanecen (los usa traslado).

- [ ] **1. Escribir pruebas rojas de migración de catálogo.** Sobre estado fleet.0032 + bookings.0045 crear ExtrasItem por Empresa con valores distintos MXN/USD; testea brunch, licencia editable, carnada, item inactivo, precio USD None, preseleccionado verdadero/falso y colisión con Personalizacion del mismo nombre. Verificar mismo precio y flags, aislado por Empresa. Sembrar dos veces después y comprobar que no cambien precios capturados ni duplique filas. La licencia queda recomendada/reforzada, cantidad_editable y cobrar_por_persona se preservan. El texto exacto «Paquete de Brunch» no cambia.

Si hay nombre coincidente con Personalizacion existente: reutilizar únicamente cuando campos de interacción/cobro sean compatibles; si asociación al Servicio ya existe con precio/config distinta, abortar con error identificando Empresa/nombre, **antes** de dropear. No sobrescribir configuraciones ajenas silenciosamente. Resolver ese conflicto de datos explícitamente al ejecutar migración, usando estado concreto del ambiente; no inventar nombres alternativos ni fusionar precios. Ampliar `Personalizacion.nombre` a max_length=150 en fleet.0033 antes de copiar (ExtrasItem permite 150); incluir AlterField y modelo final, preservando cualquier nombre de más de 100 caracteres y la unicidad. Esto es compatibilidad de esquema para los datos capturados, no un truncado.

- [ ] **2. Implementar traslado de catálogo** usando modelos históricos y alias DB, antes de los DeleteModel:

```python
def copiar_extras(apps, schema_editor):
    from apps.tenancy.rls import alcance_operador_migracion
    Extra = apps.get_model('fleet', 'ExtrasItem')
    Pers = apps.get_model('fleet', 'Personalizacion')
    SP = apps.get_model('fleet', 'ServicioPersonalizacion')
    Servicio = apps.get_model('fleet', 'Servicio')
    db = schema_editor.connection.alias
    with alcance_operador_migracion(schema_editor.connection):
        for extra in Extra.objects.using(db).all().iterator():
            servicio = Servicio.objects.using(db).filter(empresa_id=extra.empresa_id,
                slug='pesca-deportiva', tipo_servicio='pesca').first()
            if servicio is None:
                raise RuntimeError(f'Falta pesca-deportiva en empresa {extra.empresa_id}')
            licencia = extra.tipo == 'licencia'
            campos = dict(tipo=extra.tipo, tipo_interaccion='check',
                opciones_seleccion=[], aviso_reforzado=licencia,
                cobrar_por_persona=extra.cobrar_por_persona,
                cantidad_editable=extra.cantidad_editable, activo=extra.activo)
            p, creada = Pers.objects.using(db).get_or_create(
                empresa_id=extra.empresa_id, nombre=extra.nombre, defaults=campos)
            if not creada and any(getattr(p, k) != v for k, v in campos.items()):
                raise RuntimeError(f'Conflicto de catálogo: empresa {extra.empresa_id}, extra {extra.pk}')
            precio_flags = dict(precio=extra.precio, precio_usd=extra.precio_usd,
                obligatorio=False, preseleccionado=licencia or extra.preseleccionado,
                activo=extra.activo)
            sp, creada_sp = SP.objects.using(db).get_or_create(
                servicio_id=servicio.pk, personalizacion_id=p.pk, defaults=precio_flags)
            if not creada_sp and any(getattr(sp, k) != v for k, v in precio_flags.items()):
                raise RuntimeError(f'Conflicto de precio: empresa {extra.empresa_id}, extra {extra.pk}')
```

Esta función preserva campos exigidos por spec. No hay campo descripcion en Personalizacion; no simular que se preservó la descripción legacy. No migrar reservas/pagos históricos inexistentes según alcance; snapshots nuevos se crean en flujo nuevo, no a partir de precios actuales aplicados retroactivamente. Agregar test de rollback de migración que no deje copia parcial tras conflicto.

```python
# fleet/0033_extrasitem_a_personalizacion.py
dependencies = [('fleet', '0032_retirar_tarifa')]
operations = [
    migrations.AlterField('personalizacion', 'nombre', models.CharField(max_length=150)),
    migrations.RunPython(copiar_extras, migrations.RunPython.noop),
]
# bookings/0046_retirar_reservaextra.py
dependencies = [('bookings', '0045_rename_reservapersonalizacion'),
                ('fleet', '0033_extrasitem_a_personalizacion')]
operations = [
    migrations.DeleteModel(name='ReservaExtra'),
    migrations.AlterField('reserva', 'servicio', models.ForeignKey(
        'fleet.Servicio', on_delete=django.db.models.deletion.PROTECT,
        null=True, blank=True, related_name='reservas',
        help_text='Servicio o experiencia que ampara esta reserva. Vacío solo cuando hay paquete.')),
]
# fleet/0034_retirar_extrasitem.py
dependencies = [('fleet', '0033_extrasitem_a_personalizacion'),
                ('bookings', '0046_retirar_reservaextra')]
operations = [migrations.DeleteModel(name='ExtrasItem')]
```

Cada bloque pertenece a su `class Migration(migrations.Migration)` con imports `from django.db import migrations, models` e `import django.db.models.deletion` para AlterField; no ubicar los tres en una sola migración. Actualizar el help_text de Reserva.servicio en models.py al mismo texto de bookings.0046.

- [ ] **3. Corte simultáneo UI/serializer/pricing de pesca.** Quitar restricciones temporales `tipo_servicio != 'pesca'` para personalizaciones. Quitar extra serializer/campo/pops/sincronización y modelo ReservaExtra; `_guardar` recibe solo reserva+personalizaciones (revisar `_guardar_traslado`: conserva su firma propia y no depende de `_guardar`; no cambiar contrato público de TrasladoCheckoutSerializer). Quitar resolver legacy, usar `_resolver_personalizaciones` para cualquier Reserva con selección, paquete o servicio. Ya no existen dos cargos paralelos. Conservar validación de entrada y congelado atómico de tarea 3. Eliminar rama de cálculo de cargo_por_extra y helper si `rg` confirma cero consumidores vivos; sus tests de negocio pasan a cargo_personalizacion.

Quitar UI legacy (estado extrasSeleccionados/cantidadesExtras, getExtras, bloque JSX, payload extras, recuperación extras y adaptador tipo licencia). Construir todo desde catalogoUnificado para servicio o paquete; el modal recibe únicamente aviso_reforzado. El resumen pagado filtra checks y usa monto congelado; reanudación restaura también respuesta input. Cambiar tipos EstadoReservaPendiente/Pagada para retirar extras (y no retirar campos de transporte que aún usen consumidores ajenos sin comprobar referencias). `personalizaciones: []` se manda siempre y borra selección vieja.

- [ ] **4. Notificaciones y admin en el mismo cambio.** Reemplazar bucle de `_cuerpo_html` que leía extras_seleccionados por:

```python
lineas_personalizaciones = []
filas = (reserva.personalizaciones_seleccionadas.select_related(
    'servicio_personalizacion__personalizacion') if reserva.pk else [])
for fila in filas:
    personalizacion = fila.servicio_personalizacion.personalizacion
    if personalizacion.tipo_interaccion != 'check' or fila.subtotal is None:
        continue
    lineas_personalizaciones.append(
        f'<li><strong>{_html(personalizacion.nombre)}:</strong> {fila.cantidad} '
        f'— {fila.subtotal:.2f} {_html(reserva.moneda)} (incluido en tu pago)</li>')
extras = ''.join(lineas_personalizaciones)
```

`_html` ya existe en services.py y escapa texto de catálogo; conservar guardia `reserva.pk` porque los tests de correo también usan reservas sin guardar. Tests en notifications/tests.py: correo con licencia 450×2 contiene 900 en desglose, input texto no aparece; cambiar precio catálogo a 999 no cambia 900; `notificar_reserva_pagada` sigue llamando al canal WhatsApp con mail simulado. No enviar mensajes reales en pruebas. Inline ReservaExtra se elimina, el nuevo permanece; quitar menú Extras y permisos extrasitem/reservaextra (el nuevo view ya se agregó tarea 3). Quitar `bookings_reservaextra` de whitelist RLS y `fleet_extrasitem` si está explícita. Ejecutar setup_roles en DB limpia para demostrar ausencia de ContentType viejo requerido.

- [ ] **5. Reescribir seed_extras** con `--empresa` obligatorio, scope por Empresa y get_or_create de Personalizacion/SP. Mantener precios por defecto del comando anterior únicamente en defaults, no updates. Configuración exacta:

```python
semillas = [
    ('Paquete de Brunch', 'brunch', True, False, False, False, PLACEHOLDER_BRUNCH),
    ('Licencia de pesca', 'licencia', True, True, True, True, PLACEHOLDER_LICENCIA),
    ('Carnada', 'carnada', False, False, False, True, PLACEHOLDER_CARNADA),
]
for nombre, tipo, por_persona, editable, reforzado, recomendada, precio in semillas:
    p, _ = Personalizacion.objects.get_or_create(empresa=empresa, nombre=nombre,
        defaults=dict(tipo=tipo, tipo_interaccion='check', cobrar_por_persona=por_persona,
                      cantidad_editable=editable, aviso_reforzado=reforzado, activo=True))
    ServicioPersonalizacion.objects.get_or_create(servicio=servicio, personalizacion=p,
        defaults=dict(precio=precio, precio_usd=None, obligatorio=False,
                      preseleccionado=recomendada, activo=True))
```

`servicio` se resuelve por Empresa/slug pesca-deportiva dentro del scope; si falta, CommandError claro, sin precio inventado. Conservar siembra idempotente de PuntoEncuentro Marina La Costa existente. Contador de nuevos suma solo creados. Probar re-run después de editar precio a 777: sigue 777.

- [ ] **6. Reescribir pruebas legacy preservando escenarios.** Donde antes se creaba ExtrasItem, crear Personalizacion y ServicioPersonalizacion del Servicio de reserva; payload usa id SP. Donde se esperaba ReservaExtra, esperar ReservaPersonalizacion. No reemplazo global ciego: `cantidad_solicitada` antigua corresponde a `cantidad` de selección pendiente, mientras `cantidad` antigua pagada es cantidad efectiva congelada. Tests de aislamiento siguen usando dos empresas. Cubrir pesca default y explícita, licencia desmarcada con total base, brunch grupo completo, stepper licencia menor al grupo, USD sin precio 503, promoción/anticipo, 409/502 sin cambiar snapshot, recuperación pendiente/pagada y webhook/conciliación idempotentes.
- [ ] **7. Verde:** suite completa SQLite, suite completa Postgres no-bypass, instalación limpia y upgrade desde HEAD anterior; `manage.py check`, `makemigrations --check --dry-run`; helpers Node + lint/tsc/build. Smoke ES/EN pesca/paquete/servicio otro y regresión traslado/Orden. Commit `feat: unificar extras de pesca y retirar catalogo legacy` limitado a los paths afectados.

## Cierre verificable de implementación

- [ ] Confirmar cero imports/runtime de modelos y managers retirados; migraciones históricas y sus pruebas son excepciones deliberadas:

```powershell
rg -n "ReservaPaquetePersonalizacion|paquete_personalizaciones|extras_seleccionados|_resolver_extras|\bExtrasItem\b|\bReservaExtra\b|\bTarifa\b|getTarifa|getExtras" backend/apps backend/config frontend/src -g '!**/migrations/**'
git diff --check
```

- [ ] Revisar SQLite y Postgres con instalaciones nuevas y con migraciones aplicadas desde `4d5bef3`. Ejecutar suite `manage.py test apps config` completa en ambos motores; registrar números de pruebas, skips y errores reales. Si Postgres no está disponible, la implementación no se declara verificada en RLS.
- [ ] Frontend: registrar lint, tsc, build y helpers Node. Ejecutar en navegador: recomendadas marcadas al inicio, quitar/reforzado/continuar sin cargo, opcional apagada, stepper y grupo, inputs texto/número/selección, bloqueo solo al pagar/foco correcto, recarga restaura `[]` y respuestas, pagada muestra monto congelado; ambos idiomas. No usar Stripe live ni enviar notificaciones reales.
- [ ] Validar matriz de scope: catálogo/selección por Empresa, mismo SP no duplicado, servicio ajeno rechazado, input no aparece en Agenda, vendedora consulta respuesta sin editar catálogo/precio, Orden cruza-empresa y traslado conservan flujo.
- [ ] Actualizar notas técnicas de backend que aún describan auto-inclusión o Tarifa; no reescribir decisiones históricas de specs. Añadir evidencia de ejecución al final del plan solamente cuando se obtenga.
- [ ] Despliegue, si después se solicita: preparar release backend antiguo+migraciones aditivas hasta fleet.0031, frontend puente de tarea 8; verificar Servicio y extras legacy juntos. Cutover final con checkout temporalmente suspendido, migraciones restantes/código final/frontend final, roles sincronizados, smoke de tarjeta de prueba y reapertura. No aplicar rollback de código antiguo contra tablas eliminadas; una reversión requiere restaurar ambiente de pruebas coherente con su esquema. Este plan no ejecuta despliegue ni merge.

## Cobertura de spec y revisión del documento

| Requisito | Tareas |
|---|---|
| Checks recomendados removibles/opcionales, flag reforzado, 3 inputs gratis | 1, 2, 3, 5, 11 |
| Respuesta obligatoria/formatos, cero válido, selección exacta, id Empresa/Servicio | 2, 3, 5 |
| Cantidad editable por persona sin factor duplicado | 3, 5, 11 |
| Precio vigente al iniciar pago, snapshot, promoción/anticipo, moneda independiente | 3, 5, 10, 11 |
| Rename físico preserva RLS + caso servicio suelto | 2, 4 |
| Recuperación de selección/respuestas y monto pagado | 3, 5, 11 |
| Servicio pesca default, precios y ventana, fixtures y alta manual | 6, 7, 8, 9, 10 |
| Migración catálogo configurado, seed idempotente, permisos y correo | 1, 6, 11 |
| No respuestas en Agenda; traslados/Orden sin nuevas personalizaciones | 3, 5, 11 y cierre |
| SQLite/Postgres/frontend e instalación/upgrade | Cada gate y cierre |

**Estado:** documento de implementación retomado desde el mapa parcial; casillas sin marcar significan trabajo por ejecutar. Ninguna suite ni despliegue se afirma ejecutado por redactar este plan.

### Verificación del documento realizada el 2026-09-12

- Mapa revisado por agente arquitectónico independiente: APPROVED tras corregir contratos por fase, grafo de migraciones y despliegue.
- 11 tareas numeradas, 29 bloques Python analizados con `ast.parse` sin errores sintácticos; fences balanceados, sin marcadores de tareas por definir ni whitespace al final de línea. Los bloques son ejemplos de integración, no módulos completos verificados contra Django.
- Helper TypeScript y sus dos pruebas Node extraídos literalmente del documento a un directorio temporal: compilación TypeScript estricta exitosa y 2/2 pruebas exitosas (recomendada removible/cantidad efectiva y validación de cero/vacío/no finito).
- Esta evidencia solo valida el documento y esos ejemplos aislados. No se implementaron tareas, no se ejecutó la suite de la aplicación y no se modificaron bases de datos, migraciones runtime, despliegues ni cambios previos del worktree.
