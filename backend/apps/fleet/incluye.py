"""Lo que incluye un servicio o un paquete, por idioma: `{"es": [..], "en": [..]}`.

Lo pinta la tarjeta del catálogo y la página de detalle (Task 9.0). Es lista propia del
producto: nunca se deriva de `descripcion`. Lo usan `Servicio.clean()`, `Paquete.clean()`
y los formularios del admin, que lo capturan como un renglón por línea.
"""

INCLUYE_IDIOMAS = ('es', 'en')
INCLUYE_MAX_RENGLONES = 8
INCLUYE_MAX_CARACTERES = 80


def normalizar_incluye(valor):
    """(lista recortada, '') si es válido; (None, mensaje) si no."""
    if not isinstance(valor, dict):
        return None, 'Lo que incluye debe ser un objeto con las claves es y en.'
    if set(valor) - set(INCLUYE_IDIOMAS):
        return None, 'Lo que incluye solo admite las claves es y en.'
    limpio = {}
    for idioma, renglones in valor.items():
        if not isinstance(renglones, list):
            return None, 'Cada idioma debe ser una lista de renglones.'
        if len(renglones) > INCLUYE_MAX_RENGLONES:
            return None, f'Cada idioma admite hasta {INCLUYE_MAX_RENGLONES} renglones.'
        recortados = []
        for renglon in renglones:
            if not isinstance(renglon, str) or not renglon.strip():
                return None, 'Cada renglón debe ser un texto no vacío.'
            renglon = renglon.strip()
            if len(renglon) > INCLUYE_MAX_CARACTERES:
                return None, f'Cada renglón admite hasta {INCLUYE_MAX_CARACTERES} caracteres.'
            recortados.append(renglon)
        limpio[idioma] = recortados
    return limpio, ''


def lineas_de_texto(texto):
    """Un renglón por línea, sin espacios sobrantes ni líneas vacías (cuadro de texto del admin)."""
    return [linea.strip() for linea in (texto or '').splitlines() if linea.strip()]
