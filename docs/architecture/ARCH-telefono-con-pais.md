# ARCH: teléfono con selector de país (los tres checkouts)

> Lector: el dueño (aprueba) y el senior-dev que lo implementa. Decisión: cómo guardar, validar y mostrar el teléfono con código de país sin que ningún cliente real se quede sin poder reservar.
> Fecha: 2026-10-27. Rama base: `feat/marca-sun-baja`. Alcance fuera: precios, cupo, Stripe, modelos de reserva (ver Non-goals).

```
SIGNALS
  input      texto que el cliente teclea, pega o autocompleta: cadena arbitraria, se trata como hostil | revalida el backend
  boundary   navegador -> API -> WhatsApp Business (Meta) y correos; el formato que sale a Meta cambia (de "612 123 4567" a "+526121234567")
  data       PII (teléfono) en Reserva/Orden.telefono_cliente, sin cambio de retención ni de lectores; borrador en sessionStorage de la pestaña
  money      none directo (precios, cupo y Stripe fuera de alcance). Un número equivocado cuesta un cliente sin confirmación en el muelle
  control    validación por país; inverso: bloquear a un cliente real con un número válido = venta perdida. Por eso se valida SOLO largo
  execution  none (todo síncrono; la biblioteca se importa estática, no hay ventana "aún no cargó")
SIZE  Medium: ~14 archivos de frontend, 4 de backend, 1 dependencia y 267 assets, sin migración
GATE  gate:arch con 6 decisiones del dueño (abajo). Lo forzó `boundary` (Meta) y `control` (validación); verificación manual de WhatsApp y autofill antes de subir
```

## 1. Contexto y hechos verificados

"Extensión" en la petición = código de país (lada internacional), no extensión de PBX. Hoy el campo es un `<Input type="tel">` libre. Verificado en el código:

- Backend: `validar_telefono` exige 10 a 15 dígitos (`bookings/validators.py`); `telefono_marcable` (`bookings/admin.py:93`) antepone 52 si hay exactamente 10 dígitos; WhatsApp recibe `'to': reserva.telefono_cliente` crudo (`notifications/services.py:385,946`); el tope de apartados compara igualdad exacta (`payments/views.py:241`); `Orden` y `Reserva` (`models.py:536,1695`) usan el mismo validador con `max_length=20`; el flujo de órdenes (`views.py:1087`) hace `full_clean()`.
- Frontend: la validación existe en tres versiones distintas: `checkout-view.tsx:83` (10 a 15), `traslado-view.tsx:72` (**8** a 15, así que 8 o 9 dígitos pasan en el navegador y el backend responde 400) y `validacion-paquete.ts:16`.
- Medido con libphonenumber-js 1.13.15 (`/min`): `+376 312 345` (Andorra, 9 dígitos), `+299 321000`, `+500 51234` son válidos; `+47 41234567`, `+45…`, `+65…` suman exactamente 10 dígitos. Con el código incluido, el backend actual **rechaza** los de menos de 10 y `telefono_marcable` **marca mal** los de 10 (les pone 52 delante).
- La idea "todos escogen código, México por defecto, sin tocar backend" se acepta en lo esencial, pero no alcanza sola: sin los 3 cambios de backend de §5 fallan los países de arriba.

## 2. Decisiones y alternativas descartadas

