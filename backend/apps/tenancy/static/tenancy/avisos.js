/* Aviso de reservas nuevas y campana de notificaciones en cualquier pantalla del admin.
 *
 * Pregunta cada 10 segundos que reservas entraron desde la ultima vez y las muestra arriba a la derecha. Sigue
 * preguntando con la pestana en segundo plano (el ritmo lo marca un worker: los navegadores frenan los temporizadores
 * normales de una pestana oculta a una vez por minuto o menos) y ahi avisa tambien con el sonido, el titulo de la
 * pestana y, si la persona lo activo, una notificacion del sistema. No es instantaneo: el admin no tiene una conexion
 * abierta con el navegador y montar una (WebSockets) no vale la pena para este volumen. Nunca recarga sola: la vendedora puede estar a media
 * asignacion; en el listado de Reservas y en Asignar pangas el aviso ofrece "Actualizar lista".
 * Ver apps/bookings/avisos.py.
 *
 * La misma respuesta trae `no_leidas` y `notificaciones_url`: con ellos se pinta la campana de notificaciones en el
 * encabezado (apps/tenancy/notificaciones.py) sin otra peticion. Al hacer clic en la campana se abre un panel con las
 * ultimas (apps/tenancy/vistas_notificaciones.py); la lista completa queda a un enlace. Si el contador sube entre una consulta y la
 * siguiente sale una tarjeta «Notificación nueva»: el correo de asignacion y otros procesos terminan cuando la
 * pantalla que los pidio ya respondio, asi que ese es el aviso inmediato de lo que paso despues.
 */
