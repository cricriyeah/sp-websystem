# Revisión de código: backoffice (notificaciones, avisos, Turnstile en login, transferencia)

**Primera línea, tamaño:** el cambio es grande. Worktree contra 22026a87: 41 archivos, +4819 / -248. Sin pruebas, docs ni migraciones: 25 archivos, +1749 / -168. No pude revisar todo con el mismo cuidado; la sección "No cubierto" dice qué quedó fuera.

**Método:** lectura de código con Read/Grep/git. No ejecuté pruebas ni la suite (instrucción del coordinador). Todo hallazgo de comportamiento en tiempo de ejecución está marcado como "lectura de código, no ejecutado". Base de la revisión: commit 31391e04 (publicado) más los cambios sin commitear (avisos.js, avisos.css, login.py, login-turnstile.js, messages.html, admin/login.html, config, render.yaml).

## Tabla de severidad

| Sev. | Cant. | Hallazgos |
|---|---|---|
| Crítico | 1 | C1 |
| Mayor | 4 | M1, M2, M3, M4 |
| Menor | 5 | m1 a m5 |
| Nit / Observación | 4 | n1 a n4 |

## Hallazgos

### C1 (Crítico). El aviso de pantalla "Correo enviado / No se pudo avisar" nunca llega al admin en producción, y las pruebas lo ocultan

- **Dónde:** `apps/bookings/admin.py` ~318-346 (`AvisoDeAsignacionMixin._decir_lo_que_paso`, `changelist_view`, `changeform_view`); `apps/bookings/signals.py` (`transaction.on_commit(lambda: _mandar(...))` y `_anotar_resultado`); `apps/tenancy/middleware.py` (`with alcance:` alrededor de toda la petición).
- **Mecanismo (lectura de código, no ejecutado):** `EmpresaScopeMiddleware` envuelve la petición entera en `scope.con_empresa` / `como_operador_plataforma`, que abre `transaction.atomic()`. Los `on_commit` registrados durante `save_model` se ejecutan al salir de ese `atomic` exterior, es decir, después de que `changeform_view` ya llamó `tomar_resultados_de_aviso()` / `_decir_lo_que_paso()`. Resultado: la lista de resultados está vacía cuando se lee.
- **Consecuencia:** el requisito explícito del dueño ("al asignar panga y capitán debe aparecer un aviso que diga correo enviado… y si falla, por qué") no se cumple en pantalla. Solo queda la notificación persistente, que sí se escribe porque `_dejar_constancia` corre dentro de `con_empresa`. El propio `backend/CLAUDE.md` (sección «Avisos del admin») lo llama "limite conocido" y dice que "casi nunca aparece"; en el código de rutas de admin con membresía es "nunca".
- **Por qué no se detectó:** `tests_aviso_mensajes.py:21` (`AL_INSTANTE`, parchea `transaction.on_commit` para ejecutar al instante), `tests_notificaciones_procesos.py:33` y el docstring de `tests_aviso_mensajes.py:4-5` afirman que eso "ocurre como en producción". No es cierto. El mock oculta el defecto.
- **Arreglo propuesto:** en `changeform_view` y `changelist_view`, después de `super()`, registrar `transaction.on_commit(lambda: self._decir_lo_que_paso(request))`. El orden de registro garantiza que corre después de `_mandar`. `MessageMiddleware` escribe los mensajes después del middleware de alcance, así que el mensaje sí se guarda en la respuesta. Añadir una prueba que NO parchee `on_commit` y que cuente el mensaje en la respuesta del cliente.
- **Estado:** hipótesis fuerte por lectura de código; falta confirmarla con una prueba sin mock.

### M1 (Mayor). Si Cloudflare no carga, nadie puede entrar al backoffice

- **Dónde:** `apps/tenancy/static/tenancy/login-turnstile.js:4-18`; `templates/admin/login.html` (div `#login-turnstile` con `hidden`); `apps/cuentas/login.py:25-28` (`MENSAJE_CAPTCHA`).
- **Mecanismo (lectura de código):** el widget se muestra solo cuando `cargaTurnstileLogin` corre. Si `challenges.cloudflare.com` está bloqueado (bloqueador de anuncios, red corporativa, caída), la caja queda oculta y sin token. El formulario responde con "Espera a que termine la verificación", que no tiene a qué esperar.
- **Consecuencia:** lockout total del equipo hasta que alguien cambie `LOGIN_TURNSTILE_OBLIGATORIO=0` en Render, lo que requiere acceso a Render y un redeploy.
- **Arreglo:** si tras unos segundos no existe `window.turnstile`, mostrar la caja con un mensaje claro ("No carga la verificación: desactiva el bloqueador de anuncios o recarga"). Revisar el texto de `MENSAJE_CAPTCHA` para que no sugiera esperar un widget que no está.

