# F8 — Asistente móvil: una navegación nueva, aparte de las tarjetas

> Fecha: 2026-10-18. Rama `feat/marca-sun-baja`, worktree `.claude/worktrees/qa`, sin push.
> Estado: **diseño propuesto, pendiente de la luz verde del dueño** (ver «Preguntas abiertas»).
> Reemplaza lo que la Task 8.4a hizo para móvil. Es la base de la 8.4b.
> Plan padre: `docs/superpowers/plans/2026-10-15-frontend-base-rediseno.md` (F8, Tasks 8.4a, 8.4b, 8.4c).

## 1. Qué pidió el dueño y qué se hizo mal

El dueño pidió una **forma de navegación completamente nueva** para móvil: un asistente de una pantalla por vez, con un botón grande fijo abajo y una flecha que va a la pantalla anterior. No pidió adaptar las tarjetas del checkout para que se comporten así.

La 8.4a (`5f5f1d5a`, más los arreglos `4de568ef` y `7f1a919e`) hizo lo contrario: dejó la máquina de tarjetas (`activo`, `editando`, `completado`, `suspendido`) y la forzó a parecer un asistente:

- Ocultó las tarjetas `completado` con `max-sm:hidden` (`ItemPaso` con `has-[[data-completado]]`, atributo `data-completado` en `CheckoutSectionCard`).
- Mandó el botón de la tarjeta activa a la barra con un portal (`PieDeTarjeta` + `useMovil` + `contexto-barra`).
- Ocultó «Cómo pagas» mientras hay algo reabierto (`mostrarDestino ... && editando === null`).

Consecuencias que el dueño vio en su teléfono:

1. Al dar atrás desde un paso, la flecha pone `editando` en el paso anterior mientras `actual` sigue siendo el paso nuevo. La tarjeta anterior aparece con «Listo» arriba, y la tarjeta del paso actual queda `suspendida`: una franja con solo el título («Tus datos»).
2. El botón grande de abajo desaparece, porque la tarjeta suspendida no tiene pie y el portal solo pinta el pie de una tarjeta activa.
3. Atrás no respeta los grupos de un paso: debería caer en la pantalla anterior, no en la primera del paso.

Causa de fondo: las tarjetas modelan «una respuesta ya dada que se reabre», no «ir y venir entre pantallas». Torcerlas otra vez no sirve.

## 2. El modelo

Solo en móvil (menos de 640 px). **Escritorio y tablet (640 px en adelante) conservan las tarjetas exactamente como están**, incluida la franja «Listo» y «Modificar».

- Cada ruta define una **lista ordenada de pantallas**. Se ve **una sola**. No hay tarjetas, ni renglones de pasos hechos, ni «Listo», ni «Modificar».
- Cada pantalla tiene título (`texto-paso`), el contenido y su validación.
- **Botón grande fijo abajo («Continuar»)**: valida la pantalla y pasa a la siguiente. En la última pantalla de Pago es el botón de pagar.
- **Flecha de arriba**: va a la pantalla anterior, solo a esa. Si estás en el segundo servicio de un paquete, cae en el primero; si estás en «Tus datos», cae en la última pantalla de Viaje. En la primera pantalla sale al origen (`lib/origen.ts`, como hoy).
- **Atrás del navegador**: lo mismo, porque cada pantalla es una entrada de historial (`pushState`). Ir y venir no pierde nada de lo capturado: el estado vive en los reducers existentes y en el borrador de la pestaña.
- **Línea de progreso** (`reserva/linea-progreso.tsx`, ya existe): tres segmentos, Viaje, Datos y Pago; la pantalla actual lleva su nombre debajo.
- **Asa «Ver resumen · $X»** y la **hoja de resumen** (ya existen en `barra-inferior.tsx`): se conservan tal cual.
- Cambio de pantalla: foco al título de la pantalla y anuncio con `aria-live`. Animación de entrada 250 ms (`translateX(24px) → 0`) solo en el contenido; las pantallas de Pago, solo fundido de 150 ms. El contenedor de Stripe nunca lleva `transform`, `filter` ni `will-change`. La barra, la cabecera y el aviso son **hermanos** del contenedor que anima, nunca hijos (un ancestro con `transform` rompe `position: fixed`).
- `prefers-reduced-motion`: sin traslado, solo fundido.

