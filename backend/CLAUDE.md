# CLAUDE.md — backend/

Notas especificas de este modulo. Contexto de negocio completo: ../docs/contexto-negocio.md.

## Estructura y settings

- Apps viven bajo `apps/` (paquete), no como apps top-level: `apps.fleet`, `apps.bookings`.
  Cada `AppConfig` usa `name = 'apps.<app>'` y `label = '<app>'`.
- Settings split en `config/settings/{base,local,production}.py`. `manage.py` usa
  `local` por defecto; `wsgi.py`/`asgi.py` usan `production` por defecto (Render las sobreescribe
  via `DJANGO_SETTINGS_MODULE` solo si hace falta otra cosa).
- `production.py` lee todo de variables de entorno (`DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DJANGO_ALLOWED_HOSTS`) — falla explicito si faltan, no hay defaults.

## Comandos (Windows, venv en `backend/venv/`)

```
venv/Scripts/python.exe manage.py runserver 8000
venv/Scripts/python.exe manage.py makemigrations
venv/Scripts/python.exe manage.py migrate
```

## Estado de las apps

- `fleet`, `bookings`: modelos + admin implementados.
- `payments`, `notifications`: carpetas vacias (`__init__.py` solo) — sin implementar todavia.

## Gotchas

- `bookings.Reserva.hora` valida ventana 5:00–7:00am (`validar_ventana_salida` en `models.py`).
  Esto es solo el campo — la validacion de **cupo diario (8-10 viajes)** NO esta implementada aun.
  Cuando se construya, debe ser un motor unico que use tanto el flujo de pago web como la creacion
  manual de reserva desde el admin/panel vendedora — no una copia paralela de la logica (ver
  "Notas de implementacion" en contexto-negocio.md).
- `embarcacion`/`capitan` en `Reserva` son nullable a proposito: quedan vacios hasta que la
  vendedora asigna manualmente.
