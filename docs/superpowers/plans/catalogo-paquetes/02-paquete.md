# Paso 8 del backoffice: Catálogo y paquetes (orden, ayuda y vista previa)

## Problema (PFD)
El jefe arma servicios y paquetes pocas veces, así que no recuerda cómo se hacía: la pantalla tiene que explicarse sola.
- `ServicioAdmin` (`backend/apps/fleet/admin.py`) muestra 19 campos editables en una sola columna; solo 11 llevan ayuda y muchos solo aplican a cierto tipo de servicio (los de horario no sirven para hospedaje).
- `PaqueteAdmin` muestra ~13 campos planos y una tabla de componentes (`PaqueteServicioInline`) con columnas numéricas sin explicación (`orden`, `dia_estancia`, `salidas`, `noches`, `personas_incluidas`).
- Las reglas cruzadas (`errores_de_paquete`, `errores_de_precio_contra_transporte`) ya están bien hechas, pero solo se ven al guardar, juntas en una lista arriba, sin decir qué campo corregir.
- El menú lateral dice «Ocupaciones de hospedaje» y el nombre del modelo dice «ocupaciones de recursos».

## Decisión del dueño
Orden, ayuda y vista previa, **sin tocar las reglas de negocio** (no cambies `paquete_reglas.py` ni los cálculos de precio/cupo): campos agrupados por tarea y ocultando lo que no aplica al tipo; componentes con columnas explicadas; en el Paquete, un resumen del itinerario día por día, del precio por tamaño de grupo y de la cobertura del transporte; errores que digan qué corregir; y nombres de menú unificados.

## Tarea 2: formulario de Paquete, resumen y nombres del menú

La tarea 1 ya dejó `ServicioAdmin` ordenado. Léelo como ejemplo del estilo.

### Qué hacer
1. **`fieldsets` en `PaqueteAdmin`** (con título y `description`): **Qué es** (`nombre`, `slug`, `descripcion`, `sede`, `empresa_lider`, `activo`); **Precio** (`precio_ancla`, `estrategia_precio`, `personas_precio_base`, `precio_persona_extra`); **Reserva** (`pide_hora`); **Anticipo** (`permite_anticipo`, `porcentaje_anticipo`, ocultar `porcentaje_anticipo` con `conditional_fields` si `permite_anticipo` está apagado; verifica que no sea obligatorio); registro de solo lectura al final. Revisa `regla_precio` (probablemente interno): si no debe editarse, déjalo fuera de la edición como hoy. Verifica que NINGÚN campo editable quede fuera.
2. **Componentes explicados.** En `PaqueteServicioInline` el jefe necesita entender cada columna: añade una explicación breve y exacta sobre la tabla (qué es «día», «salidas», «noches», «personas incluidas», «orden»), con una `description`/texto en el inline o una plantilla de inline mínima (mira cómo Unfold permite `fieldsets` con `description` en un `TabularInline`; si no se puede, usa `help_text` en los campos desde el formulario del inline, no en el modelo). Lee `calendario_paquete.py` y `paquete_reglas.py` para que lo que digas sea CORRECTO (por ejemplo, que el día 1 es el inicio elegido por el cliente y que las salidas se repiten en días seguidos).
3. **Resumen del paquete.** Un campo de solo lectura `resumen_del_paquete` mostrado ARRIBA del formulario en la edición de un paquete ya guardado (en el alta nueva muestra «Guarda el paquete para ver su resumen.»), con tres partes en HTML seguro (`format_html`/`format_html_join` o una plantilla incluida; escapa todo lo que venga de la base):
   a. **Itinerario**: día por día, qué ocurre (por ejemplo «Día 1 · Hospedaje (3 noches)», «Día 2 y 3 · Pesca deportiva (2 salidas)»). Sale de las filas de `PaqueteServicio` (`dia_estancia`, `salidas`, `noches`) y de `calendario_paquete.py`; no reimplementes las reglas, reutiliza.
   b. **Precio por tamaño de grupo**: de 1 a 8 personas, el total en MXN con `paquete.precio_total_en('MXN', n)`.
   c. **Cobertura del transporte**: si el paquete incluye un servicio de transporte, por cada tamaño de grupo hasta `personas_incluidas` del traslado, el precio del paquete contra la peor tarifa (`peor_tarifa` y `errores_de_precio_contra_transporte` en `models.py` son la fuente; reutiliza `peor_tarifa`, no copies la lógica) y márcalo en rojo si el precio NO la cubre, con el mínimo que faltaría. Si no hay transporte, no muestres esta parte.
   Estilos en línea o clases que ya usa el panel de Finanzas (regla 6).
4. **Errores que dicen qué corregir.** Hoy `PaqueteServicioFormSet.clean` junta todos los mensajes en una lista. Mejora SOLO la presentación: que cada mensaje diga a qué campo o fila se refiere cuando eso se pueda saber con certeza (por ejemplo anteponer el nombre del servicio del componente), sin cambiar CUÁNDO se rechaza algo ni las funciones de `paquete_reglas.py`. Las pruebas existentes que comprueban estos mensajes deben seguir pasando o actualizarse con un texto equivalente (dilo en el reporte).
5. **Nombres del menú.** El menú lateral (`UNFOLD['SIDEBAR']` en `backend/config/settings/base.py`) dice «Ocupaciones de hospedaje» y el modelo `ReservaOcupacion` dice `verbose_name_plural = 'ocupaciones de recursos'` (en `backend/apps/bookings/models.py`). Unifica en «ocupaciones de hospedaje» (es lo que son hoy). **Esta es la ÚNICA migración permitida de toda la tarea**: cambiar el `verbose_name_plural` genera un `AlterModelOptions`; escríbela a mano en el siguiente número libre de `bookings` (mira la última), con las `options` COMPLETAS del modelo tal como quedan (copia el `verbose_name` y todo lo que ya tenga `Meta`) para que `makemigrations --check` quede limpio.

### Pruebas (archivo nuevo `backend/apps/fleet/tests_admin_paquete.py`)
- El alta y la edición del Paquete cargan (200); todos los campos editables están en algún fieldset.
- El resumen: itinerario correcto para un paquete con hospedaje + pesca de varias salidas; precios por grupo iguales a `precio_total_en`; la cobertura del transporte marca en rojo un paquete cuyo precio no cubre la tarifa y no marca uno que sí la cubre; un paquete sin transporte no muestra esa parte; el alta nueva muestra el mensaje de guardar primero; un nombre de servicio con HTML se escapa.
- Los errores del formset siguen rechazando lo mismo que antes (dos hospedajes, anticipo con dos empresas, precio bajo la tarifa) y ahora nombran el componente.
- `makemigrations --check` sin cambios; el menú lateral muestra «Ocupaciones de hospedaje» y el admin de esa lista carga.
