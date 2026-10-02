# Prompts para ejecutar el cambio 2 (salidas en varios días)

Uso: a cada agente se le dice solo "Lee docs/superpowers/plans/prompts-cambio-2-salidas.md y ejecuta el Preámbulo común más el Prompt X". Orden: A, B, C y luego D. Cada uno depende de que el anterior haya dejado el árbol en verde. Modelo recomendado: Sonnet con esfuerzo alto.

## Preámbulo común (va en todos los prompts)

Trabajas en el worktree C:\Users\kkjf\desarrollo\sistema-pescadeportiva\.claude\worktrees\checkout-unificado (rama feat/checkout-unificado). Solo tocas backend/ y docs/. NO hagas commits y NO reviertas cambios sin commitear que ya existan (hay trabajo previo en el mismo árbol; conservarlo es tu responsabilidad).

Plan que ejecutas: docs/superpowers/plans/2026-10-01-salidas-multidia-paquetes.md. Léelo completo antes de empezar, junto con docs/superpowers/specs/2026-10-01-paquetes-por-persona-y-salidas-multidia-design.md y backend/CLAUDE.md. El plan trae el código y las pruebas de cada paso: síguelo en orden y con TDD (prueba que falla, implementación, prueba que pasa).

Entorno:
- No hay venv en el worktree. Usa SIEMPRE: PY=C:/Users/kkjf/desarrollo/sistema-pescadeportiva/backend/venv/Scripts/python.exe, y corre los comandos desde backend/.
- Shell Git Bash en Windows. Los comandos en primer plano mueren a los 120 s: corre las suites largas con run_in_background. No uses heredocs largos para escribir archivos: usa la herramienta de escritura.
- NO corras `npm run build` ni toques el frontend: hay un servidor de desarrollo activo y un build lo daña.
- Los nombres de archivo, campos y funciones del plan se verificaron al escribirlo, pero el código puede haber cambiado. Si algo no coincide (un campo obligatorio de un modelo, el nombre de una función), léelo y adáptate, pero NO debilites ninguna aserción para que pase. Anota cada adaptación en tu reporte.
- Reglas del proyecto: textos al cliente dicen "retenido/retención", nunca "autorizado"; cada tabla nueva con empresa_id lleva política RLS; pesos y dólares no se suman ni se convierten.
- Falla conocida que NO es tuya: apps.finance.tests.PanelPorPeriodoTests.test_una_etiqueta_y_un_dato_por_cada_dia_del_periodo falla solo los días 1 de cada mes.

Reporte final obligatorio: archivos creados y modificados, salida LITERAL de cada comando de prueba que corriste, cada adaptación al plan con su motivo, y todo lo que no pudiste verificar. Si algo del plan resulta imposible o contradice el código, detente y repórtalo en vez de improvisar.

## Prompt A: Tasks 1 a 4 (reglas, modelos, cupo, confirmación)

Ejecuta las Tasks 1, 2, 3 y 4 del plan, en ese orden, con TDD.

Contexto clave: una actividad de un paquete (por ejemplo pesca) puede repetirse en días seguidos (PaqueteServicio.salidas). El cupo hoy se cuenta solo por Reserva.fecha; sin las Tasks 2 a 4 se podría sobrevender la misma panga en los días 2 a 5. Lo que más importa es que NO se sobrevenda y que NADA cambie para lo existente (salidas = 1).

Puntos de atención:
- Task 2: las migraciones son fleet 0039 y bookings 0049 y 0050 (la última de fleet hoy es 0038_paquete_precio_por_persona y la de bookings 0048). La 0050 es la política RLS de bookings_reservasalida, copiada de 0027_rls_reservaocupacion. ReservaSalida NO tiene panga ni capitán.
- Task 3: el filtro salidas__isnull=True evita contar dos veces el primer día. Verifica con las pruebas del plan Y corre antes las suites de cupo existentes (apps.bookings.tests_cupo_*, apps.bookings.cupo) para confirmar que no cambian.
- Task 4: los locks de cupo van en orden de fecha ascendente. Si falta cupo en cualquier día debe ocurrir el rollback y reembolso 100 % que ya existen, sin dejar ReservaSalida huérfanas.
- Antes de cerrar, corre en segundo plano: $PY manage.py test apps.fleet apps.bookings apps.payments. Debe quedar verde.