| # | Decisión | Descartado y motivo |
|---|---|---|
| D1 | Se guarda `+<código><número>` compacto (`+526121234567`) en el campo existente. Sin migración ni campo nuevo. 16 caracteres máx (E.164 = 15 dígitos + `+`), cabe en `max_length=20`. Los viejos no se tocan | Campo nuevo `telefono_pais` + migración: toca 2 modelos, serializers, RLS, admin y no aporta (el código ya va en el número). Normalizar viejos con migración de datos: riesgo sin beneficio |
| D2 | `libphonenumber-js` **1.13.15** exacta, build `/min` (publicada 2026-10-08, 19 días; MIT; releases cada ~2 semanas, mantenida). Validación = `isPossible()` (largo por país). En `/min`, `isValid()` se comporta igual | `/max` (+65 KB): su `isValid` envejece y rechaza rangos recién asignados, el propio README prefiere `isPossible`. `react-phone-number-input`: trae su UI con `<select>`/`<img>` crudos y banderas desde CDN (CSP `img-src 'self'` las bloquea, la guardia las cuenta). `intl-tel-input`: CSS+sprite propios, mismo choque. `google-libphonenumber` ~550 KB. Tabla propia de códigos sin biblioteca: no valida largo, justo lo que el dueño no quiere que falle |
| D3 | Importación **estática** de la biblioteca (+84 KB crudo / 19.9 KB gzip de metadata medido; con el código estimo ~30 KB gzip, **medir** en `next build`, tope aceptado 40 KB gzip en `/reservar` y `/traslados`; no afecta hub ni sedes) | Carga bajo demanda: abre una ventana en que la validación aún no existe; el costo de ese fallo es mayor que 30 KB en una ruta que ya carga Stripe |
| D4 | Banderas = 267 SVG 3x2 de `country-flag-icons` **1.6.20** (MIT, 2026-07-01), 178 KB en total (0.6 a 3.4 KB c/u), copiados por script a `frontend/public/flags/<ISO>.svg` y commiteados; se pintan con `next/image` `unoptimized` dentro de `ui/bandera.tsx` (no `<img>`, que la guardia cuenta con umbral 0 incluso en `ui/`). El paquete queda como devDependency usada solo por `npm run banderas` | Emoji de bandera: no se ven en Windows. CDN: CSP. Sprite único: baja 180 KB aunque solo se vea una. Componentes React por país: entran al JS. Ningún cambio de CSP necesario (`/flags/` es `'self'`) |
| D5 | País por defecto **México** en es y en (pedido del dueño). El país del selector es presentación: lo que vale es el código (ver caso +1/+7/+44) | Detectar por idioma/IP/`navigator`: una suposición equivocada produce un número válido pero ajeno, en silencio. Ver riesgo R1 y decisión 5 |
| D6 | Selector propio: botón con bandera+código que abre lista con buscador sobre `FieldPopover` (escritorio) o `Sheet` (móvil, < 640 px, como el resto del asistente). Diseño visual: design-advisor | `<select>` nativo: sin banderas y la guardia lo prohíbe; 245 opciones sin búsqueda |
| D7 | Backend retrocompatible (§5): solo **acepta más**, nunca menos | Normalizar en el servidor al guardar: cambia lo que ve la vendedora en altas manuales y no es necesario |

Triage de las dos elecciones discutibles (3 rondas resumidas): (a) validar con `isValid` max vs `isPossible` min: la premisa "necesitamos rechazar prefijos inexistentes" no es real (el costo de un falso positivo es una llamada de la vendedora; el de un falso negativo es una venta perdida) -> `isPossible`. (b) `autocomplete`: ver caso 12.

## 3. Contrato de datos de punta a punta

| Etapa | Valor |
|---|---|
| Estado `contacto.phone` (3 vistas, `pedido-estado.ts`, borrador) | **string compacto**: `''` si no hay dígitos (el país solo no cuenta como valor, así `missingFields` sigue funcionando), si no `+<código><dígitos escritos>`. Se guarda lo tecleado (con `0` inicial incluido) para no mover el cursor |
| Al salir del campo (blur) y al enviar | `aE164()` canoniza con la biblioteca (`07911 123456` en +44 -> `+447911123456`; `+52 1 612…` -> `+526121234567`) |
| Payload (`pedido-payload.ts:90,119`, `checkout-view.tsx:1073`, `traslado-view.tsx:573`) | `telefonoParaEnviar(phone)`: E.164 si parsea; si no, el texto recortado tal cual (el backend decide; nunca se vacía ni se inventa) |
| Backend | guarda lo recibido; `validar_telefono` y `telefono_marcable` entienden el `+` |
| Lectura (resumen del pedido, "Continuar reservación", `estado.telefono_cliente`) | `restaurarTelefono(valor)`: compacto si se puede; si no, se muestra en el campo con México y el error de siempre. **Jamás se borra** lo que había |
| Mostrar al cliente | `formatearTelefono()` = `+52 612 123 4567` y nombre del país, en el renglón "Tus datos" y en el resumen (`resumen-paquete.ts:58`) |

