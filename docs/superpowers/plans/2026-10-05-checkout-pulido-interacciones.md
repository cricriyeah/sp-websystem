# Checkout: pulido de interacciones (transiciones, calendario, tipo de traslado) — Plan

> **Para quien ejecute:** un commit por tarea, `git add` por ruta (nunca `-A`). Todo texto nuevo en `es.json` y `en.json`; tras tocar diccionarios reiniciar `npm run dev`. Solo clases Tailwind ya existentes. Gate por tarea desde `frontend/`: `npx.cmd tsc --noEmit`, `npx.cmd eslint src tests`, `npm.cmd test`; `npm.cmd run build` al cerrar la Tarea 5. Si el plan y el código discrepan, PARAR y preguntar. Este plan va DESPUÉS de las Tareas 11-12 del plan `2026-10-02-checkout-anatomia-unificada.md` (ambos tocan `stripe-panel.tsx`).

**Meta:** que los controles que se abren o cambian lo hagan de forma continua, que el calendario del mes ocupe el ancho de su contenedor, que "tipo de traslado" se vea igual en el paquete y en `/traslados`, y que la fecha de regreso quede pegada al tipo que la provoca.

## Diseño aprobado (derivación Perception-First, 2026-10-05; dueño dio luz verde)

- **R1 (L0):** ≤4 bloques por card; una fecha secundaria pesa menos que la principal.
- **R2 (L1):** el mes en línea ocupa el 100 % del ancho y alinea sus 7 columnas con la tira semanal.
- **R3 (L2):** la misma decisión usa el mismo componente y la misma apariencia (tipo de traslado).
- **R4 (L3):** todo despliegue/plegado se anima (altura + opacidad, ~150–250 ms), respeta `prefers-reduced-motion` y no hace saltar CTA ni total.
- **R5 (L4):** el efecto aparece pegado a su causa; lo secundario va plegado con control a la mano; el desplegado no compite con el CTA de pago.

**Decisiones del dueño:** (1) la fecha de regreso del traslado pasa a una **fila compacta** bajo el selector de tipo ("Regreso: sáb 12 oct · Cambiar"); la tira semanal se despliega al pulsar; la tira siempre visible queda solo para la fecha de inicio (card Viaje). (2) Se puede tocar `traslado-view.tsx` únicamente para usar el componente compartido de tarjetas de tipo, **sin cambio visual** allí. (3) En el paquete el traslado va incluido en el precio: las tarjetas de tipo no llevan "Desde $".

**Reglas de diseño que ya existen y se respetan:** la fecha de regreso NO se prellena (sin respuesta se muestra la pregunta; `DateField` documenta por qué: no sugerir una elección que el cliente no hizo). `traslado-view.tsx` ya anima con `motion/react` y `sinMovimiento`; se reutiliza esa convención.

## Mapa de archivos

| Archivo | Acción |
|---|---|
| `frontend/src/components/checkout/despliegue.tsx` | crear: primitivo de transición |
| `frontend/src/components/date-field.tsx` | modificar: `PanelCalendario` con modo ancho completo |
| `frontend/src/components/pedido/fecha-paquete.tsx` | modificar: mes animado y a ancho completo; variante compacta de regreso |
| `frontend/src/components/stripe-panel.tsx` | modificar: código promocional y mensajes con `Despliegue` |
| `frontend/src/components/checkout/tipo-traslado-cards.tsx` | crear: tarjetas de tipo compartidas |
| `frontend/src/components/traslado-view.tsx` | modificar: usar el componente compartido (sin cambio visual) |
| `frontend/src/components/pedido/grupo-servicio.tsx` | modificar: tarjetas compartidas, regreso compacto tras el tipo, bloques con `Despliegue` |
| `frontend/src/app/[lang]/dictionaries/{es,en}.json` | modificar solo si falta algún texto (p. ej. "Cambiar" en la fila de regreso) |
| `frontend/CLAUDE.md` | modificar: documentar `Despliegue` y `TipoTrasladoCards` |

---

### Tarea 1: Primitivo `Despliegue`

**Archivo:** crear `frontend/src/components/checkout/despliegue.tsx`.

- [ ] **Paso 1:** Leer `checkout-section-card.tsx`, `field-popover.tsx` y `traslado-view.tsx` (uso de `motion`, `AnimatePresence`, `sinMovimiento`) para copiar la convención exacta de duración y easing del proyecto. No inventar otra.
- [ ] **Paso 2:** Crear `Despliegue({ abierto, children, className })`: monta/desmonta con `AnimatePresence` (`initial={false}`), anima `height: 'auto'` y `opacity`, ~200 ms ease-out, `overflow: hidden` mientras anima. Con `prefers-reduced-motion` (usar el mismo hook que ya use `traslado-view`) solo anima opacidad, sin altura. Debe ser accesible: el contenido desmontado no queda en el árbol.
- [ ] **Paso 3:** Gate y commit: `feat(checkout): primitivo Despliegue para abrir y plegar sin saltos`.

### Tarea 2: Calendario del mes a ancho completo

**Archivos:** `date-field.tsx`, `fecha-paquete.tsx`.