Al terminar, reporta y NO sigas con la Task 5.

## Prompt B: Tasks 5 y 6 (una panga, habitaciones automáticas)

Las Tasks 1 a 4 ya están hechas en el árbol (verifica con git status que existen ReservaSalida y las migraciones 0039/0049/0050; si no, detente). Ejecuta las Tasks 5 y 6 del plan, con TDD.

Contexto clave:
- Task 5: una sola panga y un solo capitán para TODA la estancia, asignados en la reserva (Agenda actual). La regla "una panga, una salida por día" debe revisar cada día de mar. Lee primero el cuerpo actual de Reserva._validar_una_salida_por_dia y conserva sus mensajes exactos de error: las pruebas de la agenda existentes deben seguir verdes.
- Task 6: el motor ya soporta varias habitaciones por reserva (cantidad_recursos); la asignación siempre pedía una. Agrega habitaciones_necesarias y úsala en evaluar_disponibilidad_hospedaje y en _asignar_cupo_hospedaje. Efecto esperado: grupos que antes se rechazaban por no caber en UNA habitación ahora se aceptan si caben en varias libres. Si una prueba existente asumía lo contrario, ajusta su aserción a "no alcanzan las habitaciones juntas" y repórtalo explícitamente; no la borres.
- Cuida los casos límite: el grupo cabe exacto en una habitación (debe seguir siendo una), no hay habitaciones activas (SinCupoError como hoy) y las habitaciones ocupadas en el rango no cuentan como libres.
- Antes de cerrar, corre en segundo plano: $PY manage.py test apps.bookings apps.payments apps.fleet. Verde.

Al terminar, reporta y NO sigas con la Task 7.

## Prompt C: Tasks 7 y 8 (API, compuerta, Postgres)

Las Tasks 1 a 6 ya están hechas en el árbol. Ejecuta las Tasks 7 y 8 del plan.

Task 7: el catálogo público devuelve salidas por servicio asociado (revisa backend/apps/fleet/catalogo.py y el serializador).

Task 8, compuerta completa:
1. Actualiza backend/CLAUDE.md con el texto del plan y corrige lo que quedó desactualizado en las secciones de cupo (busca la nota sobre una salida por día y confirma que sigue siendo cierta).
2. Suite completa SQLite, en segundo plano: $PY manage.py test apps config. Solo se admite el fallo conocido de finance.
3. Suite completa Postgres. Docker Desktop debe estar abierto: docker start psd-pg; verifica el rol: docker exec psd-pg psql -U postgres -d pescadeportiva_test -tc "select rolname, rolbypassrls from pg_roles where rolname='ci_rls'" (debe ser bypassrls = f). Corre, en segundo plano, con timeout largo: DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 $PY manage.py test apps config --noinput. Debe pasar test_guardarrail_toda_tabla_con_empresa_tiene_politica (confirma la RLS de la tabla nueva). Si Docker no está disponible, dilo y NO declares el gate cerrado.
4. Prueba de concurrencia del plan (Task 8, paso 4) en tests_concurrencia.py, solo Postgres: dos confirmaciones simultáneas de paquetes con salidas solapadas sobre una flota de una sola panga; exactamente una queda confirmada y la otra cancelada con reembolso. Si no logras una prueba determinista, dilo y explica por qué en vez de dejarla intermitente.
5. Aplica las migraciones a la base local del worktree: $PY manage.py migrate (la base db.sqlite3 de backend/ la usa el servidor de desarrollo).

Reporta el resultado literal de ambas suites completas.

## Prompt D: revisión independiente (después de C; no modifica archivos)

Revisa SIN modificar archivos el cambio de "salidas en varios días" en el worktree indicado (git diff y git status; si el cambio 1 de precio por persona no está commiteado, ignora lo que no sea de salidas). Lee el plan docs/superpowers/plans/2026-10-01-salidas-multidia-paquetes.md.