## 4. Frontend por archivo

| Archivo | Cambio |
|---|---|
| `package.json` | `"libphonenumber-js": "1.13.15"` (dependencies, exacta); `"country-flag-icons": "1.6.20"` (devDependencies); script `"banderas": "node scripts/copiar-banderas.cjs"` |
| `tests/run-hub-tests.cjs` | agregar `telefono` y `paises-telefono` a `suites` y `NODE_PATH: path.join(root,'node_modules')` al `env`: el JS compilado vive en un directorio temporal sin `node_modules`, así que `require('libphonenumber-js/min')` no resolvería. Es una línea y mantiene el módulo puro probado igual que los demás. Verificar en la primera tarea que TS (Node10) resuelve `libphonenumber-js/min` por `min/package.json` |
| `src/lib/telefono.ts` (nuevo, puro) | `PAIS_POR_DEFECTO='MX'`; `dividir(valor)->{codigo,nacional}`; `compactar(codigo,texto)`; `evaluar(valor)->'vacio'\|'ok'\|'incompleto'\|'codigo-desconocido'`; `aE164`; `telefonoParaEnviar`; `restaurarTelefono`; `formatearTelefono`; `resolverCodigo(texto)` (los códigos son libres de prefijo, así que `+52` se resuelve en cuanto está completo). Toda llamada a la biblioteca va en `try/catch`: si lanza, degrada a "ok si 7 a 15 dígitos" (un fallo de la biblioteca nunca bloquea una venta). Reglas México (la biblioteca no las cubre, verificado): con `+52`, nacional de 11 dígitos que empieza en `1` -> quitar el `1`; nacional que empieza en `01`, `044` o `045` y deja 10 dígitos -> quitarlo |
| `src/lib/paises-telefono.ts` (nuevo, puro) | lista (`getCountries()` = 245 + `getCountryCallingCode`), nombre por `Intl.DisplayNames(lang,{type:'region'})` con respaldo al ISO, orden con `Intl.Collator(lang)`, fijos arriba (MX, US, CA), búsqueda sin acentos por nombre, ISO o código (`+34`, `34`) |
| `src/components/ui/bandera.tsx` (nuevo) | `Bandera({iso})` con `next/image unoptimized`, `alt=""` (decorativa), tamaño fijo 24x16 (sin salto de layout); sin archivo -> icono Phosphor `Globe` |
| `scripts/copiar-banderas.cjs` (nuevo) | copia a `public/flags/` solo los ISO de `getCountries()` que existan; imprime los que faltan (esperables: `AC`, `TA`, `XK`, según versión) |
| `src/components/checkout/telefono-campo.tsx` (nuevo) | el control: selector + `Input`. Props como el resto de campos (`valor`, `onCambio`, `error`, `refInput`, `idError`, `lang`, textos). Estado local solo para el país (desempate +1/+7/+44) y el texto mostrado; se resincroniza si el `valor` externo cambia (restauración tardía) |
| `src/components/checkout/campos-contacto.tsx` | la rama `phone` usa `TelefonoCampo`. **Trampa**: el `<label>` actual envuelve el control; con un botón dentro, tocar la etiqueta abriría el selector (el botón es el primer elemento etiquetable). El teléfono lleva `<div role="group">` + `<label htmlFor>` apuntando al input. `refs.phone` apunta al input numérico (foco y scroll al error ya dependen de eso) |
| `checkout-view.tsx` (83, 919, 849, 1073, 1306), `traslado-view.tsx` (72, 428, 301, 573, 747), `validacion-paquete.ts:16`, `pedido-payload.ts` (90, 119), `resumen-paquete.ts:58`, `campo-paso.ts` | borrar las tres `telefonoValido`; un solo `evaluar()`; payload con `telefonoParaEnviar`; restauración con `restaurarTelefono`; resúmenes con `formatearTelefono` |
| `dictionaries/{es,en}.json` | claves nuevas (§7). Reiniciar `next dev` tras editarlas. Sin raya larga (la guardia `guion-largo` la cuenta) |

