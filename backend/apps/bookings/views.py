import uuid
from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tenancy import scope

from .models import (
    ESTADOS_QUE_OCUPAN_CUPO,
    MAX_PERSONAS,
    MIN_PERSONAS,
    Reserva,
    cupo_maximo_del_dia,
    disponibilidad_por_fecha,
    evaluar_cupo,
    proxima_fecha_disponible,
)
from .captcha import verificar_turnstile
from .serializers import CupoSerializer, ReservaCheckoutSerializer, ip_del_cliente


class CupoDisponibleView(APIView):
    """Cupo restante para una fecha y un tamano de grupo, para que el checkout
    avise antes de pagar (la validacion real y definitiva ocurre al confirmar el
    pago, ver apps/payments).

    La Empresa se resuelve por el slug de la URL: 404 si no existe o si esta
    pausada (`activo=False`) — es dinero por cobrar, no debe vender."""

    throttle_scope = 'consulta'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            fecha = request.query_params.get('fecha')
            if not fecha:
                return Response({'detail': 'Falta el parametro fecha.'}, status=400)

            try:
                fecha = date.fromisoformat(fecha)
            except ValueError:
                return Response({'detail': 'fecha debe tener el formato YYYY-MM-DD.'}, status=400)

            # Opcional con default 1 a proposito: una peticion sin `personas` tiene que
            # responder lo mismo que antes de que el cupo supiera de tamanos.
            try:
                personas = int(request.query_params.get('personas', MIN_PERSONAS))
            except (TypeError, ValueError):
                return Response({'detail': 'personas debe ser un numero entero.'}, status=400)
            if not (MIN_PERSONAS <= personas <= MAX_PERSONAS):
                return Response(
                    {'detail': f'personas debe estar entre {MIN_PERSONAS} y {MAX_PERSONAS}.'},
                    status=400,
                )

            motivo = evaluar_cupo(fecha, personas, empresa)
            data = {
                'fecha': fecha,
                'cupo_maximo': cupo_maximo_del_dia(fecha, empresa),
                'ocupadas': Reserva.objects.filter(
                    fecha=fecha, estado__in=ESTADOS_QUE_OCUPAN_CUPO, empresa=empresa,
                ).count(),
                'disponible': motivo is None,
                # Se responde siempre, tambien cuando el dia pedido si tiene espacio:
                # asi el navegador nunca necesita una segunda vuelta.
                'proxima_disponible': proxima_fecha_disponible(fecha, personas, empresa),
                'motivo_no_disponible': motivo,
            }
            return Response(CupoSerializer(data).data)


# Tope de dias que puede pedir /api/<empresa>/cupo/rango/ de un golpe. Dos meses
# cubren de sobra lo que un calendario pinta a la vez (el del hero muestra un mes,
# el del checkout una semana) y dejan margen para precargar el mes siguiente.
# Existe para que una sola peticion no pueda pedir diez anios y barrer la tabla de
# reservas: la ruta es publica y sin autenticacion.
MAX_DIAS_RANGO = 62


