# Reglas comunes (se anteponen a cada tarea)

Proyecto Django (backoffice con Unfold, 4 empresas con tenancy y RLS) + Next.js. Estás en el worktree `.claude/worktrees/apartado` (rama `feat/apartado-temporal`). Implementas UNA tarea de un plan mayor: el **apartado temporal de cupo** en el checkout web. La fuente de verdad del diseño es el spec `docs/superpowers/specs/2026-10-12-apartado-temporal-cupo-design.md` (LÉELO: cada tarea indica las secciones). Lee también `backend/CLAUDE.md`. Código y comentarios en español, igual que el código vecino (sin tildes en identificadores; comentarios cortos que explican el porqué).

## Reglas duras

1. **NO puedes ejecutar comandos ni pruebas.** Otra persona las correrá. Por eso: lee el código existente con MUCHO cuidado y NO inventes nombres de funciones, campos, argumentos ni rutas: verifica cada uno antes de usarlo. Si algo no se puede resolver leyendo, déjalo dicho en tu reporte final en vez de adivinar.
2. **Toca SOLO lo que pide la tarea.** No refactorices, no «mejores» código ajeno, no cambies pruebas existentes salvo que el spec lo exija (y entonces dilo). `backend/apps/bookings/admin.py`, `models.py` y `payments/views.py` son archivos grandes: ediciones QUIRÚRGICAS por bloques pequeños, nunca los reescribas completos.
3. **Migraciones: no puedes correr `makemigrations`.** Si la tarea pide una migración, escríbela a mano en el siguiente número libre de `backend/apps/bookings/migrations/` (mira la última), con `dependencies` correctas, y que el estado resultante coincida EXACTAMENTE con los campos del modelo (la verificación corre `makemigrations --check`).
4. **Nunca `except Exception` ni `except:` desnudo** para esconder un fallo. Atrapa solo la excepción concreta que significa «caso esperado». Un error real debe propagarse.
5. **Trampa de Django:** `ValidationError({'campo': 'texto'}, code='x')` **ignora `code=`** cuando el mensaje es un diccionario; el código va en el error interior: `ValidationError({'campo': ValidationError('texto', code='x')})`.
6. **Tenancy/RLS:** toda consulta corre bajo el alcance de la petición (empresa de quien la hace, u operador). No abras otro `scope.con_empresa` anidado con otra empresa (lanza `RuntimeError`). `select_for_update` sobre consultas con `select_related` de FKs opcionales debe llevar `of=('self',)`. Nunca `Reserva.objects.all()` fuera del alcance ni mezclando empresas.
7. **No cambies `ESTADOS_QUE_OCUPAN_CUPO`** (`bookings/models.py:82`) ni el significado de «ocupa cupo» en el resto del sistema: el apartado se cuenta SOLO dentro del adaptador del motor de cupo (`backend/apps/bookings/cupo/`), como dice el spec.
8. Unfold sirve un `styles.css` compilado: las clases Tailwind nuevas NO existen. En el frontend (Next.js) sí puedes usar las clases y componentes que ya usa el código vecino.

## Cómo escribir las pruebas (las pruebas son parte de la tarea)

- Pruebas Django en archivos NUEVOS con el nombre que pida la tarea. Base: `EmpresaTestCase` de `apps/testing.py` (en la carpeta de contexto tienes `testing_copia.py`, copia de solo lectura; importa SIEMPRE desde `apps.testing`, nunca desde la copia). Helpers: `crear_servicio_pesca`, `crear_flota`, `self.crear_vendedora()`, `self.crear_jefe()`. Mira pruebas parecidas ya existentes en `backend/apps/bookings/tests_*.py` y `backend/apps/payments/tests*.py` antes de escribir las tuyas.
- `EmpresaTestCase` mantiene abierto el alcance de UNA empresa durante todo el test: para sembrar datos de otra empresa o para un operador de plataforma, sal con `self._alcance.__exit__(None, None, None)` y restáuralo en `finally` con `self._alcance = scope.con_empresa(self.empresa); self._alcance.__enter__()` (hay ejemplos en `tests_enlace_pago.py` y `tests_alta_traslado.py`), o usa un `TestCase` aparte con `scope.como_operador_plataforma()`.
- **Nombres de personas SIN dígitos** en los datos de prueba (un validador rechaza `'Cliente 1'`). La pesca solo sale entre 05:00 y 07:00: usa `hora='06:00'`. Una reserva nueva necesita una fecha de mañana en adelante.
- Compara contra el cálculo real del sistema (llama a las funciones existentes en la prueba), no contra números inventados.
- Un test que debe fallar por una razón concreta debe asertar ESA razón (no solo «hay un error»), para que no enmascare otro fallo.
- Las pruebas de concurrencia con hilos y candados solo corren en Postgres (`@SOLO_POSTGRES`, ver `tests_concurrencia.py`); en SQLite los candados no hacen nada.

## Entrega

Al terminar, escribe un reporte final breve en español: qué archivos creaste/editaste, qué decisiones tomaste donde el spec dejaba margen, qué supuestos NO pudiste verificar (porque no ejecutas nada) y qué riesgos ves. No hagas commits (los hace el runner tras verificar).