Comportamiento del control (no negociable, el visual lo define el design-advisor):
- Teclear: solo dígitos y `+ ( ) - . espacio`; letras se descartan; máximo 15 dígitos entre código y número. **Sin formateo en vivo** (es la causa clásica de saltos de cursor); se formatea al salir del campo.
- Si el texto empieza con `+` o `00` (tecleado, pegado o autocompletado), se separa el código con `resolverCodigo`, el selector se mueve solo y el resto queda como número.
- Cambiar de país con número escrito: se conserva el número y cambia el código; no se trunca ni se borra.
- Validación al salir del campo y al "Continuar" (nunca mientras se teclea). Un solo mensaje claro; el error usa `ErrorDeCampo` ya existente (`aria-describedby`, foco y scroll).
- Teclado: Enter/Espacio abre; flechas, escribir para buscar, Enter elige, `Esc` cierra y devuelve el foco al botón. Etiqueta accesible del botón: "País y código del teléfono: México +52". Opciones: nombre + código. Banderas decorativas.
- `type="tel"`, `inputMode="tel"`, `enterKeyHint="next"`, `autocomplete="tel"`, `dir="ltr"`.

## 5. Backend por archivo (retrocompatible, sin migración)

| Archivo | Cambio | Por qué no rompe datos viejos |
|---|---|---|
| `bookings/validators.py` `validar_telefono` | Si el texto empieza con `+` y tiene de **7 a 9** dígitos, se acepta, salvo que el número empiece con `1` o `52` (NANP y México siempre son más largos, así `+52 612 123` de 8 dígitos se sigue rechazando; los de 10 o más dígitos pasaban y siguen pasando). Todo lo que antes pasaba o fallaba sigue igual; solo se **agregan** aceptados. Mantener el máximo 15 | Una reserva vieja se edita sin cambio de resultado |
| `bookings/telefono.py` (nuevo, sin imports de modelos) | Mover aquí `LADA_PAIS` y `telefono_marcable`; `admin.py` los reexporta (`from .telefono import …`) para no romper `vistas_enlace_pago.py` ni pruebas. Regla nueva: si el texto empieza con `+`, devolver los dígitos tal cual (7 a 15), **sin** anteponer 52. Sin `+`: comportamiento actual intacto (10 dígitos -> 52, 11 o más tal cual, menos de 10 -> `''`) | `+47 41234567` (10 dígitos) ya no se marca como mexicano. Un viejo `+6121234567` (más con `+` que sin él) sería la única regresión imaginable; improbable, se acepta |
| `notifications/services.py:385,946` | `'to': telefono_marcable(reserva.telefono_cliente) or reserva.telefono_cliente` | Los viejos de 10 dígitos ahora salen con 52 (hoy Meta los recibe sin código); los nuevos salen sin `+`. Meta normaliza detalles locales (p. ej. el 9 de Argentina o el 1 antiguo de México), eso no lo controlamos |
| `payments/views.py:241` (tope de apartados) | **Sin cambio.** Comparación exacta; con el formato compacto coincide más que antes (ya no depende de espacios). Los viejos con formato distinto no cuentan juntos: es un freno anti-acaparamiento, no una garantía | n/a |
| `search_fields` del admin | **Sin cambio** en v1. Buscar `6121234567` encuentra `+526121234567` (subcadena); buscar con espacios solo encuentra viejos. Opcional posterior: normalizar el término en `get_search_results` | n/a |
| Alta manual (`forms_alta_reserva.py`, `vistas_enlace_pago.py`) | Sin cambio: texto libre, acepta `612 123 4567` y `+código` | n/a |
| Correos y WhatsApp plantilla | Muestran el número tal cual se guardó (`+526121234567`); aceptable en v1 | n/a |

