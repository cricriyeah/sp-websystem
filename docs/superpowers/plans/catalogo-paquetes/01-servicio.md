# Paso 8 del backoffice: Catálogo y paquetes (orden, ayuda y vista previa)

## Problema (PFD)
El jefe arma servicios y paquetes pocas veces, así que no recuerda cómo se hacía: la pantalla tiene que explicarse sola.
- `ServicioAdmin` (`backend/apps/fleet/admin.py`) muestra 19 campos editables en una sola columna; solo 11 llevan ayuda y muchos solo aplican a cierto tipo de servicio (los de horario no sirven para hospedaje).
- `PaqueteAdmin` muestra ~13 campos planos y una tabla de componentes (`PaqueteServicioInline`) con columnas numéricas sin explicación (`orden`, `dia_estancia`, `salidas`, `noches`, `personas_incluidas`).
- Las reglas cruzadas (`errores_de_paquete`, `errores_de_precio_contra_transporte`) ya están bien hechas, pero solo se ven al guardar, juntas en una lista arriba, sin decir qué campo corregir.
- El menú lateral dice «Ocupaciones de hospedaje» y el nombre del modelo dice «ocupaciones de recursos».

## Decisión del dueño
Orden, ayuda y vista previa, **sin tocar las reglas de negocio** (no cambies `paquete_reglas.py` ni los cálculos de precio/cupo): campos agrupados por tarea y ocultando lo que no aplica al tipo; componentes con columnas explicadas; en el Paquete, un resumen del itinerario día por día, del precio por tamaño de grupo y de la cobertura del transporte; errores que digan qué corregir; y nombres de menú unificados.

## Tarea 1: formulario de Servicio

### Qué hacer (solo `ServicioAdmin` en `backend/apps/fleet/admin.py` y sus pruebas)
1. **`fieldsets` por tarea**, con título y `description` corta en español para cada bloque. Propuesta (ajusta si un campo tiene más sentido en otro bloque, y verifica que NINGÚN campo editable quede fuera): **Qué es** (`nombre`, `slug`, `tipo_servicio`, `descripcion`, `activo`); **Cupo** (`estrategia_cupo`, `modo_ocupacion`, `capacidad_maxima`); **Precio** (`estrategia_precio`, `precio_base`, `precio_persona_extra`, `personas_incluidas`); **Horario** (`pide_hora`, `paso_hora_minutos`, `hora_apertura`, `hora_cierre`); **Anticipo y visibilidad** (`permite_anticipo`, `porcentaje_anticipo`, `solo_en_paquete`). Los campos de solo lectura (`creado_en`, `actualizado_en`) en un bloque «Registro» plegado al final. `empresa` se sigue manejando como hasta ahora (lo quita/pone `EmpresaScopedAdminMixin`: mira cómo para no romper el alta; si el mixin ya quita el campo, no lo pongas en los fieldsets).
2. **Ayuda sin migraciones**: para los campos que no tienen `help_text` en el modelo y no se explican solos (`estrategia_cupo`, `modo_ocupacion`, `estrategia_precio`, `paso_hora_minutos`, `hora_apertura`, `hora_cierre`, `capacidad_maxima`, `solo_en_paquete`, `tipo_servicio`), pon una línea de ayuda en español escrita para quien arma el servicio por primera vez (qué elige y qué pasa), usando `formfield_for_dbfield` o `get_form`. Lee los `choices` y el resto del código (`apps/fleet/enums.py`, `apps/bookings/cupo/`) para que cada explicación sea CORRECTA; si no puedes verificar un efecto, no lo afirmes.
3. **Ocultar lo que no aplica** con `conditional_fields` (regla 7): los campos de horario cuando `tipo_servicio` es hospedaje; `porcentaje_anticipo` cuando `permite_anticipo` está apagado; los de precio por persona/personas incluidas solo cuando la estrategia de precio los usa. Verifica en `enums.py`/`pricing.py` qué estrategias usan qué campos, y comprueba que cada campo oculto NO es obligatorio.
4. La lista (`list_display`, `list_filter`) no cambia.

### Pruebas (archivo nuevo `backend/apps/fleet/tests_admin_catalogo.py`)
- La página de alta y de edición de un Servicio carga (200) con jefe y con operador; todos los campos editables del modelo aparecen en algún fieldset (prueba que compara `fields` del formulario contra los fieldsets).
- Los bloques están en el HTML con su título; los campos con ayuda nueva muestran su texto.
- `conditional_fields` solo referencia campos NO obligatorios (prueba que lo comprueba contra el modelo).
- Guardar un Servicio de hospedaje sin campos de horario sigue funcionando; guardar uno de pesca con horario sigue funcionando (POST completo).
- `python manage.py makemigrations --check` sin cambios (si puedes, una prueba con `call_command('makemigrations', check=True, dry_run=True)`).
