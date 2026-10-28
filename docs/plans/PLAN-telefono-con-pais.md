# PLAN: teléfono con selector de país (los tres checkouts)

Fecha: 2026-10-27 | ARCH: `docs/architecture/ARCH-telefono-con-pais.md` (gate:arch aprobado, 6 decisiones) | Diseño: `docs/design/DESIGN-telefono-con-pais.md` (en escritura por design-advisor) | Owner: pm
Modo: full (Medium, archetype `commerce`, gates `strict`). Rama `feat/marca-sun-baja`, worktree `qa`. **Sin commit ni push hasta que el dueño lo pida**: cada tarea termina en su verificación.

## Resumen

| Dato | Valor |
|---|---|
| Tareas | 10 (T1-T4, T5a/b/c, T6, T7, T8) + 2 pasadas de revisión |
| Pools | 2 senior-dev concurrentes como máximo (A = frontend, B = backend y apoyo) + qa-engineer + code-reviewer + security-officer |
| Ruta crítica (con +40%) | T1 84 + T2 56 + T4 126 + T5a 63 + T5b 56 + T8 63 + revisión final 35 = **483 min = 8,05 h** de reloj de agente |
| Sin buffer / con buffer | 5,75 h (345 min) a 8,05 h. Agente-tiempo total (suma): 826 min = 13,8 h |
| Espera humana (async, no gasta tokens) | gate:plan, gate:design, gate:code-backend, gate:code, pruebas del dueño, gate:ship: ~0,5 a 2 h cada uno |
| Peso en `/reservar` y `/traslados` | tope 40 KB gzip, se mide en T8 |

Los `gate:*` de abajo no están en Beads (`bd` no instalado): se llevan en este documento y en la conversación.

## Tareas

Las estimaciones son base / con buffer 40% (min). «Archivos» = exclusivos; los demás son solo lectura.