Orden de despliegue: **backend primero** (Render), después frontend (`vercel --prod` desde `qa/frontend`). Con el frontend nuevo y un backend viejo, solo fallan los números con menos de 10 dígitos totales.

## 6. Casos borde y su manejo

(V) = comportamiento medido con la biblioteca 1.13.15 al diseñar.

| # | Caso | Manejo |
|---|---|---|
| 1 | México normal `612 123 4567` o `(612) 123-4567` | `+526121234567` (V) |
| 2 | Pega `+52 1 612 123 4567` (prefijo móvil viejo) | La biblioteca lo da por imposible (V). Regla México de §4 quita el `1`. Sin esto, un cliente real queda bloqueado |
| 3 | `01 612…`, `044…`, `045…` con México | La biblioteca falla (V). Se quitan en la misma regla |
| 4 | `0052…` o `+` pegado con otro país elegido | `00` equivale a `+` (V para MX). Cambia el selector. `011` (marcado de EE.UU.) no se soporta: da el error normal y el selector resuelve |
| 5 | Código compartido +1 (25 países), +7 (RU, KZ), +44 (GB, GG, IM, JE) (V) | Se guarda el código, que es idéntico. El selector **nunca** se re-deriva del resultado de la biblioteca si el código ya coincide (`07911 123456` con GB devuelve GG, V). Al restaurar, +1 -> US, +7 -> RU, +44 -> GB |
| 6 | Número corto fuera de México: AD, GL, FK; 10 dígitos totales: NO, DK, SG (V) | Frontend `ok`. Backend: regla `+` de 7 a 9 dígitos; `telefono_marcable` por `+` |
| 7 | Cero nacional inicial (GB, IT, etc.) | Se guarda como se tecleó; `aE164` lo canoniza al blur y al enviar (V `+447911123456`) |
| 8 | Extensión (`ext. 12`, `x12`) | La biblioteca la separa (V). Se **descarta** (viajeros; WhatsApp no marca extensiones) |
| 9 | Casi válido (9 dígitos MX, `+1 212555`, 11 dígitos sin 1) | `incompleto` (V). Mensaje al blur y al continuar, nunca al teclear; no se borra nada |
| 10 | Dígitos no ASCII (árabes), letras, símbolos, > 15 dígitos | La biblioteca convierte dígitos (V); la entrada los pasa a ASCII, descarta letras y topa en 15 |
| 11 | Código desconocido (`+999`) | `codigo-desconocido`: mensaje `phoneUnknownCode`; el texto se conserva |
| 12 | Autocompletado | `autocomplete="tel"` (número completo): el cliente lo entrega con `+` si el perfil lo tiene; si lo entrega nacional, se interpreta con el país elegido. `tel-national` descartado: siempre nacional del país **del perfil**, no del selector, y entraría válido pero equivocado. **No verificado en navegadores reales**: va a la lista manual §9. Mitigación estructural: el resumen siempre muestra el número formateado con país |
| 13 | Teclado móvil | `type=tel` + `inputMode=tel`; el `+` está en el teclado numérico de iOS/Android (pulsación larga de 0 / símbolos) y el código ya viene puesto, así que normalmente no hace falta |
| 14 | Cambiar país con número escrito | Conserva dígitos, cambia código; si queda imposible, error al validar (ver 9) |
| 15 | Borrador viejo en `sessionStorage` (`612 123 4567`) | `restaurarTelefono` -> `+526121234567`. Si no parsea, queda visible en el campo con México; nunca se vacía |
| 16 | Reanudar desde el servidor con formato viejo (`+52 1 612…`, `(612) 123-4567`) | Igual que 15 (`checkout-view.tsx:849`, `traslado-view.tsx:301`) |
| 17 | Reservas existentes sin código | No se migran. `telefono_marcable` sigue completando con 52 los de 10 dígitos. WhatsApp ya recibe 52 (§5) |
| 18 | Lector de pantalla y teclado | `role="group"` con etiqueta, botón con nombre de país y código, opciones con texto, banderas con `alt=""`, error por `aria-describedby`, foco devuelto al cerrar |
| 19 | es / en | Nombres con `Intl.DisplayNames(lang)`; búsqueda sin acentos; sin `Intl.DisplayNames` -> se muestra el ISO y la lista sigue operable. RTL no aplica |
| 20 | Biblioteca lanza o falla | `try/catch`: degrada a "ok si 7 a 15 dígitos"; backend es la red de seguridad |
| 21 | Bandera inexistente (`XK`, `AC`, `TA`) | Icono `Globe`; el código y el nombre siguen |
| 22 | Doble clic / reintento de pago | Sin efecto: el teléfono se canoniza antes de crear la reserva y el `checkout_id` ya es idempotente |
| 23 | Alta manual de la vendedora | Intacta: `612 123 4567` y `+código` |