Busca específicamente, con archivo y línea:
1. SOBREVENTA: ¿existe algún camino por el que una panga o el cupo de un día de mar se pueda vender dos veces? Revisa obtener_contexto_cupo y obtener_contexto_rango, el doble conteo del primer día, reservas canceladas, excluir_pk con las salidas de la propia reserva, y la validación al hacer full_clean de una reserva que ya tiene salidas.
2. CONFIRMACIÓN DE PAGO: ¿hay un caso donde falte cupo en un día y queden ReservaSalida o componentes huérfanos, o el reembolso no ocurra? ¿El orden de locks es siempre ascendente?
3. REGRESIÓN: con salidas = 1 todo debe comportarse como antes. Compara el camino de una sola fecha en confirmacion.py y _validar_cupo_de_paquete contra git (git diff) y marca cualquier cambio de comportamiento.
4. RLS: la migración 0050 aplica la política tenancy_alcance a bookings_reservasalida; confirma que usa empresa_id y que ReservaSalida.empresa siempre se llena con la empresa de la reserva.
5. HABITACIONES: habitaciones_necesarias y la asignación de varias habitaciones. Casos límite: capacidad justa, habitaciones ocupadas en el rango, ninguna activa, grupo mayor que la suma de todas.
6. PANGA ÚNICA: la regla de una salida por día revisa todos los días de mar y también ve a las reservas sueltas; el capitán igual.
7. Cambios en el comportamiento de pruebas existentes: lista toda prueba existente que se modificó y juzga si el ajuste fue legítimo o debilitó una aserción.

Clasifica cada hallazgo como CRÍTICO / IMPORTANTE / MENOR / NO VERIFICABLE. Corre las suites relevantes en segundo plano (apps.bookings, apps.payments, apps.fleet) y pega el resultado literal. No modifiques nada.


## Prompt E: correcciones de la revisión D (después de D)

Las Tasks 1 a 8 están hechas. La revisión independiente (Prompt D) encontró problemas reales que debes corregir ahora, con TDD (primero la prueba que falla, después el arreglo). Lee antes los archivos que cita cada punto. No toques el frontend. Corre las suites largas en segundo plano y UNA SOLA suite de Postgres a la vez.

### E1. Dos servicios de mar pueden vender la misma panga a la vez (CRÍTICO, ya existía)
El cupo se calcula contra la flota completa de la EMPRESA (backend/apps/bookings/cupo/adaptador.py: obtener_contexto_cupo), pero el lock de cupo incluye servicio_id en su clave (backend/apps/bookings/cupo/candado.py: calcular_clave_candado). Dos pagos de servicios distintos de la misma empresa (por ejemplo pesca y avistamiento, que comparten pangas) no se serializan y pueden confirmar a la vez.
- Arreglo: el lock de cupo de actividades debe serializar por (empresa, fecha) y NO depender del servicio. Haz que bloquear_cupo ignore servicio_id (conserva el parámetro por compatibilidad de firma) y use siempre la clave de la fecha. Actualiza el docstring.
- Pruebas: en tests_cupo_candado.py, actualiza lo que asumía claves distintas por servicio (es un cambio legítimo; repórtalo) y agrega que dos servicios en la misma fecha dan la MISMA clave. En tests_concurrencia.py (solo Postgres) agrega una prueba con DOS servicios de mar distintos de la misma empresa y UNA sola panga: dos pagos simultáneos, uno por servicio, exactamente uno aplicado y el otro cancelado con reembolso.

