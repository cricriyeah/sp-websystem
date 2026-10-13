# Paso 7 del backoffice: Finanzas con detalle (Movimientos)

## Problema
El panel de Finanzas (`/admin/finanzas/`, `backend/apps/finance/`) muestra cifras (tarjeta, efectivo, transferencia, reembolsos, balance) por periodo y moneda, pero **ninguna cifra es un enlace**: el jefe que quiere cuadrar contra Stripe, la caja o el banco no puede ver qué reservas forman una cifra. La lista de Reservas filtra por fecha de VIAJE y el dinero se cuenta por fecha de MOVIMIENTO, así que no sirve para reconstruirlas.

## Decisiones ya tomadas por el dueño
1. Una **pantalla nueva «Movimientos»** a la que llega cada cifra del panel, con el mismo periodo, moneda y concepto de la cifra y un total al pie que COINCIDE con ella.
2. **Simplificar el panel**: quitar los tres cuadros fijos «Hoy», «Mes en curso» y «Año en curso»; el selector de periodo queda como único corte. Se conservan: las tres tarjetas «Lo que debería haber», el periodo elegido con su tabla y su gráfica, y el histórico día por día con navegación de meses.
3. **Cerrar un hueco de acceso**: hoy `puede_ver_finanzas` (en `backend/apps/tenancy/permisos_unfold.py`) y la vista dejan pasar a CUALQUIER usuario con empresa, incluida una vendedora; el menú se lo oculta pero abre la URL a mano. Finanzas es solo para **jefes y operadores de plataforma** (ver `backend/CLAUDE.md`, sección «Roles»; los jefes son el grupo Django `Jefe`).

## Cómo se calculan hoy las cifras (no lo cambies)
`backend/apps/finance/services.py`: cuatro movimientos por reserva, cada uno con su monto y su fecha:
tarjeta = `monto_pagado` / `pagada_en`; efectivo = `monto_efectivo` / `efectivo_cobrado_en`; transferencia = `monto_transferencia` / `transferencia_registrada_en`; reembolsos = `monto_reembolsado` / `reembolsada_en`. Cada moneda va por separado (nunca se suman MXN y USD). `Balance.neto` = entradas − reembolsos; `en_cuenta` (Stripe) = tarjeta − reembolsos; `en_efectivo` = efectivo; `en_banco` = transferencia. Los filtros son por la fecha del movimiento (`__date__gte/lte`).

## Tarea 2: enlaces en el panel y simplificación

La tarea 1 ya creó la ruta `finanzas_movimientos` y el servicio `movimientos`. Léelos primero.

### Qué hacer
1. **Enlaces.** En `finance/_tabla_balances.html` cada celda con cifra (Tarjeta, Efectivo, Transferencia, Reembolsos, Balance) pasa a ser un enlace a `{% url 'finanzas_movimientos' %}` con los parámetros `concepto` (`tarjeta`/`efectivo`/`transferencia`/`reembolsos`/`todos` para Balance), `moneda` (la de la fila) y, si la tabla tiene periodo, `desde` y `hasta` (AAAA-MM-DD). La plantilla se incluye con `balances=...`: pásale también `desde` y `hasta` con `{% include ... with balances=... desde=... hasta=... %}` (sin periodo = acumulado histórico: no mandes fechas). Una celda en cero NO se convierte en enlace (no hay nada que ver). Estilo: el enlace es el mismo número con subrayado discreto al pasar el cursor; no cambies la cifra ni el alineado. Las tres tarjetas «Lo que debería haber» enlazan igual: En la cuenta → `concepto=stripe`; En efectivo → `concepto=efectivo`; En el banco → `concepto=transferencia`; todas sin fechas (acumulado) y con la moneda de cada renglón.
2. **Histórico día por día.** Mira la última sección de `panel.html` (la tabla del histórico con `dias`): cada cifra de un día enlaza igual, con `desde=hasta=ese día`.
3. **Simplificar (decisión 2).** Quita de `panel.html` las secciones «Hoy», «Mes en curso» y «Año en curso» (las tres) y deja el resto. En `panel_financiero` (`views.py`) quita del contexto lo que ya no se usa SOLO si nada más lo usa (revisa que `resumen()` siga siendo usada por las tarjetas del acumulado; no borres funciones de `services.py` que otras partes o pruebas usen). El título del periodo elegido queda como el encabezado principal de la tabla.
4. Una línea de ayuda corta bajo el título del panel: «Toca una cifra para ver las reservas que la forman.».

### Pruebas (agrega a `backend/apps/finance/tests_movimientos.py` o crea `tests_panel_detalle.py`)
- Cada cifra distinta de cero del panel es un enlace cuya URL lleva el concepto, la moneda y las fechas correctas del periodo; una cifra en cero no es enlace.
- Siguiendo el enlace de una cifra, **el total de Movimientos es igual a la cifra** (prueba de punta a punta con el cliente de pruebas de Django para varios conceptos).
- Las tres tarjetas del acumulado enlazan a `stripe`/`efectivo`/`transferencia` sin fechas.
- El panel ya no contiene «Hoy ·», «Mes en curso» ni «Año en curso», y sigue mostrando el selector de periodo, la gráfica y el histórico.
- Las pruebas existentes de `tests.py` que fijaban esas secciones se actualizan (di cuáles en el reporte); no las borres sin reemplazo.