### M2 (Mayor). Un pago rechazado por falta de cupo, con reembolso automático, no deja ninguna constancia en Notificaciones

- **Dónde:** `apps/payments/services.py:357-388` (`_cancelar_sin_cupo`, sin `registrar_notificacion`); `_notificar_reserva_nueva` (~línea 190) se llama después del `return` de sin cupo; `aplicar_reembolso` (~482-490) regresa antes de notificar porque `monto_reembolsado` ya quedó fijado.
- **Mecanismo (lectura de código):** el reembolso sí ocurre; el webhook `charge.refunded` detecta que ya estaba registrado y sale sin notificar.
- **Consecuencia:** el dinero sale sin aviso en el feed, y la reserva nunca aparece como "Nueva reserva". El objetivo del feed ("si llegó una reserva y nadie la vio") queda incumplido en este caso.
- **Arreglo:** llamar `registrar_notificacion` (nivel AVISO, tipo REEMBOLSO o CANCELACION) dentro de `_cancelar_sin_cupo`, en la misma transacción.

### M3 (Mayor). La cancelación del PaymentIntent en Stripe ocurre dentro de la transacción con lock, y un rollback posterior no la deshace

- **Dónde:** `apps/bookings/transferencia.py:66-76` (`_cerrar_cobro_con_tarjeta`: `retrieve` y `cancel` en Stripe); `:93` (`select_for_update`); `:106` (llamada a Stripe dentro del `atomic`); `:116-125` (`SinCupoError` / `ValidationError` / `IntegrityError` después, que hacen rollback).
- **Mecanismo (lectura de código):** si la cancelación de Stripe tiene éxito y después falla el cupo o la validación, la base hace rollback pero el PaymentIntent queda cancelado. La reserva queda `pendiente_pago` con un intent muerto. Además, la red a Stripe se hace con la fila bloqueada, así que dos operaciones o el webhook quedan esperando.
- **Consecuencia:** reserva atorada en estado inconsistente tras un error visible al operador; latencia con lock.
- **Arreglo:** validar cupo y `full_clean` antes de cancelar en Stripe (o aplicar el cupo y luego cancelar en `on_commit` con reintento); sacar la llamada de red fuera del bloqueo, con reverificación del estado al entrar al `atomic`.

### M4 (Mayor). `setup_roles` corre en cada build de Render y sobrescribe los permisos de grupo

- **Dónde:** `render.yaml` (buildCommand: `migrate && setup_roles`); `apps/bookings/management/commands/setup_roles.py` (`_grupo`: `group.permissions.set(perms)`, y `sincronizar_todos()`).
- **Mecanismo (lectura de código):** cada despliegue reemplaza los permisos de Vendedora, Jefe y OperadorPlataforma por los del código. Cualquier ajuste manual hecho en el admin se pierde. Un error en `setup_roles` (por ejemplo, un codename que no exista) también tumba el build.
- **Consecuencia:** cambios de autorización en producción sin intervención humana, en cada deploy.
- **Arreglo:** correrlo solo en un paso explícito (no en buildCommand), o que solo agregue permisos que falten sin hacer `set`. Documentar que los permisos de grupo se gobiernan desde código.

### m1 (Menor). Tipo de notificación equivocado en "Reserva pagada por transferencia"

- **Dónde:** `apps/bookings/transferencia.py:151` usa `Notificacion.Tipo.RESERVA_NUEVA`; existe `Tipo.TRANSFERENCIA`.
- **Consecuencia:** el filtro por tipo del feed mezcla transferencias con pagos con tarjeta.
- **Arreglo:** cambiar a `Tipo.TRANSFERENCIA`.

### m2 (Menor). Si `avisos.js` no se ejecuta, los mensajes de Django desaparecen

- **Dónde:** `apps/tenancy/static/tenancy/avisos.css` (`[data-avisos-django] { display: none }`); `templates/unfold/helpers/messages.html`; `avisos.js` `convertirAvisosDeDjango` (fallback `lista.style.display = 'block'`).
- **Mecanismo:** el CSS oculta el bloque antes de que el JS tenga oportunidad de convertirlo. Si el JS falla al cargar, el bloque queda oculto. Además, si el fallo ocurre a mitad de la conversión, el fallback muestra la lista completa, duplicando los ya convertidos.
- **Consecuencia:** contradice el comentario de `messages.html` ("nunca se pierde un mensaje").
- **Arreglo:** ocultar solo cuando el script marque `<html>` o el bloque (clase que pone el JS al arrancar), no al cargar el CSS. En el fallback, desmarcar los ítems ya convertidos.

### m3 (Menor). Heurística de "Notificación nueva" puede tragarse avisos y duplica la acción propia