| ID | Objetivo | Archivos exclusivos | Depende | Est | Hecho cuando (verificable) | Verificación | Riesgo |
|---|---|---|---|---|---|---|---|
| T1 | Dependencias exactas, `NODE_PATH` en el runner y `lib/telefono.ts` (puro) con TDD | `frontend/package.json` (+lock), `tests/run-hub-tests.cjs`, `src/lib/telefono.ts`, `tests/telefono.test.cjs` | gate:plan | 60/84 | Cubre todos los (V) de ARCH §6 y §9 (vacío, `+52 1`, `01/044/045`, GB/GG, biblioteca que lanza simulada, 15 dígitos, ≤16 caracteres); `libphonenumber-js` 1.13.15 en `dependencies`, `country-flag-icons` 1.6.20 en `devDependencies`, script `banderas`; TS resuelve `libphonenumber-js/min`; `npm audit` sin altos nuevos | `cd frontend && node tests/run-hub-tests.cjs` y `npx tsc --noEmit` | Resolución de `/min` en TS Node10; mover la regla México mal |
| T2 | `lib/paises-telefono.ts` (puro): 245 países, orden es/en, búsqueda sin acentos, fijos MX/US/CA | `src/lib/paises-telefono.ts`, `tests/paises-telefono.test.cjs`, una línea en `tests/run-hub-tests.cjs` (serial tras T1, mismo pool) | T1 | 40/56 | 245 países con código, sin duplicados, `mex`, `+34`, `34`, `alemania`/`germany` encuentran lo esperado; sin `Intl.DisplayNames` degrada a ISO | `node tests/run-hub-tests.cjs` | `Intl.DisplayNames` distinto entre Node y navegador |
| T3 | Banderas: script de copia, `public/flags/*.svg`, `ui/bandera.tsx` | `frontend/scripts/copiar-banderas.cjs`, `frontend/public/flags/**`, `src/components/ui/bandera.tsx`, config de knip/guardia solo si lo exigen | T1 | 40/56 | `npm run banderas` copia los ISO existentes e imprime los faltantes; sin `<img>` ni colores literales; `Globe` si falta archivo; ningún SVG con `<script>`/`onload` | `npm run banderas` y `grep -L "<svg" public/flags/*.svg` vacío; `npx tsc --noEmit` | SVG de terceros (ver security); knip marca el paquete |
| T4 | `TelefonoCampo` (selector + input) y rama `phone` de `CamposContacto` con `label htmlFor` + `role=group` | `src/components/checkout/telefono-campo.tsx`, `src/components/checkout/campos-contacto.tsx` | T2, T3, **gate:design**; T6 debe aterrizar antes de su `tsc` final | 90/126 | Cumple el comportamiento de ARCH §4 (solo dígitos y `+ ( ) - . espacio`, tope 15, sin formato en vivo, cambia de país conservando el número, `00`/`+` mueve el selector, teclado y ARIA, 44 px táctil); coincide con DESIGN | `npx tsc --noEmit && npx eslint src/components/checkout` y prueba de componente si el repo la tiene | Salto de cursor; tocar la etiqueta abre el selector; diseño aún sin aprobar |
| T5a | Cablear **servicio suelto** (`checkout-view`) con `evaluar`, `telefonoParaEnviar`, `restaurarTelefono`, `formatearTelefono`; borrar su `telefonoValido` | `src/components/checkout-view.tsx` | T4, T6 | 45/63 | Sin `telefonoValido` local; payload E.164; borrador y reanudación (ARCH §6 casos 15-16) restauran sin borrar; renglón «Tus datos» formateado | `npx tsc --noEmit && npx eslint src/components/checkout-view.tsx` | Borrar un teléfono viejo al restaurar |
| T5b | Cablear **traslados** (`traslado-view`); desaparece el 8-15 divergente | `src/components/traslado-view.tsx` | T4, T6 (tras T5a: mismo pool B) | 40/56 | Igual que T5a para traslados; 8 o 9 dígitos sin `+` ya no pasan en el navegador | `npx tsc --noEmit && npx eslint src/components/traslado-view.tsx` | Rutas de reanudación distintas a T5a |
| T5c | Cablear **paquete 1 empresa y cruza-empresa** (`pedido-paquete`) y libs compartidas | `src/lib/pedido-payload.ts`, `src/lib/pedido-estado.ts`, `src/components/pedido/validacion-paquete.ts`, `src/components/pedido/resumen-paquete.ts`, `src/components/pedido/pedido-paquete.tsx`, `src/lib/campo-paso.ts` (solo si hace falta), `src/components/pedido/grupo-datos.tsx` (solo si hace falta) | T4, T6 | 50/70 | `erroresDeContacto` usa `evaluar`; `armarPayloadOrden/Reserva` usan `telefonoParaEnviar`; `armarResumenPaquete` usa `formatearTelefono`; pruebas existentes de resumen/payload siguen verdes | `node tests/run-hub-tests.cjs && npx tsc --noEmit` | Pruebas de payload existentes asumen el formato viejo |
| T6 | Diccionarios es/en (claves de ARCH §7, `invalidPhone` reescrita) | `src/dictionaries/es.json`, `src/dictionaries/en.json` | T1 (las claves ya están en ARCH §7) | 25/35 | 8 claves en ambos idiomas, mismo conjunto de claves, sin raya larga; `next dev` reiniciado | `npx tsc --noEmit` y `npm run guardia` | Raya larga cuenta en la guardia; servidor dev con caché vieja |
| T7 | **Backend** (solo acepta más): `validar_telefono` (+ de 7 a 9 dígitos, salvo `1` y `52`), nuevo `bookings/telefono.py` con `telefono_marcable`, `to` de WhatsApp | `backend/apps/bookings/validators.py`, `backend/apps/bookings/telefono.py`, `backend/apps/bookings/admin.py` (**solo** el reexport; ver nota), `backend/apps/notifications/services.py` (:385, :946), sus pruebas (`grep validar_telefono`, `tests` de notifications) | - (arranca en cuanto pasa gate:plan) | 60/84 | Pruebas de ARCH §9 verdes: acepta `+376 312 345`, `+299 321000`, `+47 41234567`, `612 123 4567`, `+52 1 612 123 4567`; rechaza `+52 612 123`, `+1 212`, `123`, `asdf`; `+47 41234567` -> `4741234567`, `612` -> `''`; `to` con viejo y nuevo; POST a `ordenes/` y `reservas/` con `+376 312 345` | `cd backend && STRIPE_SECRET_KEY= STRIPE_WEBHOOK_SECRET= STRIPE_PUBLISHABLE_KEY= venv/Scripts/python.exe manage.py test apps.bookings apps.notifications apps.payments` | Chocar con los cambios `rk_` sin commit de `bookings/admin.py` |
| T8 | Verificación integral, medición de peso, preparar lista manual | - (solo lectura; sí puede arreglar fallos pequeños de integración con aviso al pool dueño) | T5a, T5b, T5c, T6, T7 | 45/63 | `npm run verificar` verde (tsc, eslint, test, guardia, knip, build); peso gzip de `/reservar` y `/traslados` medido y ≤ 40 KB sobre la línea base; suite backend verde en SQLite | `cd frontend && npm run verificar` y el comando de T7 | Peso por encima del tope -> carga dinámica solo si se rebasa |

