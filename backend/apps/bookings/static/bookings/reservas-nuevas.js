/* Aviso de reservas nuevas en el listado del admin.
 *
 * Pregunta cada 30 segundos cuantas reservas entraron desde que se cargo la
 * pagina y muestra un boton con el conteo. Nunca recarga sola: la vendedora
 * puede estar a media asignacion de capitan, asi que el refresco lo decide ella.
 * Ver ReservaAdmin.reservas_nuevas_view en apps/bookings/admin.py.
 */
(function () {
  'use strict';

  var INTERVALO_MS = 30000;

  // Solo en los listados que tienen su endpoint `nuevas/`: Reservas y Agenda. Se
  // valida contra la URL y no contra el DOM porque unfold reescribe las
  // plantillas del admin y sus ids pueden cambiar.
  if (!/\/bookings\/(reserva|agenda)\/$/.test(window.location.pathname)) return;

  var endpoint = new URL('nuevas/', window.location.origin + window.location.pathname).toString();
  var desde = null;
  var boton = null;
  var timer = null;

  function crearBoton() {
    var el = document.createElement('button');
    el.type = 'button';
    el.hidden = true;
    el.style.cssText = [
      'position:fixed', 'right:1.5rem', 'bottom:1.5rem', 'z-index:60',
      'padding:0.75rem 1.25rem', 'border:none', 'border-radius:9999px',
      'background:rgb(194 65 12)', 'color:#fff', 'font-size:0.875rem',
      'font-weight:500', 'cursor:pointer',
      'box-shadow:0 10px 25px rgba(0,0,0,0.18)',
    ].join(';');
    el.addEventListener('click', function () {
      window.location.reload();
    });
    document.body.appendChild(el);
    return el;
  }

  function render(nuevas) {
    if (!boton) boton = crearBoton();
    if (nuevas < 1) {
      boton.hidden = true;
      return;
    }
    boton.textContent =
      nuevas === 1
        ? '1 reserva nueva — actualizar'
        : nuevas + ' reservas nuevas — actualizar';
    boton.hidden = false;
  }

  function consultar() {
    // Sin `desde` la primera vez: el servidor devuelve su propia hora y con eso
    // se ancla la cuenta, sin depender del reloj del navegador.
    var url = desde ? endpoint + '?desde=' + encodeURIComponent(desde) : endpoint;

    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        desde = data.desde;
        render(data.nuevas);
      })
      .catch(function () {
        // Sesion expirada o backend caido: no se avisa nada y se reintenta
        // en el siguiente ciclo.
      });
  }

  function arrancar() {
    if (timer) return;
    timer = window.setInterval(consultar, INTERVALO_MS);
  }

  function parar() {
    window.clearInterval(timer);
    timer = null;
  }

  // Con la pestaña en segundo plano no tiene caso preguntar; al volver se
  // consulta de inmediato para no esperar el ciclo completo.
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      parar();
    } else {
      consultar();
      arrancar();
    }
  });

  consultar();
  arrancar();
})();
