# Tarea 02: endpoints públicos de cupo cuentan el apartado y excluyen el propio por cabecera

Lee del spec: §4.2, el párrafo de los endpoints públicos y la consecuencia asumida.

## Qué hacer
1. `obtener_contexto_rango`, `disponibilidad_por_fecha` y `proxima_fecha_disponible` (busca en `backend/apps/bookings/cupo/adaptador.py` y `bookings/models.py`) no tienen `excluir_pk`: agrégalo (opcional, por defecto `None`) y haz que sumen la demanda apartada vigente (reutiliza `cupo/apartado.py` de la tarea 01) excluyendo esa reserva. Las consultas del rango deben seguir siendo pocas: carga los retratos vigentes de la empresa y el rango en UNA consulta, sin trabajo por reserva.
2. Las vistas públicas `/api/cupo/` y `/api/cupo/rango/` (`backend/apps/bookings/views.py`) leen la cabecera `X-Checkout-Id` (en Django: `request.META['HTTP_X_CHECKOUT_ID']`); si coincide con el `checkout_id` de una reserva `pendiente_pago` con apartado vigente DE LA EMPRESA de la petición, pasan su pk como `excluir_pk`. Una cabecera inválida, inexistente o de otra empresa se ignora sin error. La cifra `ocupadas` de `/api/cupo/` también cuenta los apartados vigentes.
3. CORS: agrega `x-checkout-id` a las cabeceras permitidas (`CORS_ALLOW_HEADERS`, extendiendo `corsheaders.defaults.default_headers`) en `backend/config/settings/base.py` o donde se configure; verifica dónde está CORS y respeta cómo lo leen `local.py`/`production.py`.

## Pruebas (archivo nuevo `backend/apps/bookings/tests_apartado_endpoints.py`)
Sin cabecera, un apartado vigente ajeno hace que el día salga lleno; con la cabecera del propio `checkout_id` el día sale disponible; cabecera de otra empresa o inexistente se ignora; el rango y `proxima_fecha_disponible` cuentan los apartados; `ocupadas` los suma; con `APARTADO_MINUTOS=0` todo queda como antes.
