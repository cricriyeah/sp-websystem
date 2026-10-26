# PCI-transferencia-y-cobros — Revisión del manejo de dinero tocado el 2026-10-26

Reviewed: base 22026a87 + 31391e04 (publicado) + cambios sin commitear. Archivos leídos: `backend/apps/bookings/transferencia.py`, `backend/apps/payments/services.py` (completo salvo disputas), `backend/apps/payments/views.py` (`CrearPagoView` A/C, `_intent_de`, `StripeWebhookView`), `backend/apps/payments/ordenes.py:192-271`, `backend/apps/bookings/admin.py` (transferencia, efectivo, cancelación, `save_model`), `backend/apps/bookings/cobros.py`, `Reserva._registrar_movimientos_de_dinero`, `signals.py` (diff), `tests_seguridad_transferencia.py`.
Standard: PCI-DSS SAQ-A (el sistema no toca PAN; todo PAN queda en Stripe Elements, `payment_method_types=['card']`, `views.py:672`); controles de corrección de dinero de la norma del repositorio (`backend/CLAUDE.md` «Garantias del cobro» y «Panel de finanzas»): idempotencia, webhook como única fuente de verdad, sin doble cobro, reconciliación.
Fecha: 2026-10-26. Modo: solo lectura (no se corrió la suite ni el servidor; ningún hallazgo se reprodujo por ejecución, todos son por lectura de código con la secuencia exacta).
Auditorías previas leídas: `docs/security/CSO-notificaciones-backoffice.md`, `docs/security/CSO-2-backoffice.md`. No se repiten sus Bajos B-1 a B-6; se amplía su M-1.

## Alcance
Dinero tocado hoy: marcar pagada por transferencia, `_resolver_cobro_repetido`, avisos en la ruta de reembolso/cancelación, `crear-pago` frente a la transferencia, acciones de admin que mueven dinero. Fuera de alcance: PCI de captura de tarjeta (no hay PAN en el sistema), `conciliar_pagos` más allá de confirmar que solo toma `pendiente_pago`, disputas (`aplicar_disputa`), frontend.

## Veredicto en una frase
BLOCKED: el cambio de `_resolver_cobro_repetido` convierte un cobro con tarjeta posterior a una transferencia en un reembolso duplicado cuyo evento `charge.refunded` cancela solo la reserva ya pagada y libera su cupo (A-1), y `crear-pago` sigue sin revalidar estado bajo candado (M-1).

---

## Hallazgos

### [Alto] A-1 El reembolso automático del «cobro duplicado» dispara `aplicar_reembolso`, que cancela la reserva pagada por transferencia y libera cupo, panga y capitán
- **Introducido por**: el cambio de `services.py:214` (`and reserva.monto_pagado`, en 31391e04). Antes, un cobro con el mismo intent devolvía `YA_APLICADO` (doble cobro silencioso, sin cancelar nada).
- **Mecanismo** (secuencia exacta):
  1. La reserva queda `pagada` con `stripe_payment_intent_id = pi_X` y `monto_pagado` vacío. Eso ocurre siempre que el intent no se anula: (a) la vendedora registra la transferencia por el formulario general de la reserva (`estado=pagada` + `monto_transferencia`, `admin.py:905-955`), que NO llama a `_cerrar_cobro_con_tarjeta`; (b) la carrera de M-1 deja un intent nuevo escrito sobre la reserva ya saldada (`views.py:518`).
  2. El cliente completa la tarjeta de `pi_X`. Llega `payment_intent.succeeded` → `_resolver_cobro_repetido`: mismo id pero `monto_pagado` falso → `reembolsar(intent, 'cobro duplicado')` (`services.py:222-226`), reembolso total.
  3. Stripe emite `charge.refunded` (`refunded=true`) para ese cargo. `aplicar_reembolso` → `_reserva_del_cargo` busca por `stripe_payment_intent_id == pi_X` y encuentra la reserva de la transferencia (`services.py:430-446,479`). No existe ningún chequeo de que esa reserva haya cobrado ese cargo: `_es_reembolso_total` devuelve True por `refunded is True` (`services.py:562-563`), y como el estado es `pagada` (en `ESTADOS_QUE_SE_CANCELAN_AL_REEMBOLSAR`, `services.py:458`) hace `estado=CANCELADA`, `reembolsada=True`, `monto_reembolsado=<monto de la tarjeta>` y `reserva.save()` completo (`services.py:499-526`), que libera ocupaciones, componentes y viajes.
