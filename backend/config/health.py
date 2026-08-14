"""Sonda de salud para el balanceador de Render.

Existe porque `render.yaml` apuntaba su `healthCheckPath` a `/api/tarifa/`, y esa
ruta responde 503 mientras no exista la fila de `Tarifa`. En una base recien
migrada no existe, asi que el primer deploy nunca pasaba el health check y Render
lo cancelaba — pero la Tarifa no se puede crear hasta que el servicio este
arriba. Circulo cerrado.

La leccion es la distincion que faltaba: **el health check responde "¿puede este
proceso atender peticiones?", no "¿esta el negocio configurado?"**. Un dia sin
tarifa cargada es un problema de operacion, no un motivo para tumbar el deploy.

Por eso aqui se verifica solo la infraestructura: que el proceso responde y que
la base contesta. Nada de filas de negocio. Si alguna vez hace falta una sonda
que valide que el sistema esta listo para vender, va en otra ruta y **no** en el
`healthCheckPath` de Render.
"""
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """200 si el proceso vive y la base contesta; 503 si no.

    El `SELECT 1` esta a proposito: detecta credenciales mal puestas o una base
    inalcanzable en el momento del deploy, que es cuando todavia se puede
    revertir sin que nadie lo note. Es la unica dependencia externa que se
    comprueba — no se llama a Stripe ni a Resend, porque que un tercero este
    caido no significa que esta version no deba estar viva.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception as exc:
        # Sin logger.exception: si la base esta caida esto se repite en cada
        # sondeo y llenaria el log justo cuando hay que leerlo.
        return JsonResponse(
            {'status': 'error', 'database': 'unreachable', 'detail': str(exc)[:200]},
            status=503,
        )

    return JsonResponse({'status': 'ok', 'database': 'ok'})
