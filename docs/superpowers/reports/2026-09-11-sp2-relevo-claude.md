# Relevo a Claude — SP2 Sección 10 — 2026-09-11

El dueño interrumpió para continuar con Claude. NO continuar automáticamente ni
integrar/abrir PR a main. Trabajar en este worktree:
`C:/Users/kkjf/desarrollo/sistema-pescadeportiva/.claude/worktrees/transporte-multi-empresa`
Rama `feat/transporte-multi-empresa`. `fix/expansion-multi-sede-hallazgos` ya es ancestro.

## Commits hechos

- 173fb91: idempotency_key en update/capture/cancel; compensación por cupo centralizada
  en revertir_orden; cancelación mediante Reserva.save para liberar componentes/cupo.
  Incluye tests previos del usuario encontrados sin commit al empezar y preservados.
- ea71917: checkout espera estado capturada/cancelada consultando cada 5 s; no toma
  autorizada como fallo; reanuda sin repetir succeeded; card_error solicita evaluar
  conjunto incompleto para void. Callback opcional en StripePanel.
- de4a081: seed Pesca + Traslado. Ejecutado dos veces en SQLite local. Paquete ID 5,
  slug pesca-traslado, líder sal-y-sol + transporte-la-paz, 7500 MXN / 450 USD,
  almacenados en precio_ancla/precio_ancla_usd. No se duplicó.

## Pruebas completas ya terminadas, ANTES de los últimos cambios sin commit

- SQLite: manage.py test apps config --noinput: 862 tests, OK, skipped=27, 260.121 s.
  Log: C:/Users/kkjf/AppData/Local/Temp/sp2-sqlite-final.log
- PostgreSQL: mismo comando, 862 tests, OK, sin skips, 508.373 s.
  Log: C:/Users/kkjf/AppData/Local/Temp/sp2-postgres-final.log
- Antes de cada suite PostgreSQL se ejecutó DROP DATABASE IF EXISTS
  test_pescadeportiva_test. Contenedor psd-pg, puerto 5433. Rol ci_rls verificado
  NOSUPERUSER NOBYPASSRLS CREATEDB.
- Producción check --deploy --fail-level WARNING: exit 0, 0 issues, 1 silenciado W021.
- Frontend npm.cmd run lint, npx.cmd tsc --noEmit, npm.cmd run build: exit 0 los tres
  DESPUÉS del commit de checkout. Build 19 páginas, warning previo múltiples lockfiles.
- makemigrations --check --dry-run: sin cambios; migrate local: nada pendiente.

## EXACTAMENTE dónde quedó interrumpido

El repaso adicional encontró dos bugs, se escribieron regresiones y se reprodujeron
contra PostgreSQL en una DB de test separada usando DB_NAME=pescadeportiva_sp2_audit:

1. Correo combinado: el último webhook de empresa 2 lee orden.paquete bajo RLS de
   empresa 2 y falla Paquete.DoesNotExist. El test anterior usaba objeto con paquete
   cacheado, ocultando el bug. Se modificó
   notifications.tests.NotificarOrdenPagadaTest.test_notificar_orden_pagada_correo_combinado_y_whatsapp_por_empresa
   para recargar Orden dentro del scope de empresa 2 sin caché y verificar restauración
   del scope (solo assertion de aislamiento si PostgreSQL). Falló: no se envió correo.
2. Capturada es TERMINAL según plan sección 1 (no cambiar esa decisión de negocio).
   revertir_orden podía tocar pagos/reservas y luego fallar al transicionar capturada
   a cancelada. Se añadió
   payments.tests.OrdenesModuloTest.test_revertir_capturada_rechaza_antes_de_tocar_stripe.
   Falló antes del fix con ValidationError en vez de rechazo previo a Stripe.

Los fixes YA ESTÁN GUARDADOS, SIN COMMIT:
- notifications/services.py: cargar y cachear orden.paquete bajo scope de líder antes
  de construir el correo, dentro de bloque que restaura scope.
- payments/ordenes.py: refrescar orden bajo líder antes del loop; si capturada,
  levantar OrdenCerradaError ANTES de Stripe. Mantiene máquina de estados del plan.
- bookings/admin.py: atrapar OrdenCerradaError y mostrar warning, sin tumbar admin.
- Tests indicados en notifications/tests.py y payments/tests.py.

Se lanzó prueba enfocada tras aplicar fixes, pero el dueño interrumpió la llamada:
resultado DESCONOCIDO. Puede seguir en segundo plano. Comando lanzado:
DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_sp2_audit
DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433
venv/Scripts/python.exe manage.py test apps.notifications.tests.NotificarOrdenPagadaTest apps.payments.tests.OrdenesModuloTest --noinput

Revisar proceso antes de reusar DB. No pude inventariar Win32_Process por permisos.
Las suites verdes de 862 NO cubren estos últimos cambios. Volver a verificar focused,
añadir si procede test admin del rechazo capturado y correr apps+config COMPLETO en
ambos motores después del último cambio (ahora al menos 863 tests). No acotar PostgreSQL.

## Documentación sin commit

- backend/CLAUDE.md: sección Órdenes cruza-empresa y retirada nota obsoleta monoempresa.
- frontend/CLAUDE.md: checkout de paquete.
- ADR-005: IMPLEMENTADO 2026-09-11, desviaciones precio_ancla, MXN UI y seed periferia
  2200 MXN vs spec 1800 MXN; no cambia precio real aprobado.
- Plan sección 10: marcados 10.2/3/4/6/7/8/9/10; 10.1,10.5,10.11 pendientes.
- docs/superpowers/reports/2026-09-11-sp2-cierre.md contiene reporte extenso con
  migraciones y pendientes de producción. ES BORRADOR: aún dice PostgreSQL en curso,
  no incluye los dos últimos bugs/fixes. Actualizarlo con resultados definitivos.

## Bloqueo real de 10.5 (manual Stripe test)

No se hizo E2E real. SQLite local sal-y-sol tiene llave PLACEHOLDER;
transporte-la-paz tiene llave con prefijo test (no validada contra Stripe).
Se pidió por mensaje configurar secret/publishable test de líder en admin y avisar,
sin pegar secretos en chat. No hubo respuesta antes del relevo.
No sustituir (a) éxito completo, (b) segundo pago rechazado 4000000000000002 + void
primero/sin cargo, (c) webhook perdido + conciliar_pagos, por mocks. Reportar pendiente
hasta poder probar con las dos cuentas test. No usar claves live.

## Pendiente para cerrar

1. Verificar y commitear atómicamente últimos fixes; actualizar doc sobre rechazo
   de cancelación de orden capturada (terminal por diseño) y correo bajo scope líder.
2. Suite apps+config completa SQLite Y PostgreSQL, drop de DB test antes de PostgreSQL.
3. Completar 10.5 si el dueño configura llaves; de lo contrario dejarlo explícitamente
   pendiente. No declarar cierre integral ni inventar resultados.
4. Actualizar reporte, ADR y plan con resultados exactos, commits y últimos hallazgos.
5. Commit solicitado por dueño: docs(plan): SP2 completado. Si falta 10.5, el cuerpo
   y reporte deben decirlo claramente; aún no se ha hecho ese commit.
6. PARAR. Nada de memoria, main, PR, merge ni producción.

Preservar .great_cto: cambios y logs previos del usuario, NO incluirlos en commits.
Git index vive en .git/worktrees compartido: sandbox bloquea index.lock, requirió
escalación para git add/commit. Docker también se invocó fuera del sandbox.
En PowerShell usar npm.cmd/npx.cmd (npm.ps1 bloqueado por execution policy).