- **Consecuencia**: un cliente que pagó por transferencia (dinero ya en el banco, `monto_transferencia` intacto) queda con la reserva cancelada con el motivo «Reembolso completo hecho desde el panel de Stripe», su lugar vuelve a venderse y el aviso de asignación deja de salir. Finanzas registra una salida de tarjeta (`monto_reembolsado`, `MovimientoDinero`) sin entrada de tarjeta (`monto_pagado` vacío), así que «En la cuenta» de Stripe queda negativo por esa cantidad. Nadie recibe alerta: solo la notificación de «Reembolso total registrado» (AVISO) que, además, contradice lo que pasó.
- **Probabilidad**: la vía (a) es el camino que el dueño usaba antes del botón (memoria `pendiente-marcar-pagada-por-transferencia`: «hoy se hace a mano en Reservas») y sigue disponible hoy: `estado` y `monto_transferencia` son editables en el formulario (`admin.py:890`). Requiere que el cliente complete la tarjeta después; es exactamente el caso de uso que motivó el botón.
- **Repro** (no ejecutado; el patrón de `tests_seguridad_transferencia.py:107-119` ya cubre el paso 2):
  1. `reserva = pendiente(empresa, stripe_payment_intent_id='pi_X')`.
  2. `Reserva.objects.filter(pk=reserva.pk).update(estado='pagada', monto_transferencia=Decimal('1000'))` (equivale al formulario general).
  3. `aplicar_pago_exitoso({'id':'pi_X','amount_received':100000,'metadata':{'reserva_id':str(reserva.pk)}}, empresa)` con `reembolsar` mockeado a True → `DUPLICADO_REEMBOLSADO`.
  4. `aplicar_reembolso({'id':'ch_1','payment_intent':'pi_X','refunded':True,'amount_refunded':100000}, empresa)`.
  5. Esperado hoy (defecto): `reserva.estado == 'cancelada'`, `reembolsada == True`. Esperado correcto: sin cambio de estado.
- **Arreglo** (`services.py`, en `aplicar_reembolso`, justo después del bloque `PENDIENTE_PAGO`, línea ~492):
  ```python
  if not reserva.monto_pagado:
      # Esta reserva no cobró nada con tarjeta (la saldó una transferencia o una venta manual): un reembolso de
      # tarjeta sobre su intent es el del cobro duplicado que ya devolvimos, no una devolución de ESTA reserva.
      logger.warning('Reembolso del cargo %s sobre la reserva %s que no cobró con tarjeta; no se registra.',
                     charge['id'], reserva.pk)
      return None
  ```
  Equivalente para `aplicar_disputa` (una disputa sobre ese cargo duplicado marca `en_disputa` en una reserva que no cobró ese cargo; informativo, no cancela nada). Agregar la prueba del repro como `test_el_reembolso_del_cobro_duplicado_no_cancela_la_reserva_de_transferencia`. Orden compuesta: el guard no cambia nada, porque una reserva de orden revertida ya trae `monto_reembolsado` y el evento sale antes por `devuelto <= monto_reembolsado` (`services.py:495`).
- **Triage escéptico** (3 rondas): R1 alcanzable por evento firmado de Stripe tras acción de cliente (VALID). R2 búsqueda de defensa en `aplicar_reembolso`/`_reserva_del_cargo`/`_es_reembolso_total`: ninguna compara contra `monto_pagado` cuando `refunded=true` (`services.py:562-563` retorna antes de mirar `reserva.monto_pagado`) (VALID). R3 orden de eventos: el reembolso se emite después de `succeeded`, con la reserva ya `pagada` (VALID). Confianza 100 %.