**Nota T7 / `bookings/admin.py`**: el archivo ya tiene cambios locales sin commit de las llaves `rk_` (también `tenancy/models.py`, `payments/checks.py` y sus pruebas). T7 edita únicamente el import/reexport con `Edit` mínimo; nunca `git checkout`/`restore` ni reescritura. Al hacer commit, separar con `git add -p` o dos commits: el del dueño (`rk_`) y el de T7. Hoy `telefono_marcable` está en `admin.py:93`.

**Nota de pruebas en paralelo**: dos senior-dev editan el mismo worktree sin commit. `tsc` mira todo el proyecto: un error en un archivo ajeno a la tarea no es tuyo; se corre `verificar` completo solo en T8.

**IMPL-BRIEFs por tarea**: no emitidos (alcance de este pm acotado a este documento); las columnas «Archivos» y la Nota T7 hacen de lista permitida, y todo lo no listado es denylist. El senior-dev no toca precios, cupo, Stripe, modelos ni migraciones (Non-goals del ARCH).

## Dependencias y paralelismo

```
gate:plan
 ├─ Pool A: T1 ─┬─ T2 ──────────┐
 │               └─ T3 (Pool B) ┤
 │  Pool B: T7 ──> [gate:code-backend] ──> DEPLOY BACKEND (Render)
 │                              T6 (Pool B, tras T3)
 │  gate:design (DESIGN aprobado por el dueño) ─┐
 └──────────────────────────────── T4 <─ T2,T3,gate:design  (T6 antes de su tsc)
        T4 ─┬─ T5c (Pool A)
            └─ T5a -> T5b (Pool B)
      T5a,T5b,T5c,T6,T7 -> T8 -> [code-reviewer ‖ qa-engineer ‖ security-officer] -> gate:code
      -> pruebas manuales del dueño (Vercel preview) -> gate:ship -> vercel --prod
```

Paralelismo máximo: 2 senior-dev. Disjuntos por construcción: T7 (backend) vs T1/T2/T3/T6 (frontend); T2 (lib) vs T3 (banderas); T5a/T5b/T5c no comparten archivo (verificado: `traslado-view` y `checkout-view` solo comparten `campo-paso`, que T5c posee condicionalmente; si T5a/T5b necesitaran cambiarlo, se serializa tras T5c). `run-hub-tests.cjs` lo tocan T1 y T2 en serie en el mismo pool. T6 y T4 nunca editan los diccionarios a la vez: si T4 necesita claves nuevas, las pide a T6 una vez cerrado.

## Gantt (reloj de agente, +40%; las esperas humanas no se dibujan)

```mermaid
gantt
    title PLAN telefono-con-pais (full, 2 pools)
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %H:%M
    section Gates
    gate:plan (aprobacion)         :crit, milestone, gp, 2026-10-27 09:00, 0m
    gate:design (dueño aprueba)    :crit, milestone, gd, after gp, 0m
    section Pool A (frontend)
    T1 telefono.ts + deps          :crit, t1, after gp, 84m
    T2 paises-telefono             :crit, t2, after t1, 56m
    T4 TelefonoCampo               :crit, t4, after t2 t3 gd, 126m
    T5c paquete + cruza-empresa    :t5c, after t4 t6, 70m
    section Pool B (backend y apoyo)
    T7 backend                     :t7, after gp, 84m
    Revision backend (cr + sec)    :rb, after t7, 21m
    gate:code-backend              :crit, milestone, gcb, after rb, 0m
    T3 banderas                    :t3, after t1 t7, 56m
    T6 diccionarios                :t6, after t3, 35m
    T5a checkout-view              :crit, t5a, after t4 t6, 63m
    T5b traslado-view              :crit, t5b, after t5a, 56m
    section Cierre
    T8 verificar y peso            :crit, t8, after t5b t5c, 63m
    Revision final (cr, qa, sec)   :crit, rf, after t8, 35m
    gate:code                      :crit, milestone, gc, after rf, 0m
```