## 7. Textos (es / en)

| Clave | es | en |
|---|---|---|
| `checkout.invalidPhone` (reescrita; ya no habla de 10 dígitos ni de México) | Revisa el teléfono: no parece un número completo del país elegido. | Check the phone number: it does not look complete for the selected country. |
| `checkout.phoneUnknownCode` | No reconocemos ese código de país. Elígelo de la lista. | We do not recognize that country code. Pick it from the list. |
| `checkout.phoneCountry` | País y código del teléfono | Country and phone code |
| `checkout.phoneCountrySearch` | Buscar país o código | Search country or code |
| `checkout.phoneCountryNone` | Sin resultados | No results |
| `checkout.phoneCountryFrequent` / `phoneCountryAll` | Frecuentes / Todos los países | Frequent / All countries |

`checkout.examples.phone` ("Ej. 612 123 4567") se muestra solo con México elegido; con otro país va vacío.

## 8. Riesgos y rollback

| Id | Riesgo | Mitigación |
|---|---|---|
| R1 | **Residual principal**: turista (sobre todo en `/en`) que ignora el selector y teclea su número de 10 dígitos de EE.UU.; con México elegido es "válido" (`+522125551234`) y la confirmación va a otro lado. `/min` no distingue prefijos | Selector con bandera y nombre visibles, número formateado con país en el renglón "Tus datos" y en el resumen del pedido. Decisión 5 del dueño: default US en `/en` |
| R2 | Meta rechaza algún `to` | Prueba real manual (§9). El fallo no tumba el cobro (ya se atrapa) |
| R3 | Autofill pone un número ajeno | Resumen visible; revisión manual |
| R4 | Peso en `/reservar` | Medir en `next build`; tope 40 KB gzip. Rollback: dinámico solo si se rebasa |
| R5 | 267 SVG en el repo | 178 KB; script reproducible; fijar versión |
| R6 | Dependencia nueva | Versiones exactas, MIT, `npm audit` en la tarea 1 |

Rollback: revertir el frontend es seguro (el backend nuevo acepta lo viejo y lo nuevo). Revertir solo el backend con el frontend nuevo rechaza únicamente números `+` con menos de 10 dígitos. Sin migración ni datos que deshacer.

## 9. Plan de pruebas

- `tests/telefono.test.cjs`: todos los (V) de §6 más: vacío, solo código, `+` suelto, 11 dígitos MX sin 1, restauración de `612 123 4567` / `+52 1 612 123 4567` / `(612) 123-4567` / basura, `telefonoParaEnviar` (válido, inválido), biblioteca que lanza (simulada), tope de 15 dígitos, ≤ 16 caracteres siempre. `tests/paises-telefono.test.cjs`: 245 países con código, orden es/en, búsqueda `mex`, `+34`, `34`, `alemania`/`germany`, fijos arriba, sin duplicados.
- Backend (`manage.py test apps.bookings apps.notifications apps.payments`, SQLite basta, sin cambios de BD): `validar_telefono` acepta `+376 312 345`, `+299 321000`, `+47 41234567`; rechaza `+52 612 123`, `+1 212`, `123`, `asdf`; sigue aceptando `612 123 4567`, `+52 1 612 123 4567`. `telefono_marcable`: `+47 41234567` -> `4741234567`, `612 123 4567` -> `526121234567`, `612` -> `''`. WhatsApp `to` con viejo y nuevo. POST a `ordenes/` y `reservas/` con `+376 312 345`. Ubicar pruebas existentes con `grep validar_telefono`.
- `npm run verificar` verde (tsc, eslint, test, guardia, knip, build). Sin `<img>` ni colores literales; formas rectángulo o círculo; objetivo táctil de 44 px.
- A mano (el dueño, en teléfono real, sin navegador automatizado): (1) servicio suelto, paquete 1 empresa, cruza-empresa y traslados con México, EE.UU. y Noruega; (2) pegar `+52 1 …` y `+1 …` estando en México; (3) autofill de Chrome Android y Safari iOS con perfil de otro país; (4) recargar a medio llenado y "Continuar reservación" con un borrador viejo; (5) WhatsApp real de confirmación a un `+52` y a un `+1`; (6) lector de pantalla (TalkBack o VoiceOver) en el selector.