### [Medio] M-1 (confirma y precisa CSO-2 M-1) `crear-pago` escribe un intent nuevo sobre una reserva ya saldada: no hay candado ni revalidación de estado entre A y la escritura final
- **Preexistente en `crear-pago`; alcanzable por la transferencia (31391e04); su daño se amplifica con A-1.**
- **Precisión sobre el reporte anterior**: el bloque C no usa una instancia vieja; hace `reserva.refresh_from_db()` en `views.py:474`, pero sin candado y sin mirar `estado`. El hueco real va de la lectura del bloque A (`views.py:101,112`, única comprobación de `PENDIENTE_PAGO`) hasta la escritura de `views.py:507-524`, e incluye las llamadas a Stripe de B/C (`_intent_de`: `retrieve`/`create`/`update`, `views.py:645-683`).
- **Mecanismo**: (i) reserva sin intent guardado: la transferencia no tiene nada que anular (`transferencia.py:64-65`), `crear-pago` termina `create` y escribe `stripe_payment_intent_id`, `precio_total`, `iva_*` y `forma_pago` (`update_fields`, `views.py:521-524`) sobre una reserva `pagada`, devolviendo un `client_secret` vivo. (ii) Reserva con intent guardado y monto distinto (cambió una promo o extras): el intent guardado ya está `canceled` (no reutilizable, `views.py:57`), se crea otro con otra llave de idempotencia (`views.py:675`) y pasa lo mismo. Si el monto es igual, la llave `reserva-{pk}-{moneda}-{centavos}` repite la respuesta cacheada del intent original ya anulado (inocuo).
- **Consecuencia**: el cobro posterior se reembolsa (A-1 corrige que eso no cancele la reserva) pero el cliente ve cargo + reembolso y la comisión de Stripe no se devuelve; `precio_total`/`iva_monto`/`forma_pago` de la reserva saldada quedan reescritos, y con ellos `saldo_pendiente`.
- **Repro**: dos hilos en Postgres: hilo 1 `POST crear-pago` con un `time.sleep` dentro de `_intent_de` (mock de `payment_intents.create`); hilo 2 `marcar_pagada_por_transferencia` completo; liberar hilo 1. Esperado hoy (defecto): `reserva.stripe_payment_intent_id == intent.id` y `estado == 'pagada'`.
- **Arreglo mínimo** (`views.py`, reemplazar el bloque `with transaction.atomic():` de 507-524 por):
  ```python
  with transaction.atomic():
      bloqueada = Reserva.objects.select_for_update().get(pk=reserva.pk)
      if bloqueada.estado != Reserva.Estado.PENDIENTE_PAGO:
          perdio_la_carrera = True          # transferencia o webhook ganaron
      else:
          perdio_la_carrera = False
          reserva = bloqueada               # escribir sobre la fila bloqueada
          ... (detalle_a_congelar, congelar_personalizaciones y los 7 campos igual que hoy)
  if perdio_la_carrera:
      try:  # fuera del candado: es una llamada de red
          cliente.payment_intents.cancel(
              intent.id, options={'idempotency_key': f'crearpago-{reserva.pk}-{intent.id}-huerfano'})
      except stripe.StripeError:
          logger.exception('No se pudo anular el intent %s huerfano de la reserva %s', intent.id, reserva.pk)
      return Response({'detail': 'Esta reserva ya no esta pendiente de pago.', 'codigo': 'ya_no_pendiente'}, status=409)
  ```
  (Si `intent.id` ya es el cobrado, Stripe rechaza el `cancel`; se registra y el 409 igual protege el cliente.) Prueba de concurrencia solo en Postgres (`tests_carreras.py`).