ASCII (minutos desde gate:plan; `*` = ruta crítica):

```
min   0      84     140     175         301    364    420    483
A:    [T1*---][T2*--]            [T4*-------][T5c--]  (libre)
B:    [T7----][T3*-][T6]                   [T5a*][T5b*]
                            T4 arranca en min 140 si gate:design ya está dado
                                    T8* [63] -> revisión final [35]
Backend: T7 (0-84) -> revisión (84-105) -> gate:code-backend -> deploy (antes del frontend)
```

Ruta crítica: T1 84 -> T2 56 -> T4 126 -> T5a 63 -> T5b 56 -> T8 63 -> revisión final 35 = 483 min (8,05 h). Si gate:design se retrasa más de 140 min desde el arranque, T4 pasa a ser el cuello y la fecha se mueve minuto a minuto; T1-T3, T6 y T7 no esperan al diseño.

## Orden de despliegue y puertas

1. **gate:plan** (este documento). Dueño aprueba.
2. **gate:design**: el dueño aprueba `DESIGN-telefono-con-pais.md` antes de construir T4 (regla del repo). Si el diseño no existe al aprobar el plan, T4 queda «depende del diseño».
3. T7 termina y pasa **gate:code-backend** (strict, parte backend): code-reviewer revisa la compatibilidad (solo acepta más, mismo resultado para datos viejos, reexport sin ciclo de imports); security-officer revisa entrada hostil (largo, `+`, dígitos no ASCII) y que no se loguee PII; qa corre `apps.bookings apps.notifications apps.payments`. `pci-reviewer`: no aplica, no se toca cobro.
4. **Despliegue backend**: solo cuando el dueño pida commit y push. Commit de T7 separado del de las llaves `rk_`. `git push origin feat/marca-sun-baja:main` despliega Render; **ojo**: empuja *todos* los commits de la rama aún no en `main` (por ejemplo los del héroe en video), así que el dueño debe confirmar que quiere ese lote. Confirmar también que Vercel NO despliega solo desde `main` (según el registro, el frontend sale con `vercel --prod` manual).
5. T1-T6, T5a/b/c y T8 corren en local mientras tanto (el frontend nuevo contra backend viejo solo falla con `+` de menos de 10 dígitos).
6. **gate:code** (strict, `commerce`), tras T8 verde: code-reviewer = unicidad de `evaluar`, ausencia de `telefonoValido` duplicado, try/catch de la biblioteca, no borrar teléfonos al restaurar, a11y de `role=group`; qa-engineer = suite completa, casos §6 faltantes, peso medido; security-officer = ver abajo.
7. **Pruebas manuales del dueño** (lista abajo) sobre un deploy de **Vercel preview** (no producción) con el backend ya nuevo en Render; la de WhatsApp real exige backend desplegado.
8. **gate:ship**: el dueño da el visto bueno tras sus pruebas; entonces commit del frontend, `git push origin feat/marca-sun-baja:main` si falta y `vercel --prod` desde `qa/frontend`.

Revisión de seguridad (security-officer): 267 SVG de terceros servidos con `next/image unoptimized` (confirmar que no contienen `<script>`, `onload` ni referencias externas y que la CSP `img-src 'self'` no cambia), `npm audit` de ambas dependencias nuevas, versiones exactas y lockfile consistente, ningún dato personal en logs ni en la URL, validación del lado del servidor sigue siendo la autoridad (el frontend es solo ayuda), y que `telefonoParaEnviar` nunca envíe algo que el servidor no revalide.

## Pre-mortem

Titular: «El 3 de noviembre un turista de Texas reservó una pesca, tecleó su número de EE.UU. sin tocar el selector (México), la confirmación de WhatsApp fue a `+52` y la panga salió sin él.»