(function () {
  'use strict';

  // Mientras esta clase no exista, avisos.css NO esconde las barras de Django: si este script no corre, un error de
  // guardado se sigue viendo.
  document.documentElement.classList.add('avisos-js');

  var INTERVALO_MS = 10000;
  var MAXIMO_VISIBLES = 3;
  var FALLOS_PARA_PARAR = 3;
  var ENDPOINT = '/admin/avisos/reservas-nuevas/';
  var ENDPOINT_PANEL = '/admin/avisos/notificaciones/';

  // Sin sesion no hay a quien avisar: login, recuperacion de contrasena y cierre de sesion. Los avisos de Django
  // (tarjetas) si se convierten ahi tambien; el sondeo, la campana y el sonido no.
  var sinSesion = /\/admin\/(login|logout|recuperar|password_reset)/.test(window.location.pathname);

  var enListado = /\/(bookings\/(reserva|agenda)|tenancy\/notificacion)\/$/.test(window.location.pathname);
  var desde = null;
  var timer = null;
  var worker = null;
  var tituloOriginal = document.title;
  var tituloPendientes = 0;
  var CLAVE_OFRECIDO = 'avisos-sistema-ofrecido';
  var ofrecido = false;
  var fallos = 0;
  var contenedor = null;
  var campana = null;
  var insignia = null;
  var todasUrl = '';
  var panel = null;
  var panelLista = null;
  var panelEstado = null;
  var panelMarcar = null;
  var panelPie = null;
  var panelAbierto = false;
  var cargaDelPanel = 0;
  var csrfPanel = '';
  var urlMarcarTodas = '';
  var ultimaNotif = null;
  var CLAVE_ULTIMA = 'avisos-ultima-notificacion';
  var vistas = null;
  var CLAVE_VISTAS = 'avisos-notificaciones-vistas';
  var MAXIMO_VISTAS = 50;
  var audio = null;
  var botonSonido = null;
  var CLAVE_SILENCIO = 'avisos-sonido-apagado';
  var SEGUNDOS_DE_EXITO = 8;

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

  // Quita tarjetas viejas cuando hay muchas, pero nunca un error: quien lo causo tiene que poder leerlo.
  function recortar(lugar) {
    while (lugar.children.length > MAXIMO_VISIBLES) {
      var candidata = null;
      for (var i = lugar.children.length - 1; i >= 0; i -= 1) {
        if (lugar.children[i].getAttribute('data-nivel') !== 'error') { candidata = lugar.children[i]; break; }
      }
      if (!candidata) return;
      lugar.removeChild(candidata);
    }
  }

  var TITULOS_DE_AVISO = { success: 'Listo', info: 'Aviso', warning: 'Ojo', error: 'No salió' };

  // Los avisos de Django («Panga y capitán asignados…») ya vienen en la pagina (templates/unfold/helpers/messages.html):
  // se leen con textContent y se pintan como tarjetas, en vez de las barras verdes y naranjas de Unfold.
  function convertirAvisosDeDjango() {
    var listas = document.querySelectorAll('[data-avisos-django]');
    for (var i = 0; i < listas.length; i += 1) {
      var lista = listas[i];
      try {
        var items = lista.querySelectorAll('li[data-nivel]');
        var lugar = asegurarContenedor();
        for (var j = 0; j < items.length; j += 1) {
          var nivel = items[j].getAttribute('data-nivel') || 'info';
          if (!TITULOS_DE_AVISO[nivel]) nivel = 'info';
          var texto = (items[j].textContent || '').replace(/\s+/g, ' ').trim();
          if (!texto) continue;
          var tarjeta = crearAviso(TITULOS_DE_AVISO[nivel], texto, null, '', nivel);
          lugar.appendChild(tarjeta);
          if (nivel === 'success') programarCierre(tarjeta, SEGUNDOS_DE_EXITO);
        }
        recortar(lugar);
        lista.parentNode.removeChild(lista);
      } catch (e) {
        lista.style.display = 'block'; // si algo falla, salen las barras de siempre: nunca se pierde un mensaje
      }
    }
  }

  function programarCierre(tarjeta, segundos) {
    window.setTimeout(function () { if (tarjeta.parentNode) tarjeta.parentNode.removeChild(tarjeta); }, segundos * 1000);
  }

  function crearAviso(titulo, detalle, enlace, enlaceTexto, nivel, accion) {
    var tarjeta = el('div', 'aviso-reservas__tarjeta');
    var cabecera = el('p', 'aviso-reservas__titulo');
    if (nivel) {
      tarjeta.setAttribute('data-nivel', nivel);
      var marca = el('span', 'aviso-reservas__marca aviso-reservas__marca--' + nivel);
      marca.setAttribute('aria-hidden', 'true');
      cabecera.appendChild(marca);
    }
    cabecera.appendChild(document.createTextNode(titulo));
    tarjeta.appendChild(cabecera);
    if (detalle) tarjeta.appendChild(el('p', 'aviso-reservas__detalle', detalle));
    var acciones = el('div', 'aviso-reservas__acciones');
    if (enlace) {
      var a = el('a', 'aviso-reservas__boton', enlaceTexto);
      a.href = enlace;
      acciones.appendChild(a);
    }
    if (accion) {
      var extra = el('button', 'aviso-reservas__boton', accion.texto);
      extra.type = 'button';
      extra.addEventListener('click', accion.hacer);
      acciones.appendChild(extra);
    }
    if (enListado && !nivel) {
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
    recortar(lugar);
    if (datos.reservas.length > 0) {
      sonar();
      marcarTitulo(datos.total);
      var primera = datos.reservas[0];
      var cuerpo = primera.cliente + (primera.producto ? ' · ' + primera.producto : '');
      if (datos.total > 1) cuerpo += ' (+' + (datos.total - 1) + ' más)';
      avisarAlSistema('Nueva reserva', cuerpo, 'reserva-nueva');
    }
  }

  // Con la ventana en segundo plano la tarjeta no se ve: el titulo de la pestana lleva la cuenta y, si la persona dio
  // permiso, el sistema operativo muestra una notificacion. El permiso se pide solo con un clic (ver ofrecerAvisosDelSistema).
  function fueraDeVista() {
    return document.hidden || !document.hasFocus();
  }

  function marcarTitulo(cuantas) {
    if (!fueraDeVista()) return;
    tituloPendientes += Number(cuantas) || 1;
    document.title = '(' + tituloPendientes + ') Nueva reserva · ' + tituloOriginal;
  }

  function restaurarTitulo() {
    if (tituloPendientes === 0) return;
    tituloPendientes = 0;
    document.title = tituloOriginal;
  }

  function avisarAlSistema(titulo, cuerpo, etiqueta) {
    if (!fueraDeVista() || typeof window.Notification === 'undefined' || window.Notification.permission !== 'granted') return;
    try {
      var aviso = new window.Notification(titulo, { body: cuerpo, tag: etiqueta });
      aviso.onclick = function () { window.focus(); aviso.close(); };
    } catch (e) { /* sin notificaciones del sistema: quedan el sonido y el titulo */ }
  }

  // Una sola vez por navegador ofrece activar las notificaciones del sistema, con un boton (el navegador exige un clic).
  function ofrecerAvisosDelSistema() {
    if (ofrecido || typeof window.Notification === 'undefined' || window.Notification.permission !== 'default') return;
    ofrecido = true;
    try {
      if (window.localStorage.getItem(CLAVE_OFRECIDO) === '1') return;
      window.localStorage.setItem(CLAVE_OFRECIDO, '1');
    } catch (e) { return; }
    var lugar = asegurarContenedor();
    lugar.insertBefore(
      crearAviso(
        'Avisos con la ventana en segundo plano',
        'Activa los avisos del sistema para enterarte de una reserva nueva aunque estés en otra pestaña o programa.',
        null, '', 'info', { texto: 'Activar', hacer: function () { window.Notification.requestPermission(); } }
      ),
      lugar.firstChild
    );
    recortar(lugar);
  }

  // Sonido de reserva nueva: dos tonos cortos generados en el navegador (sin archivo de audio). Los navegadores no
  // dejan sonar nada hasta que la persona toco la pagina una vez (clic o tecla); antes de eso, la tarjeta sale igual
  // pero en silencio. Se apaga con el boton de la bocina y la eleccion se recuerda en este navegador.
  function sonidoApagado() {
    try { return window.localStorage.getItem(CLAVE_SILENCIO) === '1'; } catch (e) { return false; }
  }

  function desbloquearAudio() {
    var Contexto = window.AudioContext || window.webkitAudioContext;
    if (!audio && Contexto) {
      try { audio = new Contexto(); } catch (e) { audio = null; }
    }
    if (audio && audio.state === 'suspended') audio.resume();
  }

  function tono(frecuencia, inicio, duracion) {
    var oscilador = audio.createOscillator();
    var volumen = audio.createGain();
    oscilador.type = 'sine';
    oscilador.frequency.value = frecuencia;
    volumen.gain.setValueAtTime(0.0001, inicio);
    volumen.gain.exponentialRampToValueAtTime(0.2, inicio + 0.02);
    volumen.gain.exponentialRampToValueAtTime(0.0001, inicio + duracion);
    oscilador.connect(volumen);
    volumen.connect(audio.destination);
    oscilador.start(inicio);
    oscilador.stop(inicio + duracion + 0.05);
  }

  function sonar() {
    if (sonidoApagado() || !audio || audio.state !== 'running') return;
    try {
      var ahora = audio.currentTime;
      tono(880, ahora, 0.18);
      tono(1175, ahora + 0.2, 0.28);
    } catch (e) { /* sin sonido: la tarjeta ya salio */ }
  }

  function pintarBotonSonido() {
    var apagado = sonidoApagado();
    botonSonido.firstChild.textContent = apagado ? 'volume_off' : 'volume_up';
    botonSonido.setAttribute('aria-pressed', apagado ? 'true' : 'false');
    botonSonido.setAttribute('aria-label', apagado ? 'Activar el sonido de reservas nuevas' : 'Silenciar el sonido de reservas nuevas');
    botonSonido.title = apagado ? 'Sonido de reservas nuevas: apagado' : 'Sonido de reservas nuevas: encendido';
  }

  function asegurarBotonSonido() {
    if (botonSonido) return;
    botonSonido = el('button', 'aviso-sonido');
    botonSonido.type = 'button';
    var icono = el('span', 'material-symbols-outlined', 'volume_up');
    icono.setAttribute('aria-hidden', 'true');
    botonSonido.appendChild(icono);
    botonSonido.addEventListener('click', function () {
      desbloquearAudio();
      try { window.localStorage.setItem(CLAVE_SILENCIO, sonidoApagado() ? '0' : '1'); } catch (e) { /* sin memoria */ }
      pintarBotonSonido();
      if (!sonidoApagado()) sonar(); // al encenderlo suena una vez: asi se sabe que funciona
    });
    pintarBotonSonido();
    var cabecera = document.querySelector('#header-inner .ml-auto');
    if (cabecera) {
      cabecera.insertBefore(botonSonido, cabecera.firstChild);
    } else {
      botonSonido.className += ' aviso-sonido--flotante';
      document.body.appendChild(botonSonido);
    }
  }

  // Solo rutas del propio sitio: la URL viene del servidor, pero un enlace nunca debe poder ser `javascript:`.
  function rutaPropia(url) {
    return typeof url === 'string' && url.charAt(0) === '/' && url.charAt(1) !== '/' && !/[\\\u0000-\u0020\u007f]/.test(url);
  }

  function asegurarCampana(url) {
    if (campana) return;
    todasUrl = url;
    // Boton, no enlace: abre el panel encima de la pantalla actual. La lista completa queda al pie del panel.
    campana = el('button', 'aviso-campana');
    campana.type = 'button';
    campana.setAttribute('aria-haspopup', 'dialog');
    campana.setAttribute('aria-expanded', 'false');
    campana.setAttribute('aria-controls', 'aviso-panel');
    campana.addEventListener('click', alternarPanel);
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
    ponerConteo(datos.no_leidas);
  }

  function ponerConteo(sinLeer) {
    var n = Number(sinLeer) || 0;
    insignia.textContent = n > 99 ? '99+' : String(n);
    insignia.hidden = n === 0;
    campana.setAttribute('aria-label', n === 0 ? 'Notificaciones' : 'Notificaciones, ' + n + ' sin leer');
  }

  // Panel de la campana: un rectangulo debajo de ella con las ultimas notificaciones. Se consulta al abrirlo
  // (/admin/avisos/notificaciones/), no en el sondeo. Todo lo del servidor entra con textContent.
  function hora(iso) {
    var fecha = new Date(iso);
    if (isNaN(fecha.getTime())) return '';
    return new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
      .format(fecha);
  }

  function asegurarPanel() {
    if (panel) return;
    panel = el('div', 'aviso-panel');
    panel.id = 'aviso-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Notificaciones');
    panel.tabIndex = -1;
    panel.hidden = true;
    var cabecera = el('div', 'aviso-panel__cabecera');
    cabecera.appendChild(el('p', 'aviso-panel__titulo', 'Notificaciones'));
    panelMarcar = el('button', 'aviso-panel__marcar', 'Marcar todas como leídas');
    panelMarcar.type = 'button';
    panelMarcar.hidden = true;
    panelMarcar.addEventListener('click', marcarTodasDesdeElPanel);
    cabecera.appendChild(panelMarcar);
    panelEstado = el('p', 'aviso-panel__estado', 'Cargando…');
    panelEstado.setAttribute('role', 'status');
    panelLista = el('ul', 'aviso-panel__lista');
    panelPie = el('a', 'aviso-panel__todas', 'Ver todas las notificaciones');
    if (rutaPropia(todasUrl)) panelPie.href = todasUrl;
    panel.appendChild(cabecera);
    panel.appendChild(panelEstado);
    panel.appendChild(panelLista);
    panel.appendChild(panelPie);
    document.body.appendChild(panel);
  }

  function colocarPanel() {
    var caja = campana.getBoundingClientRect();
    panel.style.top = Math.round(caja.bottom + 8) + 'px';
    panel.style.maxHeight = Math.max(240, window.innerHeight - caja.bottom - 24) + 'px';
  }

  function alternarPanel() {
    if (panelAbierto) { cerrarPanel(false); } else { abrirPanel(); }
  }

  function abrirPanel() {
    asegurarPanel();
    panelAbierto = true;
    panel.hidden = false;
    colocarPanel();
    campana.setAttribute('aria-expanded', 'true');
    cargarPanel();
    panel.focus();
  }

  function cerrarPanel(devolverFoco) {
    if (!panelAbierto) return;
    panelAbierto = false;
    panel.hidden = true;
    campana.setAttribute('aria-expanded', 'false');
    if (devolverFoco) campana.focus();
  }

  function cargarPanel() {
    var turno = cargaDelPanel += 1;
    fetch(ENDPOINT_PANEL, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (res) {
        var tipo = res.headers.get('content-type') || '';
        if (!res.ok || tipo.indexOf('application/json') === -1) throw new Error('sin respuesta util');
        return res.json();
      })
      .then(function (datos) { if (turno === cargaDelPanel) pintarPanel(datos); })
      .catch(function () {
        if (turno !== cargaDelPanel) return;
        panelLista.textContent = '';
        panelMarcar.hidden = true;
        panelEstado.textContent = 'No se pudieron cargar. Abre la lista completa.';
        panelEstado.hidden = false;
      });
  }

  function pintarPanel(datos) {
    csrfPanel = typeof datos.csrf === 'string' ? datos.csrf : '';
    urlMarcarTodas = rutaPropia(datos.marcar_todas_url) ? datos.marcar_todas_url : '';
    if (rutaPropia(datos.todas_url)) panelPie.href = datos.todas_url;
    ponerConteo(datos.no_leidas);
    panelLista.textContent = '';
    var filas = Array.isArray(datos.notificaciones) ? datos.notificaciones : [];
    filas.forEach(function (n) {
      var nivel = NIVELES_DE_NOTIFICACION[n.nivel] || 'info';
      var fila = el('li', 'aviso-panel__fila' + (n.leida ? '' : ' aviso-panel__fila--nueva'));
      var marca = el('span', 'aviso-reservas__marca aviso-reservas__marca--' + nivel);
      marca.setAttribute('aria-hidden', 'true');
      var cuerpo = el('div', 'aviso-panel__cuerpo');
      cuerpo.appendChild(el('p', 'aviso-panel__texto', n.texto));
      if (n.motivo) cuerpo.appendChild(el('p', 'aviso-panel__motivo', n.motivo));
      var pie = el('p', 'aviso-panel__meta', hora(n.creado_en));
      if (rutaPropia(n.url)) {
        var enlace = el('a', 'aviso-panel__enlace', n.enlace_texto || 'Ver');
        enlace.href = n.url;
        pie.appendChild(document.createTextNode(' · '));
        pie.appendChild(enlace);
      }
      cuerpo.appendChild(pie);
      fila.appendChild(marca);
      fila.appendChild(cuerpo);
      panelLista.appendChild(fila);
    });
    panelEstado.textContent = 'No hay notificaciones.';
    panelEstado.hidden = filas.length > 0;
    panelMarcar.hidden = !(Number(datos.no_leidas) > 0) || !urlMarcarTodas;
  }

  function marcarTodasDesdeElPanel() {
    if (!urlMarcarTodas) return;
    panelMarcar.disabled = true;
    fetch(urlMarcarTodas, {
      method: 'POST', credentials: 'same-origin',
      headers: { Accept: 'application/json', 'X-CSRFToken': csrfPanel },
    })
      .then(function (res) { if (!res.ok) throw new Error('no se pudo marcar'); return res.json(); })
      .then(function () { cargarPanel(); })
      .catch(function () {
        panelEstado.textContent = 'No se pudieron marcar como leídas. Intenta de nuevo.';
        panelEstado.hidden = false;
      })
      .then(function () { panelMarcar.disabled = false; });
  }

  document.addEventListener('click', function (evento) {
    if (!panelAbierto) return;
    if (panel.contains(evento.target) || campana.contains(evento.target)) return;
    cerrarPanel(false);
  });
  document.addEventListener('keydown', function (evento) {
    if (panelAbierto && evento.key === 'Escape') cerrarPanel(true);
  });
  window.addEventListener('resize', function () { if (panelAbierto) colocarPanel(); });

  // Lo que paso despues de que la pantalla que lo pidio ya respondio (el correo de asignacion, un reembolso...): el
  // servidor manda el TEXTO de las notificaciones nuevas y aqui salen como tarjetas. La referencia (ultimo id visto)
  // sobrevive a recargar la pagina en sessionStorage: asi, tras guardar y volver a cargar, el primer sondeo ya trae
  // el resultado de lo que se acaba de hacer. Sin ella, abrir una pagina nunca vuelca el historial.
  var NIVELES_DE_NOTIFICACION = { exito: 'success', aviso: 'warning', error: 'error' };

  function leerUltima() {
    if (ultimaNotif !== null) return ultimaNotif;
    try {
      var guardada = window.sessionStorage.getItem(CLAVE_ULTIMA);
      if (guardada !== null && /^[0-9]+$/.test(guardada)) ultimaNotif = Number(guardada);
    } catch (e) { /* sin memoria de sesion: se parte de la referencia del servidor */ }
    return ultimaNotif;
  }

  function guardarUltima(id) {
    ultimaNotif = id;
    try { window.sessionStorage.setItem(CLAVE_ULTIMA, String(id)); } catch (e) { /* sin memoria de sesion */ }
  }

  function leerVistas() {
    if (vistas !== null) return vistas;
    vistas = [];
    try {
      var guardadas = window.sessionStorage.getItem(CLAVE_VISTAS);
      if (guardadas && /^[0-9,]+$/.test(guardadas)) {
        vistas = guardadas.split(',').filter(Boolean).map(Number);
      }
    } catch (e) { /* sin memoria de sesion */ }
    return vistas;
  }

  function agregarVistas(ids) {
    var lista = leerVistas();
    ids.forEach(function (id) { if (lista.indexOf(id) === -1) lista.push(id); });
    while (lista.length > MAXIMO_VISTAS) lista.shift();
    try { window.sessionStorage.setItem(CLAVE_VISTAS, lista.join(',')); } catch (e) { /* sin memoria de sesion */ }
  }

  function mostrarNotificaciones(datos) {
    if (typeof datos.notif_ultima !== 'number') return;
    // Primera consulta de esta pestana: lo creado hace un momento no es "nuevo", solo se marca como visto.
    if (Array.isArray(datos.notif_recientes) && datos.notif_recientes.length) agregarVistas(datos.notif_recientes);
    var nuevas = Array.isArray(datos.notificaciones_nuevas) ? datos.notificaciones_nuevas : [];
    var lugar = asegurarContenedor();
    var total = Number(datos.notificaciones_nuevas_total) || nuevas.length;
    nuevas.slice().reverse().forEach(function (n) {
      var nivel = NIVELES_DE_NOTIFICACION[n.nivel] || 'info';
      var texto = n.motivo ? n.texto + ' ' + n.motivo : n.texto;
      var enlace = rutaPropia(n.url) ? n.url : null;
      var tarjeta = crearAviso(TITULOS_DE_AVISO[nivel], texto, enlace, n.enlace_texto || 'Ver', nivel);
      lugar.insertBefore(tarjeta, lugar.firstChild);
      if (nivel === 'success') programarCierre(tarjeta, SEGUNDOS_DE_EXITO);
    });
    if (total > nuevas.length) {
      var resto = total - nuevas.length;
      lugar.insertBefore(
        crearAviso('+' + resto + (resto === 1 ? ' notificación más' : ' notificaciones más'), '',
          datos.notificaciones_url, 'Ver notificaciones', 'info'),
        lugar.firstChild
      );
    }
    recortar(lugar);
    agregarVistas(nuevas.map(function (n) { return n.id; }).filter(function (id) { return typeof id === 'number'; }));
    guardarUltima(datos.notif_ultima);
  }

  function consultar() {
    var partes = [];
    if (desde) partes.push('desde=' + encodeURIComponent(desde));
    var referencia = leerUltima();
    if (referencia !== null) {
      partes.push('notif=' + referencia);
      var ya = leerVistas();
      if (ya.length) partes.push('vistas=' + ya.join(','));
    }
    var url = partes.length ? ENDPOINT + '?' + partes.join('&') : ENDPOINT;
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
        mostrarNotificaciones(datos);
        if (datos.total > 0) mostrar(datos);
        ofrecerAvisosDelSistema();
      })
      .catch(function () {
        // Sesion vencida (el admin responde con la pantalla de login) o backend caido: se reintenta unas veces y
        // se calla. No hay nada util que decirle a quien esta trabajando.
        fallos += 1;
        if (fallos >= FALLOS_PARA_PARAR) {
          parar();
          avisarQueSePerdioLaConexion();
        }
      });
  }

  // Tras varios fallos seguidos el sondeo se detiene (sesion vencida, backend caido, sin red): sin este aviso la persona
  // creeria que sigue enterandose de las reservas nuevas.
  function avisarQueSePerdioLaConexion() {
    var lugar = asegurarContenedor();
    lugar.insertBefore(
      crearAviso(
        TITULOS_DE_AVISO.warning,
        'Dejaron de llegar los avisos nuevos (la sesión venció o no hay conexión). Recarga la página para volver a recibirlos.',
        null, '', 'warning', { texto: 'Recargar', hacer: function () { window.location.reload(); } }
      ),
      lugar.firstChild
    );
    recortar(lugar);
    avisarAlSistema('Se detuvieron los avisos', 'La sesión venció o no hay conexión. Recarga la página del panel.', 'avisos-detenidos');
  }

  // El ritmo lo marca un worker: el temporizador de una pestana oculta lo frenan los navegadores (una vez por minuto o
  // menos), el de un worker no. Sin Worker (o con una politica que lo impida) se usa el temporizador normal.
  function crearTemporizador() {
    try {
      var fuente = 'var t=setInterval(function(){postMessage(1)},' + INTERVALO_MS + ');onmessage=function(){clearInterval(t)}';
      var direccion = window.URL.createObjectURL(new window.Blob([fuente], { type: 'text/javascript' }));
      var hilo = new window.Worker(direccion);
      window.URL.revokeObjectURL(direccion);
      hilo.onmessage = function () { consultar(); };
      return hilo;
    } catch (e) {
      return null;
    }
  }

  function arrancar() {
    if (timer || worker) return;
    worker = crearTemporizador();
    if (!worker) timer = window.setInterval(consultar, INTERVALO_MS);
  }

  function parar() {
    if (worker) {
      worker.postMessage('parar');
      worker.terminate();
      worker = null;
    }
    window.clearInterval(timer);
    timer = null;
  }

  // Ya no se pausa al ocultar la pestana: es justo cuando mas sirve el aviso. Al volver se pregunta de inmediato.
  document.addEventListener('visibilitychange', function () {
    if (sinSesion || document.hidden) return;
    restaurarTitulo();
    if (fallos < FALLOS_PARA_PARAR) {
      consultar();
      arrancar();
    }
  });
  window.addEventListener('focus', restaurarTitulo);

  function iniciar() {
    convertirAvisosDeDjango();
    if (sinSesion) return;
    ['click', 'keydown', 'touchstart'].forEach(function (evento) {
      document.addEventListener(evento, desbloquearAudio, { passive: true });
    });
    asegurarBotonSonido();
    consultar();
    arrancar();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
