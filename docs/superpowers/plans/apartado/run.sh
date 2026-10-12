#!/usr/bin/env bash
# Runner desatendido del plan "apartado temporal". Uso: bash run.sh [NN NN ...]  (sin args: 01..12)
# Variables para pruebas del runner: PLAN_DIR, ROOT, AGY_CMD, SIN_SUITE_COMPLETA=1, SIN_KEEPAWAKE=1
set -u
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAN_DIR="${PLAN_DIR:-$AQUI}"
ROOT="${ROOT:-$(cd "$AQUI/../../../.." && pwd)}"
LOG="$PLAN_DIR/logs"
EV="$LOG/eventos.log"
BRIDGE="${AGY_CMD:-$HOME/.claude/plugins/cache/agy-delegate/agy-delegate/1.6.3/scripts/agy_bridge.sh}"
INTENTOS=3
mkdir -p "$LOG"

evento() { # nivel mensaje
  echo "$(date '+%F %T') [$1] $2" | tee -a "$EV"
}

tsc_limpio() { # errores de tsc, sin los de tipos generados por Next (PageProps/LayoutProps: existen desde antes)
  local salida
  salida="$(npx tsc --noEmit 2>&1 | grep 'error TS' | grep -v -E 'PageProps|LayoutProps')"
  if [ -n "$salida" ]; then echo "$salida"; return 1; fi
  return 0
}
export -f tsc_limpio

# ---- keep-awake (Windows): mantiene el equipo despierto mientras exista la bandera ----
BANDERA="$LOG/keepawake.on"
if [ "${SIN_KEEPAWAKE:-0}" != "1" ]; then
  touch "$BANDERA"
  powershell -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w "$AQUI/keepawake.ps1")" "$(cygpath -w "$BANDERA")" >/dev/null 2>&1 &
fi
terminar() { rm -f "$BANDERA"; }
trap terminar EXIT

# ---- fallos de la suite: conjunto ordenado "FAIL: ..." / "ERROR: ..." ----
fallos_de() { grep -E '^(FAIL|ERROR): ' "$1" | sort -u; }

suite_completa() { # devuelve 0 si no hay fallos nuevos frente a la linea base; deja el reporte en $LOG/suite.out
  [ "${SIN_SUITE_COMPLETA:-0}" = "1" ] && return 0
  (cd "$ROOT/backend" && timeout 2700 python manage.py test apps config --noinput) > "$LOG/suite.out" 2>&1
  fallos_de "$LOG/suite.out" > "$LOG/suite.fallos"
  comm -13 "$LOG/baseline.fallos" "$LOG/suite.fallos" > "$LOG/suite.nuevos"
  [ ! -s "$LOG/suite.nuevos" ]
}

docker_listo() { docker info >/dev/null 2>&1; }

postgres_concurrencia() { # levanta postgres (si hace falta) y corre las pruebas reales; 0 ok
  docker ps -a --format '{{.Names}}' | grep -qx psd-pg || {
    docker run -d --name psd-pg -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
      -e POSTGRES_DB=pescadeportiva_test -p 5433:5432 postgres:17 >/dev/null || return 1
    sleep 12
    docker exec psd-pg psql -U postgres -d pescadeportiva_test -v ON_ERROR_STOP=1 -c \
      "CREATE ROLE ci_rls LOGIN PASSWORD 'ci_rls_password_local' NOSUPERUSER NOBYPASSRLS CREATEDB;" >/dev/null || return 1
  }
  docker start psd-pg >/dev/null 2>&1; sleep 4
  (cd "$ROOT/backend" && DJANGO_SETTINGS_MODULE=config.settings.ci DB_NAME=pescadeportiva_test \
    DB_USER=ci_rls DB_PASSWORD=ci_rls_password_local DB_HOST=localhost DB_PORT=5433 \
    timeout 2400 python manage.py test apps.bookings.tests_apartado_concurrencia apps.bookings.tests_concurrencia apps.payments --noinput) \
    > "$LOG/postgres.out" 2>&1
}

# ---- linea base ----
if [ ! -f "$LOG/baseline.fallos" ]; then
  evento INFO "linea base: corriendo suite completa"
  if [ -s "$LOG/baseline.out" ] && grep -qE '^Ran [0-9]+ tests' "$LOG/baseline.out"; then :; else
    (cd "$ROOT/backend" && timeout 2700 python manage.py test apps config --noinput) > "$LOG/baseline.out" 2>&1
  fi
  fallos_de "$LOG/baseline.out" > "$LOG/baseline.fallos"
  evento INFO "linea base: $(wc -l < "$LOG/baseline.fallos") fallos preexistentes"
fi