### [Medio] M-2 El formulario general de la reserva saldar una `pendiente_pago` sin anular el PaymentIntent vivo
- **Preexistente**; antes de hoy no había defensa en ningún camino. Hoy solo el botón la tiene.
- **Mecanismo**: `ReservaAdmin.save_model` acepta `estado=pagada` + `monto_transferencia` (`admin.py:905-955`) y ejecuta `reservar_cupo_al_confirmar` (`_entra_a_ocupar_cupo`, `admin.py:971-976`), sin pasar por `transferencia._cerrar_cobro_con_tarjeta`. `stripe_payment_intent_id` es de solo lectura únicamente para la vendedora (`admin.py:899-902`), no impide el cambio de estado.
- **Consecuencia**: el intent sigue cobrable; si el cliente paga, A-1 (cancelación automática de la reserva) en vez de un cobro duplicado silencioso.
- **Arreglo**: extraer `_cerrar_cobro_con_tarjeta` a una función pública (`transferencia.cerrar_cobro_con_tarjeta`) y llamarla desde `save_model` cuando `getattr(obj, '_estado_original', None) == PENDIENTE_PAGO` y `obj.estado in ESTADOS_QUE_OCUPAN_CUPO` y `obj.stripe_payment_intent_id`, capturando `ErrorDeTransferencia` → `CupoAgotadoAlGuardar`-style (aviso, sin 500). Alternativa de menor costo: quitar `pagada` de las opciones de `estado` en el formulario de una `pendiente_pago` con intent y dejar solo el botón.

### [Medio] M-3 Si el reembolso del cobro duplicado falla, no hay alerta urgente: solo una línea de log, y el webhook responde 200
- **Preexistente en `_resolver_cobro_repetido` (`services.py:222-226`); ahora alcanzable por más caminos** (la nueva condición reclasifica como duplicado un pago que antes se ignoraba).
- **Mecanismo**: `reembolsar` devuelve False ante `StripeError` (`services.py:621-623`) y el resultado `FALLO_REEMBOLSO` se descarta; `_gestionar_fallo_reembolso` (alerta + notificación una sola vez) solo se invoca desde `_cancelar_sin_cupo` y `_cancelar_codigo_promocional_invalido` (`services.py:373,411`). El webhook traga todo y responde 200 (`views.py:896-899`), así que Stripe no reintenta.
- **Consecuencia**: cliente con dos cobros (tarjeta + transferencia) sin que nadie lo sepa, hasta que alguien lea el log.
- **Arreglo** (`services.py`, rama de `_resolver_cobro_repetido`): cuando `reembolsar(...)` es False, llamar `_gestionar_fallo_reembolso(reserva, intent, empresa, motivo='Cobro duplicado: no se pudo devolver el segundo cargo')`. Hacerlo SOLO junto con el cambio de B-6 (si no, B-6 generaría alertas falsas).

### [Bajo] B-1 `monto` enorme en la pantalla de transferencia da 500 por `decimal.InvalidOperation`
- Location: `transferencia.py:53`. El `try` de 47-50 cubre solo `Decimal(...)`; `valor.quantize(Decimal('0.01'))` lanza `InvalidOperation` si el resultado necesita más de 28 dígitos (por ejemplo `1e30`). `pagar_transferencia_view` solo atrapa `ErrorDeTransferencia` (`admin.py:1470`).
- Consecuencia: 500 para un usuario autenticado; antes de abrir la transacción, sin efecto en el dinero.
- Arreglo: mover `quantize` dentro del `try` y capturar `InvalidOperation`.

### [Bajo] B-2 La llave de idempotencia de la anulación no incluye el id del intent
- Location: `transferencia.py:76` (`f'transferencia-{reserva.pk}-cancel'`).
- Mecanismo: si un primer intento anuló el intent A y el COMMIT externo falló (la reserva sigue `pendiente_pago`), y luego existe un intent B para la misma reserva, el segundo intento llama `cancel` con la misma llave y otra ruta; Stripe responde `idempotency_error` (subclase de `StripeError`) y la transferencia se rechaza durante 24 h sin salida en la interfaz (falla cerrada, sin pérdida de dinero).
- Arreglo: `f'transferencia-{reserva.pk}-{intent.id}-cancel'`.

### [Bajo] B-3 Tras un fallo de COMMIT posterior a la anulación, el cliente queda con un intent muerto durante 24 h
- Location: `transferencia.py:128` + `views.py:645-679`.
- Mecanismo: la anulación en Stripe es lo único irreversible; si el COMMIT final falla, la reserva queda `pendiente_pago` con el intent `canceled`. `_intent_de` lo descarta (no está en `INTENT_REUTILIZABLE`) y vuelve a crear con la llave `reserva-{pk}-{moneda}-{centavos}`; con el mismo monto Stripe repite el intent original (anulado, con `status` histórico `requires_payment_method`, que `views.py:677` no filtra), y la tarjeta falla al confirmar. Sin dinero perdido; la vendedora puede repetir la transferencia (el `retrieve` ve `canceled` y no vuelve a cancelar).
- Arreglo: en `_intent_de`, si el intent guardado existe y está `canceled`, incluir su id en la llave: `f'reserva-{reserva.pk}-{moneda}-{centavos}-{intent_previo.id}'`.