### E2. Reserva multidía pagada creada o reprogramada desde el admin queda sin salidas (CRÍTICO)
Las ReservaSalida solo se crean al confirmar un pago (backend/apps/bookings/cupo/confirmacion.py). Si desde el admin (backend/apps/bookings/admin.py, ReservaAdmin) se crea una reserva pagada de un paquete con salidas, o se cambia fecha/inicio_paquete de una ya pagada, los días de mar quedan sin cupo registrado o con las fechas viejas.
- Arreglo: crea una función idempotente sincronizar_salidas(reserva) (en apps/bookings/cupo/, junto a confirmacion.py) que calcula los días de mar deseados con fechas_de_componente(reserva.fecha_inicio_paquete, ps.dia_estancia, ps.salidas) para la actividad con salidas > 1 de su paquete, compara con las ReservaSalida existentes, borra las que sobran y crea las que faltan. Solo actúa si la reserva tiene paquete, no tiene orden, el paquete tiene una actividad por_recurso_dia con salidas > 1 y el estado ocupa cupo. Úsala en reservar_cupo_al_confirmar (reemplaza el ciclo que crea las salidas) y desde Reserva.save() después de super().save(), solo cuando update_fields es None (el listado editable de la Agenda guarda con update_fields y no debe disparar esto).
- Pruebas (en tests_salidas.py o un archivo nuevo): crear una reserva PAGADA de paquete multidía por el ORM con full_clean + save crea las salidas; reprogramar (cambiar inicio_paquete y fecha) mueve las salidas y el cupo se cuenta en las fechas nuevas y no en las viejas; guardar dos veces no duplica; una reserva cancelada conserva sus filas pero no cuenta cupo.

### E3. Paquetes de un día y de varios días pueden interbloquearse (CRÍTICO)
En confirmacion.py el paquete multidía toma primero todos los locks de mar y después las habitaciones; uno de un día con el hospedaje en primer orden bloquea primero las habitaciones y después el mar. Cruzados, Postgres puede abortar un pago por deadlock, y ese error no está entre las excepciones que aplicar_pago_exitoso compensa (backend/apps/payments/services.py).
- Arreglo A: orden canónico de locks para TODOS los paquetes (no solo multidía): primero los locks de mar de todas las actividades, ordenados por fecha, y después los de habitaciones. Toma los locks de mar por adelantado antes del ciclo de componentes. Los locks son reentrantes dentro de la transacción, así que no hace falta quitarlos del resto.
- Arreglo B: en aplicar_pago_exitoso, si la transacción aborta por deadlock (django.db.utils.OperationalError con causa de deadlock, sqlstate 40P01), reintenta UNA vez la transacción completa; si vuelve a fallar, deja que se propague como hoy (conciliar_pagos es la red de seguridad).
- Pruebas: una prueba que registre el orden de las llamadas a bloquear_cupo y bloquear_recurso para un paquete de un día con el hospedaje en orden 1 y compruebe que todas las de mar van antes que las de habitación. Una prueba de concurrencia (solo Postgres) con un paquete de un día con hospedaje primero y uno multidía solapados: ambos terminan sin excepción de deadlock (corre 5 veces seguidas para descartar intermitencia).

### E4. Dos actividades de mar con salidas múltiples cuentan dos grupos (IMPORTANTE)
backend/apps/fleet/paquete_reglas.py permite varias actividades en los mismos días y la confirmación crea una salida por servicio y día; el cupo las suma como dos viajes aunque la reserva usa una sola panga.
- Arreglo: nueva regla en errores_de_paquete: si alguna actividad tiene salidas > 1, no puede haber otra actividad (por_recurso_dia) en el paquete. Mensaje: "Una actividad de varios días no puede acompañarse de otra actividad de mar en el mismo paquete."
- Prueba en tests_paquete_reglas.py.

### E5. Solo documentar (NO cambiar código)
En backend/CLAUDE.md, sección de cupo, agrega una nota breve: la validación de panga y capitán (Reserva._validar_una_salida_por_dia) consulta sin lock, igual que antes de este cambio, así que dos operadores asignando la misma panga al mismo tiempo podrían pasar ambos; y una reserva pendiente_pago con panga puesta no tiene salidas todavía, así que su validación solo ve Reserva.fecha. Ambas son limitaciones conocidas y aceptadas por ahora.

### Cierre
1. $PY manage.py test apps.bookings apps.payments apps.fleet en segundo plano, verde.
2. Suite completa de Postgres, UNA vez al final y sin correr nada más en paralelo (docker start psd-pg; comando en el Prompt C). Solo se admite el fallo conocido de finance.
3. Reporte con la salida literal de cada comando, las pruebas existentes que ajustaste con su motivo, y lo que no pudiste verificar.