TAREAS=("$@")
if [ ${#TAREAS[@]} -eq 0 ]; then TAREAS=(01 02 03 04 05 06 07 08 09 10 11 12); fi

evento INFO "inicio de la corrida: tareas ${TAREAS[*]}"

for n in "${TAREAS[@]}"; do
  if [ -f "$LOG/$n.done" ]; then evento INFO "tarea $n ya hecha, se omite"; continue; fi
  meta="$(ls "$PLAN_DIR"/$n-*.meta 2>/dev/null | head -1)"
  brief="${meta%.meta}.md"
  [ -n "$meta" ] && [ -f "$brief" ] || { evento IMPORTANTE "tarea $n: faltan brief/meta. Corrida detenida"; exit 2; }
  unset TITULO KIND DIRS VERIFY REGRESION SPEC
  # shellcheck disable=SC1090
  . "$meta"
  evento INFO "tarea $n: $TITULO"
  base="$ROOT/backend"; [ "$KIND" = "frontend" ] && base="$ROOT/frontend"
  adddirs=(); for d in $DIRS; do [ -e "$ROOT/$d" ] && adddirs+=(--add-dir "$ROOT/$d"); done

  ok=0; retro=""
  for ((i=1; i<=INTENTOS; i++)); do
    prompt="$LOG/$n.prompt.$i.md"
    { cat "$PLAN_DIR/00-reglas.md"; echo; echo "---"; echo; cat "$brief"
      if [ "$i" -gt 1 ]; then
        echo; echo "## INTENTO ANTERIOR FALLÓ — corrige esto sin rehacer lo que ya está bien"
        echo "El trabajo del intento anterior sigue en el árbol. La verificación (\`$VERIFY\`) falló así:"; echo '```'; echo "$retro"; echo '```'
      fi; } > "$prompt"
    evento INFO "tarea $n intento $i: agy"
    ( cd "$ROOT" && AGY_SKIP_PERMISSIONS=1 bash "$BRIDGE" --type implement --timeout 1500 "${adddirs[@]}" \
        --log-file "$LOG/$n.agy.$i.log" < "$prompt" > "$LOG/$n.agy.$i.out" 2>&1 )
    rc=$?
    [ $rc -ne 0 ] && evento INFO "tarea $n intento $i: agy salió con código $rc"

    ( cd "$base" && timeout 1800 bash -c "$VERIFY" ) > "$LOG/$n.verify.$i.out" 2>&1
    vrc=$?
    if [ $vrc -eq 0 ] && [ "${REGRESION:-0}" = "1" ]; then
      if ! suite_completa; then vrc=1; cp "$LOG/suite.nuevos" "$LOG/$n.verify.$i.out"; echo "(fallos NUEVOS en la suite completa; ver listado arriba)" >> "$LOG/$n.verify.$i.out"; fi
    fi
    if [ $vrc -eq 0 ] && [ "$n" = "12" ]; then
      if docker_listo; then
        postgres_concurrencia || { vrc=1; tail -150 "$LOG/postgres.out" > "$LOG/$n.verify.$i.out"; }
      else
        evento IMPORTANTE "DOCKER_PENDIENTE: Docker apagado; las pruebas de concurrencia en Postgres NO se corrieron"
        echo pendiente > "$LOG/docker.pendiente"
      fi
    fi
    if [ $vrc -eq 0 ]; then ok=1; break; fi
    retro="$(tail -150 "$LOG/$n.verify.$i.out")"; [ -n "$retro" ] || retro="(la verificación falló sin imprimir nada)"
    evento INFO "tarea $n intento $i: verificación falló"
  done

  if [ $ok -ne 1 ]; then
    evento IMPORTANTE "BLOCKED tarea $n tras $INTENTOS intentos ($TITULO). Corrida detenida. Ver $LOG/$n.verify.$INTENTOS.out"
    exit 1
  fi

  ( cd "$ROOT" && git add -A -- . ':!backend/shared' ':!backend/.great_cto' ':!.great_cto' ':!docs/superpowers/plans/apartado/logs' \
    && git commit -q -m "feat(apartado): tarea $n $TITULO (agy, pendiente de revisión)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>" ) >> "$LOG/git.out" 2>&1
  if [ $? -ne 0 ]; then evento IMPORTANTE "tarea $n: falló el commit. Corrida detenida. Ver $LOG/git.out"; exit 1; fi
  touch "$LOG/$n.done"
  evento INFO "tarea $n OK, commit $(cd "$ROOT" && git rev-parse --short HEAD)"

  # revisión independiente (no bloquea): diff del commit contra el spec
  { echo "Revisa este commit contra el spec docs/superpowers/specs/2026-10-12-apartado-temporal-cupo-design.md (secciones: $SPEC)."
    echo "Busca defectos reales: contradicciones con el spec, nombres inventados, carreras, tenancy, except demasiado amplio, pruebas que no prueban lo que dicen. Reporte breve en español, con archivo:línea. No edites nada."
    echo; echo '```diff'; (cd "$ROOT" && git show HEAD --stat -p | head -c 90000); echo '```'; } > "$LOG/$n.review.prompt.md"
  ( cd "$ROOT" && AGY_SKIP_PERMISSIONS=1 bash "$BRIDGE" --type review --timeout 600 --add-dir "$ROOT/docs" \
      < "$LOG/$n.review.prompt.md" > "$PLAN_DIR/$n.review.md" 2>>"$LOG/review.err" ) || evento INFO "tarea $n: la revisión de agy no terminó"

  case "$n" in 05|08|11) evento IMPORTANTE "HITO: tarea $n lista (${TITULO})";; esac
done

# ---- cierre ----
if [ "${SIN_SUITE_COMPLETA:-0}" != "1" ]; then
  if suite_completa; then evento INFO "suite completa SQLite: sin fallos nuevos"; else evento INFO "suite completa SQLite: HAY fallos nuevos ($(wc -l < "$LOG/suite.nuevos")), ver $LOG/suite.nuevos"; fi
  if [ -d "$ROOT/frontend/node_modules" ] && [[ " ${TAREAS[*]} " =~ " 11 " ]]; then
    ( cd "$ROOT/frontend" && timeout 1200 npm run build ) > "$LOG/build.out" 2>&1 \
      && evento INFO "npm run build OK" || evento INFO "npm run build FALLÓ, ver $LOG/build.out"
  fi
fi
evento IMPORTANTE "FIN de la corrida. Resumen: $(ls "$LOG"/*.done 2>/dev/null | wc -l) tareas hechas; revisa eventos.log"