## 3. Pantallas por ruta (propuesta)

**Servicio suelto** (`checkout-view.tsx`):
1. Fecha, hora y personas (`BloqueViaje`).
2. Extras (`BloqueExtras`); se omite si el servicio no tiene.
3. Tus datos (`BloqueContacto`).
4. Cómo pagas (moneda, forma de pago, promo, deslinde, antibots).
5. Tarjeta.

**Paquete de una empresa** y **cruza-empresa** (`pedido-paquete.tsx`):
1. Fecha de inicio.
2. Una pantalla por servicio del paquete (`GrupoServicio`): personas, extras y traslado del servicio.
3. Tus datos (`BloqueContacto`).
4. Recogida («¿Dónde te recogemos?», `GrupoDatos`), solo si algún servicio lleva traslado. La pregunta y la zona con título ya existen (`48bb6969`).
5. Cómo pagas.
6. Tarjeta; en cruza-empresa, una por empresa («Pago 1 de 2», «Pago 2 de 2»).

**Traslados** (`traslado-view.tsx`):
1. Tipo de traslado.
2. Fecha (y fecha de regreso si el tipo es `redondo_aeropuerto`).
3. Hora y pasajeros.
4. Tus datos.
5. Recogida.
6. Cómo pagas.
7. Tarjeta.

Los pasos de 3 segmentos mapean así: pantallas de Viaje → Viaje; Tus datos y Recogida → Datos; Cómo pagas y Tarjeta → Pago.

## 4. Arquitectura propuesta

Principio: **la capa del asistente es nueva y no toca las tarjetas**. Reutiliza los bloques de contenido (`BloqueViaje`, `BloqueExtras`, `BloqueContacto`, `GrupoServicio`, `GrupoDatos`, `FechaPaquete`, `TipoTrasladoCards`, etc.) y los reducers.

1. **Módulo puro `src/lib/pantallas-checkout.ts` con prueba primero** (`tests/pantallas-checkout.test.cjs`, registrado en `tests/run-hub-tests.cjs`). Dada la ruta y sus condiciones (si hay extras, si hay traslado, cuántos servicios, cuántas empresas), devuelve la lista de pantallas `{ id, paso: 'viaje' | 'datos' | 'pago' }[]`, y funciones `siguiente`, `anterior`, `pasoDeLaPantalla`. Sin React.
2. **Hook `use-pantalla-movil`** (`src/components/reserva/`): guarda el índice de pantalla, lo sincroniza con el historial (extiende `lib/paso-url.ts` y `use-paso-url.ts`; hoy cada paso es una entrada, pasaría a ser cada pantalla), y con el borrador de la pestaña (`lib/borrador-reserva.ts`). Solo se activa en móvil (`useMovil`).
3. **Componente `AsistenteMovil`**: recibe la lista de pantallas con su `render` y su `validar`, muestra la activa, y entrega a la `BarraInferior` el botón («Continuar» o pagar). La barra deja de depender del portal de `PieDeTarjeta`.
4. **Validación por pantalla.** Hoy se valida por paso completo (`confirmarViaje`, `confirmarContacto`, `confirmarDatos` y `lib/validar-reserva.ts`, `lib/campo-paso.ts`). Hay que partirla por pantalla reutilizando los validadores de campo; el error queda pegado a su campo (`ErrorDeCampo`), como hoy.
5. **Cada ruta compone su lista** (`checkout-view`, `pedido-paquete`, `traslado-view`) con los bloques que ya renderiza. En escritorio y tablet siguen renderizando las tarjetas; en móvil renderizan `AsistenteMovil`.
6. **Pago en dos pantallas** (lo que pedía la 8.4b): «Cómo pagas» (moneda junto al total, forma de pago, promo, deslinde, antibots) con botón «Continuar a la tarjeta» que crea la reserva u orden y retiene; luego «Tarjeta» con «Pagar $X a [empresa]». El botón de pagar de la pantalla Tarjeta se renderiza **dentro de `<Elements>`** (portal) para poder llamar a `confirmPayment`; la barra se monta siempre en el chunk principal con el botón deshabilitado y la razón «Cargando el formulario de pago…», y el chunk de Stripe solo aporta el `onClick`. Los textos «Pago 1 de 2 · [empresa] · $X» van en la primera línea de la pantalla.
7. **Razón del botón deshabilitado** debajo del botón, en una ranura de 20 px reservada solo en pantallas con botón (por ejemplo «Elige una fecha para continuar», «Verificando que eres una persona…»). Cada pantalla declara su razón.