## 10. Tareas candidatas para el pm

| # | Tarea | Depende | Archivos que posee |
|---|---|---|---|
| T1 | Dependencias exactas, `NODE_PATH` en el runner, `lib/telefono.ts` y su prueba (TDD) | - | `package.json`, `tests/run-hub-tests.cjs`, `lib/telefono.ts`, `tests/telefono.test.cjs` |
| T2 | `lib/paises-telefono.ts` y su prueba | T1 | los dos archivos |
| T3 | Banderas: script, `public/flags/`, `ui/bandera.tsx`, knip y guardia | T1 | `scripts/copiar-banderas.cjs`, `public/flags/**`, `ui/bandera.tsx` |
| T4 | `TelefonoCampo` + cambio en `CamposContacto` (sin el visual final: lo define el design-advisor primero) | T2, T3, diseño | `checkout/telefono-campo.tsx`, `campos-contacto.tsx` |
| T5 | Cablear los 3 checkouts: validar, enviar, restaurar, resumen | T4 | `checkout-view`, `traslado-view`, `validacion-paquete`, `pedido-payload`, `resumen-paquete`, `campo-paso` |
| T6 | Diccionarios es/en | T4 | `dictionaries/*.json` |
| T7 | Backend: validador, `telefono.py`, `to` de WhatsApp, pruebas. **Se despliega primero** | - (paralela a T1 a T6) | `bookings/validators.py`, `bookings/telefono.py`, `bookings/admin.py` (solo reexport), `notifications/services.py`, pruebas |
| T8 | `npm run verificar`, medición de peso y lista manual §9 | T5, T6, T7 | - |

Exclusividad de archivos: T4 y T5 no comparten archivos; T7 no toca frontend.

## Non-goals

No se tocan precios, cupo, estados, Stripe, modelos ni migraciones. No se migran teléfonos guardados. No se detecta el país por IP o idioma. No se valida que el prefijo exista (solo el largo). No se piden extensiones de PBX. No se formatea el teléfono en correos ni plantillas. No se cambia la búsqueda del admin ni el tope de apartados.

## Decisiones que el dueño debe aprobar

1. Guardar `+<código><número>` compacto en el campo actual, sin migración y sin tocar los números ya guardados.
2. `libphonenumber-js` 1.13.15 (`/min`), validando solo el largo por país, importada estática (~+30 KB gzip en los checkouts).
3. Tocar el backend con 3 cambios que solo aceptan más (validador, marcado de enlaces, `to` de WhatsApp) y desplegarlo antes que el frontend; "no tocar backend" haría fallar Andorra, Noruega, Dinamarca, Singapur y similares.
4. Banderas SVG propias (267 archivos, 178 KB, MIT) en `public/flags/`, sin CDN y sin cambiar la CSP.
5. País por defecto: México en español e inglés (tu pedido), o EE.UU. en `/en`; el riesgo residual es el turista que ignora el selector y se mitiga con el número formateado y el país visibles en el resumen.
6. Pruebas manuales tuyas antes de subir: WhatsApp real a `+52` y `+1`, autofill de Chrome/Safari y un borrador viejo.

ARCHITECT: READY FOR GATE:ARCH