- **Dónde:** `avisos.js` `pintarCampana` (`nuevas = n - conteoAnterior - datos.total`).
- **Mecanismo (lectura de código):** si en la misma ventana de 10 s entra una reserva (total=1) y una notificación de otro tipo (n+1), la resta da 0 y la notificación no se muestra. Además, la propia acción del usuario produce una "Notificación nueva" justo después de su aviso de pantalla.
- **Consecuencia:** avisos perdidos en casos concurrentes; ruido por la acción propia.
- **Arreglo:** que el servidor devuelva los ids de notificaciones nuevas y el JS las compare, en vez de restar contadores.

### m4 (Menor). El sondeo se detiene para siempre tras 3 fallos, sin aviso

- **Dónde:** `avisos.js` `consultar` / `parar` / `visibilitychange` (`fallos < FALLOS_PARA_PARAR`).
- **Mecanismo:** una sesión vencida (respuesta HTML del login) cuenta como fallo. Tras 3, el sondeo se para y ya no vuelve a arrancar al cambiar de pestaña.
- **Consecuencia:** la pestaña deja de avisar en silencio hasta recargar. Aceptable, pero sin señal al usuario.
- **Arreglo:** al detectar sesión vencida, mostrar un aviso "Sesión vencida: recarga" en vez de callar.

### m5 (Menor). Pruebas con mock que dan verde en un caso que producción no produce

- **Dónde:** `tests_transferencia.py:118-130` espera "Se le mandó el correo de confirmación" en la pantalla; en producción esa vista aún no tiene resultado y muestra "sale en unos segundos". Mismo problema de `on_commit` que C1.
- **Arreglo:** pruebas que confirmen la transacción real de la petición, no un `on_commit` inmediato.

## Observaciones (no bloquean)

- **n1:** `signals.py` guarda en un `threading.local` hasta 50 resultados con el correo del cliente hasta que llega otro POST a una vista envuelta. Es memoria del proceso, no persistente; conviene limpiarlo al terminar la petición.
- **n2:** `notifications/services.py` (`motivo_para_persona`) guarda en el feed el mensaje de Resend; podría incluir el correo del destinatario. Revisar el texto de rechazo antes de persistirlo.
- **n3:** `_mandar` hace la llamada HTTP a Resend dentro de la petición, después de la vista (latencia visible). Tiene timeout de 10 s.
- **n4:** `messages.html` es copia de la de Unfold; una actualización de Unfold la desalinea. `avisos.js` `desbloquearAudio` llama `resume()` (asíncrono) y `sonar()` justo después; en navegadores que arrancan suspendidos la primera prueba de sonido puede no sonar. No verificado.

## Lo que está bien (verificado por lectura)

- Migración 0011: políticas RLS bien formadas para `tenancy_notificacion` y `tenancy_lecturanotificacion`; `FORCE` aplicado; operador de plataforma cubierto.
- `limpiar_notificaciones` usa `como_operador_plataforma()`, así que sí borra filas bajo RLS.
- `enlace_seguro` rechaza `javascript:`, `//` y caracteres de control; `NotificacionAdmin` escapa con `format_html`; "marcar como leídas" solo escribe lecturas de quien lo pide.
- `verificar_turnstile_obligatorio`: falla cerrado; valida `success`, `action` y `hostname`. `LoginConTurnstile.clean` verifica antes de la contraseña, así que un captcha malo no cuenta como intento de Axes.
- `login_before` y `login_after` existen en la plantilla de Unfold; `skeleton.html` incluye `styles` y `scripts`, así que las páginas de recuperación cargan avisos.js.
- `SesionSinRenovarEnSondeo`: exacto en `/admin/avisos/reservas-nuevas/`.
- Saldo: `models.py:1169` descuenta `monto_transferencia`, así que un anticipo deja saldo correcto.

## No cubierto

- No ejecuté ninguna prueba ni la suite (instrucción del coordinador). Todo hallazgo de tiempo de ejecución es hipótesis fuerte por lectura.
- No leí completos `docs/architecture/ARCH-notificaciones-backoffice.md` ni `docs/security/CSO-notificaciones-backoffice.md`; solo verifiqué referencias puntuales.
- No revisé en detalle `apps/bookings/tests_*` ni las pruebas de RLS en Postgres.
- No revisé `apps/cuentas/views.py` ni el flujo de recuperación de contraseña fuera del login.
- No revisé `apps/finance` ni la conciliación de finanzas con `monto_transferencia`.
- No revisé el JS de avisos completo línea por línea (la mayoría de funciones sí).
- No hubo revisión cross-model.

## Verdicto

**BLOCKED.** La razón: el requisito explícito del dueño (aviso en pantalla con el resultado del correo de asignación) no llega a producción (C1), y las pruebas en verde lo ocultan.
