"""Migración PostgreSQL para crear función SECURITY DEFINER estado_reservas_de_orden."""

from django.db import migrations

SQL_FUNCION = """
CREATE OR REPLACE FUNCTION estado_reservas_de_orden(p_orden_id bigint)
RETURNS TABLE (
  reserva_id bigint,
  empresa_id bigint,
  servicio_id bigint,
  estado text,
  monto_pagado numeric,
  monto_reembolsado numeric,
  stripe_payment_intent_id text,
  correo_cliente text
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_prev_operador text;
BEGIN
  v_prev_operador := current_setting('app.operador_plataforma', true);
  PERFORM set_config('app.operador_plataforma', 'on', true);

  RETURN QUERY
    SELECT r.id, r.empresa_id, r.servicio_id, r.estado::text, r.monto_pagado, r.monto_reembolsado,
           r.stripe_payment_intent_id::text, r.correo_cliente::text
    FROM bookings_reserva r
    WHERE r.orden_id = p_orden_id;

  IF v_prev_operador IS NULL THEN
    PERFORM set_config('app.operador_plataforma', '', true);
  ELSE
    PERFORM set_config('app.operador_plataforma', v_prev_operador, true);
  END IF;
END;
$$;
"""

SQL_REVOCAR = """
DROP FUNCTION IF EXISTS estado_reservas_de_orden(bigint);
DROP FUNCTION IF EXISTS estado_reservas_de_orden(int);
"""


def aplicar_funcion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_FUNCION)
        cursor.execute("REVOKE ALL ON FUNCTION estado_reservas_de_orden(bigint) FROM PUBLIC;")
        # El USER configurado puede no ser el nombre real del rol: detras del pooler de
        # Supabase lleva el sufijo del proyecto ("app_pesca.<ref>") y GRANT a ese nombre
        # falla con "role does not exist". Se prueba tal cual y sin el sufijo, y solo se
        # otorga a los que existan; CURRENT_USER (abajo) cubre al rol que migra.
        user = schema_editor.connection.settings_dict.get('USER')
        if user:
            for rol in dict.fromkeys([user, user.split('.')[0]]):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [rol])
                if cursor.fetchone():
                    cursor.execute(f'GRANT EXECUTE ON FUNCTION estado_reservas_de_orden(bigint) TO "{rol}";')
        cursor.execute("GRANT EXECUTE ON FUNCTION estado_reservas_de_orden(bigint) TO CURRENT_USER;")


def revertir_funcion(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_REVOCAR)


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0042_rls_orden'),
    ]

    operations = [
        migrations.RunPython(aplicar_funcion, revertir_funcion),
    ]
