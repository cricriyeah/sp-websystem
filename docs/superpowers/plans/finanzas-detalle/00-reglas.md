# Reglas comunes (se anteponen a cada tarea)

Proyecto Django (backoffice con Unfold, 4 empresas con tenancy y RLS) + Next.js. Estás en el worktree `.claude/worktrees/traslados` (rama `feat/traslados-vehiculos`). Implementas UNA tarea de un plan mayor: **del paso 7 del rediseño del backoffice: Finanzas con detalle**. La fuente de verdad del diseño es el encargo de esta tarea (más abajo). Lee también `backend/apps/finance/` completo antes de empezar. Lee también `backend/CLAUDE.md`. Código y comentarios en español, igual que el código vecino (sin tildes en identificadores; comentarios cortos que explican el porqué).

## Reglas duras

1. **NO puedes ejecutar comandos ni pruebas.** Otra persona las correrá. Por eso: lee el código existente con MUCHO cuidado y NO inventes nombres de funciones, campos, argumentos ni rutas: verifica cada uno antes de usarlo. Si algo no se puede resolver leyendo, déjalo dicho en tu reporte final en vez de adivinar. El modelo análogo ya resuelto es `EmbarcacionNoDisponible` / la Agenda de pangas (`backend/apps/fleet/models.py`, `backend/apps/fleet/admin.py`, `AgendaAdmin` en `backend/apps/bookings/admin.py`): imítalo.
2. **Toca SOLO lo que pide la tarea.** No refactorices, no «mejores» código ajeno, no cambies pruebas existentes salvo que el spec lo exija (y entonces dilo). `backend/apps/bookings/admin.py` y `models.py` son archivos grandes: ediciones QUIRÚRGICAS por bloques pequeños, nunca los reescribas completos.
3. **Migraciones: no puedes correr `makemigrations`.** Escríbelas a mano en el siguiente número libre de la app (mira la última de `backend/apps/fleet/migrations/` y de `backend/apps/bookings/migrations/`), con `dependencies` correctas, y que el estado resultante coincida EXACTAMENTE con los campos de los modelos (la verificación corre `makemigrations --check`). Las políticas RLS van en su propia migración, con el patrón de `backend/apps/bookings/migrations/0050_rls_reservasalida.py`.
4. **Nunca `except Exception` ni `except:` desnudo** para esconder un fallo, salvo el caso que el spec pide expresamente (§5, envoltura segura del gancho). Atrapa la excepción concreta que significa «caso esperado».
5. **Trampa de Django:** `ValidationError({'campo': 'texto'}, code='x')` ignora `code=` cuando el mensaje es un diccionario.
6. **Tenancy/RLS:** toda consulta corre bajo el alcance de la petición. No abras otro `scope.con_empresa` anidado con otra empresa (lanza `RuntimeError`). `select_for_update` sobre consultas con `select_related` de FKs opcionales lleva `of=('self',)`. Una vista pública consulta DENTRO del alcance. Una migración de datos sobre tablas con RLS se envuelve en `with apps.tenancy.rls.alcance_operador_migracion(schema_editor.connection):` (lectura y escritura).
7. **No cambies `ESTADOS_QUE_OCUPAN_CUPO`** (`bookings/models.py`) ni el cupo: la venta de traslados sigue siendo `bajo_demanda`.
8. Unfold sirve un `styles.css` compilado: las clases Tailwind nuevas NO existen. Usa estilos en línea o el CSS propio (`backend/apps/bookings/static/bookings/admin-columnas.css`), como hace la Agenda.

## Cómo escribir las pruebas (las pruebas son parte de la tarea)

- Pruebas Django en archivos NUEVOS con el nombre que pida la tarea. Base: `EmpresaTestCase` de `apps/testing.py`. Helpers: `crear_servicio_pesca`, `crear_flota`, `self.crear_vendedora()`, `self.crear_jefe()`. Mira pruebas parecidas (`backend/apps/bookings/tests_agenda.py`, `tests_alta_traslado.py`, `tests_disponibilidad.py`) antes de escribir las tuyas.
- `EmpresaTestCase` mantiene abierto el alcance de UNA empresa durante todo el test: para sembrar datos de otra empresa o un operador de plataforma, sal con `self._alcance.__exit__(None, None, None)` y restáuralo en `finally` (ejemplos en `tests_enlace_pago.py`), o usa un `TestCase` aparte con `scope.como_operador_plataforma()`.
- **Nombres de personas SIN dígitos** en los datos de prueba. Una reserva de transporte necesita su `DetalleTransporte` (mira `tests_alta_traslado.py` para crear una válida). La pesca solo sale entre 05:00 y 07:00; el transporte no tiene esa ventana.
- Compara contra el cálculo real del sistema, no contra números inventados. Un test que debe fallar por una razón concreta debe asertar ESA razón.
- Las pruebas de RLS y de candados solo tienen sentido en Postgres (`@SOLO_POSTGRES`, ver `tests_concurrencia.py`); en SQLite se saltan.

## Entrega

Al terminar, escribe un reporte final breve en español: qué archivos creaste/editaste, qué decisiones tomaste donde el spec dejaba margen, qué supuestos NO pudiste verificar y qué riesgos ves. No hagas commits (los hace el runner tras verificar).

## Trampas de pruebas ya vividas (evítalas)

1. Las pruebas con `EmpresaTestCase` mantienen abierto el alcance de UNA empresa. Una petición de un operador u OTRA empresa abre su propio alcance en el middleware y revienta con «Ya hay un alcance de tenancy activo»; para sembrar o leer datos de otra empresa sal del alcance (`self._alcance.__exit__(None, None, None)`) y restáuralo en `finally` (hay ejemplos en `backend/apps/bookings/tests_traslados_admin.py` y `tests_disponibilidad.py`). Con RLS real (Postgres) un alcance no puede escribir filas de otra empresa.
2. `aplicar_pago_exitoso(intent, empresa)` recibe 2 argumentos.
3. Nombres de personas SIN dígitos en los datos de prueba.
4. NO crees migraciones ni toques las existentes: `python manage.py makemigrations --check` debe seguir diciendo «No changes detected».
5. No uses `except Exception`.
