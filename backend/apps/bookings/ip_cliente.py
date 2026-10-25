"""IP real de quien llama a la API, detras de Render y Cloudflare.

`X-Forwarded-For` es una lista `cliente, proxy1, proxy2...`: cada salto agrega al final la IP de quien le
hablo, y lo que va a la izquierda de la primera IP que agrego un proxy nuestro lo puede escribir el
propio cliente. Contar "N saltos desde la derecha" exige saber cuantos proxies hay, y no los habia
contado bien: en produccion la IP guardada en el deslinde de una reserva de prueba empezaba con 172
(un nodo de Cloudflare) en vez de la del cliente. Con una IP compartida el limite de peticiones bloquearia
a varias personas juntas y la constancia legal del deslinde quedaria con una IP que no es de quien firma.

La regla ahora no depende del numero de saltos: se recorre la lista de derecha a izquierda, se saltan las
direcciones que son de NUESTROS proxies (Cloudflare y redes privadas) y la primera que no lo es es la IP
que se conecto a ellos. Un cliente no puede falsificarla: lo que escriba va a la izquierda de esa.

Sin proxy de confianza (`TRUSTED_PROXY_COUNT=0`, local y pruebas) no se le cree al header y se usa la IP
de la conexion. Si algun dia Cloudflare publica un rango nuevo y no esta aqui, esa IP se tomaria por la del
cliente (el limite volveria a agrupar usuarios, no es una brecha): se agrega en
`TRUSTED_PROXY_EXTRA_RANGES` (CSV de redes) sin tocar codigo. Lista oficial: https://www.cloudflare.com/ips/
"""
import ipaddress

from django.conf import settings
from rest_framework.throttling import ScopedRateThrottle

# Redes de Cloudflare (https://www.cloudflare.com/ips-v4 e ips-v6).
_CLOUDFLARE = (
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18',
    '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22', '198.41.128.0/17',
    '162.158.0.0/15', '104.16.0.0/13', '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
    '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32', '2405:8100::/32',
    '2a06:98c0::/29', '2c0f:f248::/32',
)
# Redes internas: el balanceador de Render y compania. Explicitas, no `is_private`, porque esa propiedad
# tambien cubre los rangos de documentacion (203.0.113.0/24...) que las pruebas usan como "IP publica".
_INTERNAS = (
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16',
    'fc00::/7', 'fe80::/10', '::1/128',
)


def _redes_de_confianza():
    extra = [r.strip() for r in (getattr(settings, 'TRUSTED_PROXY_EXTRA_RANGES', '') or '').split(',') if r.strip()]
    return [ipaddress.ip_network(red) for red in (*_CLOUDFLARE, *_INTERNAS, *extra)]


_REDES = None


def es_de_proxy(ip):
    """True si `ip` es de un proxy nuestro (Cloudflare o red interna). Lo ilegible cuenta como no confiable."""
    global _REDES
    if _REDES is None:
        _REDES = _redes_de_confianza()
    try:
        direccion = ipaddress.ip_address(ip.strip())
    except ValueError:
        return False
    return any(direccion in red for red in _REDES)


def ip_del_cliente(request):
    """La IP del cliente tal como la vio el primer proxy nuestro; o la de la conexion si no se le cree al header."""
    remota = request.META.get('REMOTE_ADDR')
    if getattr(settings, 'TRUSTED_PROXY_COUNT', 0) <= 0:
        return remota
    partes = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    for ip in reversed(partes):
        if not es_de_proxy(ip):
            return ip
    return remota


class LimitePorIpDelCliente(ScopedRateThrottle):
    """El limite de peticiones por IP, con la IP real del cliente y no con el header completo."""

    def get_ident(self, request):
        return ip_del_cliente(request)
