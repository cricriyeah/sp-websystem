/* Aviso de reservas nuevas y campana de notificaciones en cualquier pantalla del admin.
 *
 * Pregunta cada 10 segundos (solo con la pestana a la vista) que reservas entraron desde la ultima vez y las
 * muestra arriba a la derecha. No es instantaneo: el admin no tiene una conexion abierta con el navegador y
 * montar una (WebSockets) no vale la pena para este volumen. Nunca recarga sola: la vendedora puede estar a media
 * asignacion; en el listado de Reservas y en Asignar pangas el aviso ofrece "Actualizar lista".
 * Ver apps/bookings/avisos.py.
 *
 * La misma respuesta trae `no_leidas` y `notificaciones_url`: con ellos se pinta la campana de notificaciones en el
 * encabezado (apps/tenancy/notificaciones.py) sin otra peticion. Si el contador sube entre una consulta y la
 * siguiente sale una tarjeta «Notificación nueva»: el correo de asignacion y otros procesos terminan cuando la
 * pantalla que los pidio ya respondio, asi que ese es el aviso inmediato de lo que paso despues.
 */
(function () {
  'use strict';

  var INTERVALO_MS = 10000;
  var MAXIMO_VISIBLES = 3;
  var FALLOS_PARA_PARAR = 3;
  var ENDPOINT = '/admin/avisos/reservas-nuevas/';

  // Sin sesion no hay a quien avisar: login, recuperacion de contrasena y cierre de sesion.
  if (/\/admin\/(login|logout|recuperar|password_reset)/.test(window.location.pathname)) return;

  var enListado = /\/(bookings\/(reserva|agenda)|tenancy\/notificacion)\/$/.test(window.location.pathname);
  var desde = null;
  var timer = null;
  var fallos = 0;
  var contenedor = null;
  var campana = null;
  var insignia = null;
  var conteoAnterior = null;

  function el(etiqueta, clase, texto) {
    var nodo = document.createElement(etiqueta);
    if (clase) nodo.className = clase;
    if (texto) nodo.textContent = texto;
    return nodo;
  }

  function cuando(fechaISO, hora) {
    var p = fechaISO.split('-');
    var fecha = new Date(Number(p[0]), Number(p[1]) - 1, Number(p[2]));
    var texto = new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'short' }).format(fecha);
    return hora ? texto + ' ' + hora : texto;
  }

  function asegurarContenedor() {
    if (contenedor) return contenedor;
    contenedor = el('div', 'aviso-reservas');
    contenedor.setAttribute('role', 'status');
    contenedor.setAttribute('aria-live', 'polite');
    document.body.appendChild(contenedor);
    return contenedor;
  }

  function crearAviso(titulo, detalle, enlace, enlaceTexto) {
    var tarjeta = el('div', 'aviso-reservas__tarjeta');
    tarjeta.appendChild(el('p', 'aviso-reservas__titulo', titulo));
    if (detalle) tarjeta.appendChild(el('p', 'aviso-reservas__detalle', detalle));
    var acciones = el('div', 'aviso-reservas__acciones');
    if (enlace) {
      var a = el('a', 'aviso-reservas__boton', enlaceTexto);
      a.href = enlace;
      acciones.appendChild(a);
    }
    if (enListado) {
      var actualizar = el('button', 'aviso-reservas__boton', 'Actualizar lista');
      actualizar.type = 'button';
      actualizar.addEventListener('click', function () { window.location.reload(); });
      acciones.appendChild(actualizar);
    }
    var cerrar = el('button', 'aviso-reservas__cerrar', 'Cerrar');
    cerrar.type = 'button';
    cerrar.addEventListener('click', function () { tarjeta.remove(); });
    acciones.appendChild(cerrar);
    tarjeta.appendChild(acciones);
    return tarjeta;
  }

  // Todo lo que viene del servidor entra con textContent: el nombre del cliente lo escribe el cliente.
  function mostrar(datos) {
    var lugar = asegurarContenedor();
    datos.reservas.forEach(function (r) {
      var partes = [r.producto, cuando(r.fecha, r.hora), r.personas + (r.personas === 1 ? ' persona' : ' personas')]
        .filter(Boolean);
      var tarjeta = crearAviso('Nueva reserva: ' + r.cliente, partes.join(' · '), r.url, 'Ver reserva');
      lugar.insertBefore(tarjeta, lugar.firstChild);
    });
    var sobran = datos.total - datos.reservas.length;
    if (sobran > 0) {
      lugar.insertBefore(
        crearAviso('+' + sobran + (sobran === 1 ? ' reserva nueva más' : ' reservas nuevas más'), '', null, ''),
        lugar.firstChild
      );
    }
    while (lugar.children.length > MAXIMO_VISIBLES) lugar.removeChild(lugar.lastChild);
  }

  // Solo rutas del propio sitio: la URL viene del servidor, pero un enlace nunca debe poder ser `javascript:`.
  function rutaPropia(url) {
    return typeof url === 'string' && url.charAt(0) === '/' && url.charAt(1) !== '/' && !/[\\\u0000-\u0020\u007f]/.test(url);
  }

  function asegurarCampana(url) {
    if (campana) return;
    campana = el('a', 'aviso-campana');
    campana.href = url;
    var icono = el('span', 'material-symbols-outlined', 'notifications');
    icono.setAttribute('aria-hidden', 'true');
    insignia = el('span', 'aviso-campana__badge');
    insignia.setAttribute('aria-hidden', 'true');
    insignia.hidden = true;
    campana.appendChild(icono);
    campana.appendChild(insignia);
    var cabecera = document.querySelector('#header-inner .ml-auto');
    if (cabecera) {
      cabecera.insertBefore(campana, cabecera.firstChild);
    } else {
      campana.className += ' aviso-campana--flotante';
      document.body.appendChild(campana);
    }
  }

  function pintarCampana(datos) {
    if (!rutaPropia(datos.notificaciones_url)) return;
    asegurarCampana(datos.notificaciones_url);
    var n = Number(datos.no_leidas) || 0;
    insignia.textContent = n > 99 ? '99+' : String(n);
    insignia.hidden = n === 0;
    campana.setAttribute('aria-label', n === 0 ? 'Notificaciones' : 'Notificaciones, ' + n + ' sin leer');
    if (conteoAnterior !== null) {
      // Lo que ya explica una tarjeta de «Nueva reserva» de esta misma consulta no se avisa dos veces.
      var nuevas = n - conteoAnterior - (Number(datos.total) || 0);
      if (nuevas > 0) {
        var titulo = nuevas === 1 ? 'Notificación nueva' : nuevas + ' notificaciones nuevas';
        var lugar = asegurarContenedor();
        lugar.insertBefore(crearAviso(titulo, '', datos.notificaciones_url, 'Ver notificaciones'), lugar.firstChild);
        while (lugar.children.length > MAXIMO_VISIBLES) lugar.removeChild(lugar.lastChild);
      }
    }
    conteoAnterior = n;
  }

  function consultar() {
    var url = desde ? ENDPOINT + '?desde=' + encodeURIComponent(desde) : ENDPOINT;
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (res) {
        var tipo = res.headers.get('content-type') || '';
        if (!res.ok || tipo.indexOf('application/json') === -1) throw new Error('sin respuesta util');
        return res.json();
      })
      .then(function (datos) {
        fallos = 0;
        desde = datos.desde;
        pintarCampana(datos);
        if (datos.total > 0) mostrar(datos);
      })
      .catch(function () {
        // Sesion vencida (el admin responde con la pantalla de login) o backend caido: se reintenta unas veces y
        // se calla. No hay nada util que decirle a quien esta trabajando.
        fallos += 1;
        if (fallos >= FALLOS_PARA_PARAR) parar();
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

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      parar();
    } else if (fallos < FALLOS_PARA_PARAR) {
      consultar();
      arrancar();
    }
  });

  consultar();
  arrancar();
})();