| Causa | L | S | Riesgo | Mitigación en el plan |
|---|---|---|---|---|
| Turista ignora el selector (R1) | 3 | 4 | 12 | Diseño: bandera y nombre visibles; T5a/b/c muestran el número formateado con país en «Tus datos» y el resumen; prueba manual 1 en `/en` |
| Backend viejo en producción con frontend nuevo | 2 | 4 | 8 | Orden de despliegue: backend antes; gate:code-backend; rollback documentado en ARCH §8 |
| Restaurar un borrador viejo lo borra o lo reescribe mal | 2 | 4 | 8 | T1 prueba de `restaurarTelefono` (basura, `(612) 123-4567`, `+52 1`); T5a/b/c lo verifican; prueba manual 4 |
| La biblioteca lanza o falla en un navegador raro | 1 | 5 | 5 | `try/catch` con degradación a «7 a 15 dígitos» (T1) |
| Choque de T7 con los cambios `rk_` sin commit | 3 | 3 | 9 | Edición mínima de `admin.py`, commits separados |
| Peso excede 40 KB gzip | 2 | 2 | 4 | T8 mide; carga dinámica solo si se rebasa |

Elefante: el diseño del selector aún no está aprobado y es la parte de más trabajo (T4 = 126 min); cualquier cambio de diseño tras construirlo repite T4 y T5. Aceptado sin mitigación: Meta puede rechazar un `to` con un formato local raro (R2); la prueba manual 5 lo detecta y el fallo de WhatsApp no tumba el cobro.

## Verificaciones manuales del dueño (teléfono real, sin navegador automatizado)

1. Servicio suelto, paquete de 1 empresa, cruza-empresa y traslados con México, EE.UU. y Noruega: reservar hasta el resumen y comprobar que el número sale formateado con país.
2. Pegar `+52 1 612 123 4567` y `+1 212 555 1234` estando en México: el selector debe moverse solo y no quedar bloqueado.
3. Autofill de Chrome Android y Safari iOS con un perfil de otro país: el número que entra debe ser el correcto.
4. Recargar a medio llenar y «Continuar reservación» con un borrador viejo (`612 123 4567`): no se pierde.
5. WhatsApp de confirmación real a un `+52` y a un `+1` (exige backend nuevo ya en Render).
6. Lector de pantalla (TalkBack o VoiceOver) en el selector, y navegación solo con teclado en escritorio.
7. En `/en` entrar con default México y confirmar que el aviso/resumen hace evidente el país elegido.

## Costos

**LLM**: $13 a $64 en toda la tubería (9 tareas senior-dev $9 a $54, revisiones y qa $2 a $4, architect $1 a $2, design-advisor $0,5 a $1, pm $0,3 a $0,6; Sonnet 4.6 y Haiku 4.5).
**Human equiv**: $6.900 a $11.100 (dev 20 a 32 h x $150, qa, security, architect, PM y diseño, +30% de coordinación). Relación media ~240x sobre el costo LLM de la tubería completa.
**Infra delta**: $0 al mes (sin migración; 178 KB de SVG en el repo).
**Time to ship**: ~8,05 h de reloj de agente en la ruta crítica (13,8 h de agente-tiempo sumado), más las esperas humanas de 5 puertas y las pruebas del dueño.

## Historial

- 2026-10-27 v1: plan inicial. Cambios respecto a ARCH §10: T5 se divide en T5a/T5b/T5c (los tres checkouts reales: `checkout-view`, `traslado-view`, `pedido-paquete`) para aislar archivos y permitir 2 pools; T6 depende solo de T1 y aterriza antes de T4; T3 y T6 pasan al pool B; se agregan gate:code-backend y gate:design.

**gate:plan: ESPERANDO APROBACIÓN DEL DUEÑO**

PM: READY FOR GATE:PLAN | 10 tareas (T1-T4, T5a/b/c, T6, T7, T8), 2 senior-dev concurrentes + qa-engineer, code-reviewer, security-officer | ruta crítica 483 min (~8,05 h de agente, 5,75 h sin buffer) | backend (T7) primero, frontend después, pruebas del dueño sobre Vercel preview