- [ ] **Paso 1:** `PanelCalendario`: nueva prop opcional `anchoCompleto?: boolean`. Con `true` el contenedor es `w-full` (sin `sm:w-72`); el popover de `DateField` mantiene el ancho actual (sin prop). Las celdas del mes siguen usando `grid-cols-7`, así que alinean con la tira semanal.
- [ ] **Paso 2:** En `FechaPaquete`, pasar `anchoCompleto` al mes y darle al contenedor esquinas `rounded-lg` (hoy tiene `border` recto mientras los días son `rounded-lg`). Ajustar la altura de las celdas del día (`h-9`) para que el mes en línea se vea proporcionado con la tira (revisar sin navegador: coherencia de clases con la tira, que usa `min-h-14`).
- [ ] **Paso 3:** Envolver el mes en `Despliegue` (sustituye `{mesAbierto && …}`).
- [ ] **Paso 4:** Gate y commit: `fix(checkout): calendario del mes ocupa el ancho del contenedor y se despliega animado`.

### Tarea 3: Código promocional y mensajes animados

**Archivo:** `stripe-panel.tsx` (líneas ~298-340).

- [ ] **Paso 1:** El intercambio botón → etiqueta+input pasa por `Despliegue` (el botón se pliega, el campo se despliega, sin salto del panel).
- [ ] **Paso 2:** Los mensajes de estado (`verificando`, `valido`, `invalido`) entran/salen con `Despliegue`; reservar la altura de una línea mientras `promoEstado !== 'idle'` para que el total no brinque al cambiar entre estados.
- [ ] **Paso 3:** No cambiar la lógica de promo ni los textos. Gate y commit: `feat(checkout): transiciones continuas en el codigo promocional`.

### Tarea 4: `TipoTrasladoCards` compartido

**Archivos:** crear `checkout/tipo-traslado-cards.tsx`; modificar `traslado-view.tsx` y `grupo-servicio.tsx`.

- [ ] **Paso 1:** Extraer EXACTAMENTE el marcado de `traslado-view.tsx:601-639` (tarjeta `rounded-xl p-4`, icono por tipo, palomita, título, descripción `line-clamp-3`, "Desde …" opcional). Props: `tipos`, `valor`, `onChange`, `textos` (`traslados.types`), `iconoDe(tipo)`, `precioDesde?: (tipo) => string | null`, `nombre` (name del grupo accesible). Accesibilidad: conservar semántica de botones o radio, lo que `traslado-view` ya haga; añadir `role="radiogroup"` si procede.
- [ ] **Paso 2:** `traslado-view.tsx` pasa a usar el componente. **Verificación obligatoria:** el JSX resultante genera las mismas clases y la misma estructura que antes (diff de clases = cero). Mantener fuera los efectos de `onClick` específicos (limpiar `fechaRegreso`) en el `onChange` del padre.
- [ ] **Paso 3:** `grupo-servicio.tsx:230-241`: sustituir las píldoras por el componente, SIN `precioDesde` (el traslado va incluido en el precio del paquete). Reutilizar los iconos de `traslado-view` (mover `getIconoTipo` a un módulo compartido si hace falta; no duplicarlo).
- [ ] **Paso 4:** Gate y commit: `refactor(checkout): tarjetas de tipo de traslado compartidas entre paquete y traslados`.

### Tarea 5: Regreso compacto pegado al tipo y bloques animados

**Archivos:** `fecha-paquete.tsx`, `grupo-servicio.tsx`, diccionarios si falta texto.

- [ ] **Paso 1:** En `fecha-paquete.tsx` añadir `FechaRegresoCompacta` (o variante `compacta` de `FechaPaquete`): fila con etiqueta, valor formateado ("Regreso: sáb 12 oct") o la pregunta si aún no hay fecha, y un botón "Cambiar"/"Elegir" que despliega (con `Despliegue`) la tira semanal + mes ya existentes. Al elegir una fecha se pliega sola. Sin prellenado.
- [ ] **Paso 2:** En `grupo-servicio.tsx` mover el regreso a justo después de las tarjetas de tipo y antes de punto de encuentro/dirección. Orden final del bloque: tipo → regreso (solo `redondo_aeropuerto`) → dónde (punto/dirección, zona) . Aparece/desaparece con `Despliegue` al cambiar de tipo.
- [ ] **Paso 3:** Envolver con `Despliegue` el cambio punto de encuentro ↔ dirección libre y el fieldset de zona.
- [ ] **Paso 4:** Auditoría: listar cualquier otro cambio instantáneo de bloques en `grupo-servicio.tsx` y `pedido-paquete.tsx` (render condicional que aparece/desaparece sin transición). Anímalos con `Despliegue` si son disclosures; si no es claro, NO tocar y reportar la lista.
- [ ] **Paso 5:** Que errores de validación de la fecha de regreso sigan llevando a la tarjeta correcta (no romper `setEditando`).
- [ ] **Paso 6:** Gate completo + `npm.cmd run build` y commit: `feat(checkout): fecha de regreso compacta junto al tipo de traslado y bloques animados`.

### Tarea 6: Documentación

- [ ] `frontend/CLAUDE.md`: añadir en "Checkout unificado de paquetes" que todo despliegue usa `Despliegue`, que el tipo de traslado usa `TipoTrasladoCards`, que el mes en línea usa `anchoCompleto` y que la fecha de regreso del traslado es compacta. Commit: `docs(frontend): documenta Despliegue y tarjetas de tipo de traslado`.