### [Bajo] B-4 `monto` vacío en el POST se interpreta como «el total»
- Location: `admin.py:1466` (`request.POST.get('monto') or f'{sugerido:.2f}'`). El HTML tiene `required`, pero el servidor no: un POST directo o un cliente sin validación registra el total completo en el banco sin que nadie lo haya escrito.
- Arreglo: aplicar el valor por defecto solo cuando `request.method == 'GET'`; en POST, un monto vacío es el error «El monto no es un número válido».

### [Bajo] B-5 Evento repetido de un pago ya revertido en una orden cruza-empresa produce un segundo intento de reembolso y un `logger.exception` falso
- Location: `services.py:125,142-143,214` y `ordenes.py:239-256`.
- Mecanismo: cuando falta cupo en un componente de orden, `monto_pagado` se asigna solo en memoria (`services.py:125`); `_cancelar_orden_sin_cupo` → `revertir_orden` carga la fila de nuevo y guarda `monto_reembolsado` pero no `monto_pagado`. Una segunda entrega del mismo `payment_intent.succeeded` (Stripe garantiza al menos una) ya no entra por «mismo intent y `monto_pagado`», sino por duplicado: `reembolsar` con otra llave (`refund-{pi}` en vez de `orden-…-refund`) sobre un cargo ya devuelto → Stripe lo rechaza → `FALLO_REEMBOLSO` y traza de error. Sin pérdida de dinero (Stripe no permite sobre-reembolso).
- Arreglo: `if reserva.stripe_payment_intent_id == intent['id'] and (reserva.monto_pagado or reserva.monto_reembolsado):`. Esta condición no cubre el caso de transferencia (su `monto_reembolsado` está vacío) ni el de una reserva cancelada por mal clima sin dinero (se reembolsa, deseado).

---

## Verificado sin hallazgo (con evidencia)

**1. `marcar_pagada_por_transferencia` — doble cobro**
- Tarjeta ya cobrada o en curso: `retrieve` bajo candado; `succeeded`/`processing`/`requires_capture` rechazan (`transferencia.py:56,70-73`). El webhook concurrente y esta función se serializan por `select_for_update` (`transferencia.py:93`, `services.py:107`): quien llega segundo ve `pagada` y sale por `YA_APLICADO`/`puede_marcarse_pagada` (`transferencia.py:35-38`).
- Carrera `retrieve`→`cancel` (el cliente confirma en medio): el `cancel` falla con `InvalidRequestError` distinto de `resource_missing` y se rechaza (`77-79`).
- Estados no contemplados: `requires_confirmation`, `requires_action` (3DS en curso; el cliente pierde la autenticación al anularse) y `requires_payment_method` se anulan (`57,74-76`); `canceled` se omite sin error; con `payment_method_types=['card']` (`views.py:672`, `ordenes.py:96`) no hay métodos asíncronos (OXXO/SPEI) que dejen un cobro en vuelo tras `requires_action`.
- `resource_missing` (intent de otra cuenta tras rotar llaves) no estorba y coincide con `CrearPagoView._recuperar_intent` (`views.py:626-628`). `StripeClient.payment_intents.cancel(id, options=…)` es la firma correcta de `stripe==15.x` y la misma convención de `ordenes.py:224-227`.
- Idempotencia: doble clic cubierto (`tests_transferencia.py:78`) y por el candado; la llave del `cancel` repite la misma respuesta.
- Orden del irreversible: `_cerrar_cobro_con_tarjeta` es lo último (`transferencia.py:128`); cupo, validación, integridad y guardado fallan antes y dejan el intent vivo. Un fallo de Stripe levanta dentro del `atomic` y deshace todo. Lo único que sobrevive a un rollback posterior es la anulación (B-2, B-3: sin pérdida de dinero).