## 5. Qué hay que revertir o reevaluar de la 8.4a

- **Revertir** (era la adaptación de tarjetas): el `max-sm:has-[[data-completado]]:hidden` de `checkout/item-paso.tsx`, el atributo `data-completado` de `checkout-section-card.tsx`, el portal por `useMovil` en `checkout/pie-tarjeta.tsx` (queda el `PieDeTarjeta` plano de escritorio) y, si aplica, la condición `editando === null` que se añadió a `mostrarDestino` en `checkout-view.tsx` y `traslado-view.tsx` y a `pedido-paquete.tsx` (`4de568ef`). Ojo: ese arreglo también afectó a escritorio; al revertir, comprobar que en escritorio el comportamiento es el de antes de la 8.4a.
- **Conservar**: `reserva/linea-progreso.tsx`, `reserva/barra-inferior.tsx` (asa y hoja), `reserva/contexto-barra.tsx` (resumen vivo para la hoja), `reserva/use-movil.ts`, `checkout/pago/cuerpo-resumen.tsx`, `lib/etiqueta-boton.ts` y su prueba, `--barra-alto`, y el borrado de `checkout-stepper.tsx`, `cifra-animada.tsx` y `franja-resumen.tsx`.
- **Reevaluar**: el `ResumenPedido` oculto en móvil (`max-sm:hidden`); la ayuda flotante y el toast ya se apartan de la barra con `--barra-alto`.

## 6. Orden de trabajo y reglas

Un commit por tarea, con prefijo `feat(reserva):`, y `npm run verificar` en verde en cada uno. Sin push.

1. Módulo puro `pantallas-checkout` con sus pruebas.
2. Hook `use-pantalla-movil` y extensión de la URL y del borrador.
3. `AsistenteMovil` y adaptación de `BarraInferior` (botón, razón, foco, `aria-live`, animación).
4. Servicio suelto en el asistente (la ruta más simple), con la reversión de lo de la 8.4a.
5. Paquete (una empresa y cruza-empresa), incluida la recogida.
6. Traslados.
7. Pago en dos pantallas con la barra dentro de Stripe (8.4b), «Pago 1 de 2» y el rechazo en «Pago 2 de 2».
8. Actualizar el plan padre (Tasks 8.4a/8.4b) y `docs/design/design-components.md`.

Reglas del dueño que aplican:
- **Todo frontend:** explicar y esperar su luz verde antes de tocar código. Una pregunta reflexiva no es luz verde.
- **Puerta de taste:** `perception-first-design` para decidir, `design-taste-frontend` para construir.
- **Verificación sin navegador:** `tsc`, `eslint`, pruebas y `build`; el dueño mira el sitio en su teléfono y en escritorio.
- **Mensajes de commit:** terminar con `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## 7. Preguntas abiertas (el dueño no las ha contestado)

1. ¿Las pantallas de la sección 3 le parecen bien, o quiere juntar o separar alguna? Por ejemplo, Extras junto a Fecha y personas, o Recogida junto a Tus datos.
2. ¿Confirma que escritorio y tablet no cambian (siguen con tarjetas y «Listo»)?
3. En cruza-empresa, ¿cada empresa del paquete tiene su pantalla de Tarjeta, o se pagan juntas? (Hoy son cobros separados, uno por empresa.)

## 8. Estado del entorno al escribir este documento

- HEAD de la rama: `48bb6969` (recogida con pregunta y zona con título). Antes: `7f1a919e`, `4de568ef`, `5f5f1d5a`, `b6fdffd5` (avisos), `445642a4` (título y «Paso N de 3»).
- `npm run verificar` en verde; guardia en 21 infracciones, línea base 21.
- Servidores locales: backend `python manage.py runserver 8000` y frontend `npm run dev` (puerto 3000), ambos desde el worktree `qa`; pueden no seguir arriba en otra sesión.
- Nada probado en navegador móvil.