class CupoRangoView(APIView):
    """Disponibilidad de cada dia de un rango, para pintar el calendario.

    Existe para que el cliente vea los dias llenos **antes** de tocar uno. Antes
    solo se podia preguntar dia por dia (`cupo`), y un mes son 30 peticiones
    contra un limite de 60/min: el segundo mes devuelve 429.

    Responde `{'dias': {'2026-09-07': None, '2026-09-08': 'lleno', ...}}`, donde
    None significa que si cabe. Es informativo, igual que `cupo`: la validacion
    que manda ocurre al confirmar el pago.
    """

    throttle_scope = 'consulta'

    def get(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            fechas = {}
            for nombre in ('desde', 'hasta'):
                crudo = request.query_params.get(nombre)
                if not crudo:
                    return Response({'detail': f'Falta el parametro {nombre}.'}, status=400)
                try:
                    fechas[nombre] = date.fromisoformat(crudo)
                except ValueError:
                    return Response(
                        {'detail': f'{nombre} debe tener el formato YYYY-MM-DD.'}, status=400
                    )

            desde, hasta = fechas['desde'], fechas['hasta']
            if hasta < desde:
                return Response({'detail': 'hasta no puede ser anterior a desde.'}, status=400)
            if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
                return Response(
                    {'detail': f'El rango no puede pasar de {MAX_DIAS_RANGO} dias.'}, status=400
                )

            # Mismo default y mismos limites que `cupo`: las dos rutas contestan
            # sobre el mismo grupo y no pueden discrepar en que es un grupo valido.
            try:
                personas = int(request.query_params.get('personas', MIN_PERSONAS))
            except (TypeError, ValueError):
                return Response({'detail': 'personas debe ser un numero entero.'}, status=400)
            if not (MIN_PERSONAS <= personas <= MAX_PERSONAS):
                return Response(
                    {'detail': f'personas debe estar entre {MIN_PERSONAS} y {MAX_PERSONAS}.'},
                    status=400,
                )

            return Response({
                'dias': {
                    fecha.isoformat(): motivo
                    for fecha, motivo in disponibilidad_por_fecha(desde, hasta, personas, empresa).items()
                }
            })


class ReservaCheckoutView(APIView):
    """Guarda la reserva de una sesion de checkout, en estado pendiente_pago.

    No ocupa cupo todavia (ver ESTADOS_QUE_OCUPAN_CUPO) — el cupo se valida al
    confirmar el pago, ver apps/payments/views.py.

    Es un upsert por `checkout_id`: el navegador manda el mismo identificador
    durante toda la sesion, asi que reintentar tras un error o corregir la fecha
    reescribe la misma fila en vez de dejar reservas abandonadas duplicadas. La
    Empresa la fija el slug de la URL, nunca el payload del cliente.
    """

    throttle_scope = 'reservas'

    def post(self, request, empresa_slug):
        empresa = scope.resolver_empresa_publica(empresa_slug)
        with scope.con_empresa(empresa):
            existente = self._pendiente_de(empresa, request.data.get('checkout_id'))

            # El captcha se cobra solo al CREAR, no al corregir. El token de
            # Turnstile es de un solo uso y este endpoint es un upsert: el checkout
            # reenvia la misma reserva cada vez que el cliente cambia la fecha o
            # reintenta tras un error, asi que pedirlo siempre romperia el checkout
            # al segundo cambio. Cobrarlo al crear deja el costo donde importa — un
            # bot paga un captcha por cada reserva nueva que quiera meter.
            if existente is None and not verificar_turnstile(
                request.data.get('captcha_token'), ip_del_cliente(request)
            ):
                return Response(
                    {'captcha': 'No pudimos verificar que eres una persona. Recarga e intenta de nuevo.'},
                    status=403,
                )

            serializer = ReservaCheckoutSerializer(
                existente, data=request.data, context={'request': request, 'empresa': empresa},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=200 if existente else 201)

    @staticmethod
    def _pendiente_de(empresa, checkout_id):
        """La reserva sin pagar de este checkout, si la hay.

        El valor llega crudo del request: esta busqueda es la que decide que
        instancia recibe el serializer, asi que corre **antes** de que el
        serializer valide nada. Metido directo al filtro de un `UUIDField`, uno
        mal formado revienta con `ValidationError` (o `AttributeError`, si no es
        ni texto) y esta ruta — publica y sin autenticacion — contesta 500.

        Aqui solo se decide si hay algo que buscar. Si no es un UUID no se busca:
        el 400 lo da el serializer, que es a quien le toca. El filtro por
        `empresa` es lo unico que impide que un POST a la ruta de otra Empresa
        con un `checkout_id` que coincide reescriba una reserva ajena (sin RLS,
        en sqlite/tests, nada mas lo evita).
        """
        try:
            uuid.UUID(str(checkout_id))
        except (ValueError, TypeError):
            return None

        return Reserva.objects.filter(
            checkout_id=checkout_id, estado=Reserva.Estado.PENDIENTE_PAGO, empresa=empresa,
        ).first()