**2. `marcar_pagada_por_transferencia` — Finanzas, moneda, monto, IVA**
- `monto_pagado` no se toca: solo `monto_transferencia`, sello (`transferencia_registrada_en/por`) y `pagada_en` (`transferencia.py:106-111`). Finanzas lee tarjeta de `monto_pagado`/`pagada_en` (`finance/services.py:38`), así que el movimiento no aparece como tarjeta; `pagada_en` solo lo usa además el sondeo de avisos (`avisos.py:66`).
- `MovimientoDinero`: `_usuario_dinero` fijado, `Reserva.save()` escribe una fila con `fecha = transferencia_registrada_en` (`models.py:788-843`); la foto `_dinero_original` viene de `from_db` por el `select_for_update`. Una sola fila, sin duplicado.
- Moneda: el monto se interpreta en `reserva.moneda` (la pantalla lo rotula en `pagar_transferencia.html`); no se mezcla con otra. IVA: `precio_total` incluye IVA (`CrearPagoView` `con_iva`, `views.py:188`); el tope `monto > precio_total` (`transferencia.py:103`) y el sugerido (`monto_sugerido`) están en la misma base. Monto parcial: se acepta, `saldo_pendiente` descuenta la transferencia (`models.py:1168-1169`) y la liquidación en efectivo toma el resto (`cobros.py:saldo_liquidable`). Un monto parcial deja `forma_pago` en el valor del último `crear-pago` (informativo: «Cobro» puede marcar descuadre; sin impacto en dinero).
- `precio_total is None` y `monto <= 0`, `NaN`, `Infinity` rechazados (`46-53,99-102`), salvo B-1.
- `on_commit` (`_avisar_al_cliente`): corre tras el COMMIT; `notificar_reserva_pagada` y `registrar_notificacion` no lanzan; nada de ahí puede alterar el dinero ya confirmado.

**3. `services.py` — avisos y `_resolver_cobro_repetido`**
- `_notificar_reserva_nueva` y `_registrar_cancelacion_sin_cupo` arman argumentos fuera del `try` de `registrar_notificacion` (clase B-1 de CSO-2). Intenté el caso real de orden cruza-empresa: la reserva no líder se crea con `paquete=None` (`views.py:1150`), así que `_producto_de` usa su propio `servicio` bajo el RLS de su empresa; la líder usa su propio `paquete`. No encontré mecanismo que lance hoy; sigue siendo Bajo por defensa en profundidad (envolver `_producto_de` y el f-string en `try/except Exception`).
- `_registrar_cancelacion_sin_cupo` corre DESPUÉS de `reembolsar()` y de `reserva.save()` (`services.py:372-386`): no puede condicionar el reembolso; un fallo lo revertiría junto con el `save()` pero no el reembolso ya emitido (mismo riesgo B-1).
- `registrar_notificacion` no hace `on_commit`, escribe en savepoint propio y atrapa `Exception` (`notificaciones.py:62-76`); no puede dejar abortada la transacción del webhook.
- Webhook repetido de un pago ya aplicado: `monto_pagado = amount_received/100` (`services.py:125`) es verdadero → `YA_APLICADO`, sin reembolso (`tests_seguridad_transferencia.py:121`). `_cancelar_sin_cupo` y `_cancelar_codigo_promocional_invalido` guardan `monto_pagado` con un `save()` completo → también `YA_APLICADO` en la repetición.
- Reservas «anteriores a la columna»: `monto_pagado` existe desde la migración `0004`, antes del lanzamiento (2026-10-22) y sin ventas reales; no hay reserva pagada por Stripe con `monto_pagado` vacío.
- Pago de monto cero: Stripe no permite `succeeded` con `amount_received = 0` (mínimo del PSP); no alcanzable.
- Reserva `cancelada` por «mal clima» mientras estaba `pendiente_pago` (acción incluye pendientes) y el cliente paga después: antes `YA_APLICADO` (cobro retenido y viaje cancelado); ahora se reembolsa. Es una mejora real del cambio.
- `aplicar_reembolso`: `registrar_notificacion` va tras `reserva.save()` y los `return`/guardas; `devuelto:.2f` opera sobre `Decimal`. No altera la lógica del dinero.

