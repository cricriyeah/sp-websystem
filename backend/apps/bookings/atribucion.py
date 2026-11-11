"""De dónde llegó el cliente que compró en la web (plan de marketing de 90 días, 2026-11-11).

El navegador guarda los parámetros del enlace por el que entró (`utm_*`, el id de clic de Meta o de Google, de qué
sitio venía y a qué página llegó) y los manda con la reserva (`frontend/src/lib/atribucion.ts`). Aquí solo se
limpia: llega del navegador, así que cualquiera puede mandar lo que quiera. Solo pasan las claves conocidas, como
texto corto; lo demás se descarta en silencio, igual que un `?ref=` que no resuelve: nada de esto puede impedir que
alguien reserve.

No es la vendedora (`Reserva.vendedora`, el `?ref=`): eso dice quién vendió; esto, por qué anuncio o red llegó.
"""

CLAVES = (
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'fbclid', 'gclid',
    # Dominio del sitio del que venía (sin ruta ni parámetros) y la ruta a la que llegó.
    'referrer', 'landing',
    # Cuándo lo guardó el navegador (ISO 8601).
    'capturado_en',
    # Cookies del pixel de Meta, solo si el cliente las aceptó: la API de Conversiones las pide para unir la compra
    # con el anuncio.
    'fbp', 'fbc',
)
LARGO_MAXIMO = 300


def limpiar(dato):
    """Lo que el navegador mandó, reducido a las claves conocidas y a texto de largo razonable. Nunca lanza."""
    if not isinstance(dato, dict):
        return {}
    limpio = {}
    for clave in CLAVES:
        valor = dato.get(clave)
        if isinstance(valor, str):
            valor = valor.strip()[:LARGO_MAXIMO]
            if valor:
                limpio[clave] = valor
    return limpio


# Cómo se lee la fuente para la lista del admin: el `utm_source` que ponen las campañas, o el id de clic.
_FUENTES = {
    'facebook': 'Meta', 'fb': 'Meta', 'instagram': 'Meta', 'ig': 'Meta', 'meta': 'Meta',
    'google': 'Google', 'tiktok': 'TikTok',
}


def resumen(atribucion):
    """«Meta · anuncio · semana-santa», «Google», «Llegó desde tripadvisor.com» o '' si no hay nada."""
    if not atribucion:
        return ''
    fuente = (atribucion.get('utm_source') or '').lower()
    nombre = _FUENTES.get(fuente) or atribucion.get('utm_source') or ''
    if not nombre:
        if atribucion.get('fbclid'):
            nombre = 'Meta'
        elif atribucion.get('gclid'):
            nombre = 'Google'
    if nombre:
        partes = [nombre, atribucion.get('utm_medium', ''), atribucion.get('utm_campaign', '')]
        return ' · '.join(p for p in partes if p)
    if atribucion.get('referrer'):
        return f'Llegó desde {atribucion["referrer"]}'
    return ''