**4. Admin**
- `pagar_transferencia_view`: login/staff por `admin_site.admin_view`; `has_change_permission(request, reserva)` (`admin.py:1451`); `get_object` pasa por el queryset con alcance de empresa (404 fuera de ella); `{% csrf_token %}` en el formulario y `CsrfViewMiddleware` activo; GET solo muestra la confirmación y no muta nada; la acción de fila de checkouts abandonados es un `HttpResponseRedirect` a esa misma pantalla (`admin.py:1863-1867`) con permiso `change_reserva`.
- Doble clic: el segundo POST espera el candado y recibe «ya no está esperando el pago» (sin duplicar dinero).
- `avisar()` se llama después de mutar y fuera de la transacción de mutación en cancelación por mal clima (`admin.py:1712-1743`) y en cobro en efectivo (`1802-1834`); en `pagar_transferencia_view`, `message_user` va después de `marcar_pagada…` y `log_change`. `avisar` no lanza (CLAUDE.md) y `_avisar_por_empresa` solo agrupa e inserta. Un fallo del armado de `texto_de` revertiría la petición entera (consistente, no un estado a medias).
- Efectivo: `liquidar_saldo_en_efectivo` recalcula con `select_for_update` y `save(update_fields=…)` (`cobros.py:45-58`); no cambió hoy.

**5. `signals.py` / `cobros.py`**: el diff de `signals.py` (22026a87..HEAD) solo añade `_dejar_constancia`, `_anotar_resultado` y el actor; no toca `monto_*`, estado ni cupo. `cobros.py` sin cambios. Nada de lo nuevo toca montos.

**6. SAQ-A**: ninguna ruta revisada recibe, guarda ni registra PAN; la transferencia no maneja datos de tarjeta. Las notificaciones del feed no guardan correo ni teléfono del cliente (según `CLAUDE.md`, verificado por la auditoría previa).

---

## Brechas de prueba que recomiendo cerrar junto con los arreglos
- `charge.refunded` del cargo duplicado sobre una reserva pagada por transferencia (A-1).
- `crear-pago` concurrente con la transferencia en Postgres (M-1), en `tests_carreras.py`.
- Saldar por el formulario general una `pendiente_pago` con intent vivo (M-2).
- `FALLO_REEMBOLSO` del duplicado deja la alerta urgente (M-3).
- Segunda entrega de `succeeded` tras `_cancelar_orden_sin_cupo` (B-5).

## No cubierto
- No se ejecutó nada (suite, servidor, Stripe en modo prueba): todos los hallazgos son por lectura con la secuencia de eventos descrita.
- `aplicar_disputa` y `conciliar_pagos` (solo se confirmó que `conciliar_pagos` toma reservas `pendiente_pago`).
- Cuerpo completo de `ReservaAdmin.get_form`/permisos de cada campo (solo `get_readonly_fields` y `fieldsets`); no verifiqué si algún rol puede quitar `estado` del formulario.
- Comportamiento real de Stripe ante el reintento de `cancel` con la misma llave de idempotencia y ruta distinta (B-2 se razona por la documentación de idempotencia de Stripe).
- Separación de funciones: cualquier vendedora con `change_reserva` puede registrar una transferencia sin un segundo control; las únicas trazas son `log_change`, `MovimientoDinero.registrado_por` y la notificación. Es una decisión de negocio, no un defecto de código.
- No se crearon beads para A-1 ni M-1 (modo solo lectura): el orquestador debe abrirlos (`bd create "[High] …" --label finding`) y no registré el veredicto con `log-verdict.sh` por la misma razón.

## Orden de arreglo sugerido
1. A-1 (guard `monto_pagado` en `aplicar_reembolso`; 6 líneas + una prueba).
2. M-1 (revalidar bajo candado en el bloque C) y M-2 (anular el intent también por el formulario general).
3. M-3 junto con B-5.
4. B-1, B-2, B-3, B-4.

VERDICT: BLOCKED reason="un cobro con tarjeta posterior a una transferencia se reembolsa como duplicado y su charge.refunded cancela automáticamente la reserva ya pagada (A-1), sin remediación en el backlog"
