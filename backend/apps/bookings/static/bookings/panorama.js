/* Panorama de la agenda: recuerda si quedo abierto y deja asignar desde el.
 *
 * 1. Abierto o cerrado. El <details> abre y cierra solo, sin JavaScript; esto solo
 *    lo recuerda, porque la agenda recarga cada vez que se guarda una asignacion o
 *    se cambia de filtro. Abierto la primera vez, para que se descubra.
 *
 * 2. Asignar desde la cuadricula. Se toca un viaje sin panga (boton rojo de la fila
 *    "Sin panga"), las pangas libres ese dia donde cabe el grupo se marcan en verde,
 *    y al tocar una se llena el selector de esa reserva en la tabla de abajo. No
 *    guarda: Guardar sigue siendo el boton de la tabla, con su validacion.
 *
 *    Una panga solo se marca si su opcion existe en el selector de la fila: el
 *    servidor ya ofrece ahi nada mas las que estan libres y tienen lugar, asi que el
 *    selector es la fuente de verdad y esto no repite la regla.
 */
(function () {
  'use strict';

  var CLAVE = 'agenda:panorama-abierto';
  var VERDE = '#15803d';
  var ROJO = '#dc2626';

  function recordarApertura(panel) {
    try {
      var guardado = window.localStorage.getItem(CLAVE);
      if (guardado !== null) panel.open = guardado === '1';
      panel.addEventListener('toggle', function () {
        window.localStorage.setItem(CLAVE, panel.open ? '1' : '0');
      });
    } catch (e) {
      /* Sin almacenamiento (ventana privada): se queda como llega. */
    }
  }

  /* El selector de embarcacion de la fila de una reserva, o null. El formset de
   * Django numera las filas (form-0-, form-1-...) y pone el id en un hidden. */
  function selectorDe(reserva) {
    var ids = document.querySelectorAll('input[type="hidden"][name$="-id"]');
    for (var i = 0; i < ids.length; i++) {
      if (ids[i].value === reserva) {
        var prefijo = ids[i].name.slice(0, -2);
        return document.querySelector('select[name="' + prefijo + 'embarcacion"]');
      }
    }
    return null;
  }

  function tieneOpcion(select, valor) {
    for (var i = 0; i < select.options.length; i++) {
      if (select.options[i].value === valor) return true;
    }
    return false;
  }

  function iniciarAsignacion(panel) {
    var ayuda = panel.querySelector('[data-panorama-ayuda]');
    var pendientes = panel.querySelectorAll('[data-pendiente]');
    var celdas = panel.querySelectorAll('[data-celda]');
    if (!pendientes.length) return;

    var elegido = null;

    function decir(texto, color) {
      if (!ayuda) return;
      ayuda.hidden = !texto;
      ayuda.textContent = texto || '';
      ayuda.style.color = color || '';
    }

    /* Lo que se puso en una celda y todavia no se guarda, por reserva, para
     * devolverla a como estaba si se elige otra panga para el mismo viaje. */
    var tentativas = {};

    function limpiarCeldas() {
      for (var i = 0; i < celdas.length; i++) {
        celdas[i].removeAttribute('data-elegible');
        celdas[i].style.outline = '';
        celdas[i].style.background = '';
        celdas[i].style.cursor = '';
        celdas[i].style.opacity = '';
      }
    }

    function revertirTentativa(reserva) {
      var previa = tentativas[reserva];
      if (!previa) return;
      while (previa.celda.firstChild) previa.celda.removeChild(previa.celda.firstChild);
      for (var i = 0; i < previa.hijos.length; i++) previa.celda.appendChild(previa.hijos[i]);
      delete tentativas[reserva];
    }

    function soltar() {
      limpiarCeldas();
      for (var i = 0; i < pendientes.length; i++) {
        pendientes[i].style.background = 'transparent';
        pendientes[i].style.color = ROJO;
      }
      elegido = null;
    }

    function nombreDe(boton) {
      return boton.getAttribute('data-nombre') || boton.textContent.replace(/\s+/g, ' ').trim();
    }

    function elegir(boton) {
      soltar();
      elegido = boton;
      boton.style.background = ROJO;
      boton.style.color = '#fff';

      var reserva = boton.getAttribute('data-reserva');
      var fecha = boton.getAttribute('data-fecha');
      var personas = parseInt(boton.getAttribute('data-personas'), 10);
      var select = selectorDe(reserva);
      var cabe = 0;

      for (var i = 0; i < celdas.length; i++) {
        var celda = celdas[i];
        /* Lo que no sirve se atenua: con 70 celdas, las pocas que si sirven
         * tienen que destacar contra todo lo demas. */
        celda.style.opacity = '0.3';
        if (celda.getAttribute('data-fecha') !== fecha) continue;
        if (celda.hasAttribute('data-ocupada') || celda.hasAttribute('data-fuera')) continue;
        if (celda.querySelector('[data-tentativa]')) continue;
        if (parseInt(celda.getAttribute('data-capacidad'), 10) < personas) continue;
        if (select && !tieneOpcion(select, celda.getAttribute('data-embarcacion'))) continue;
        celda.style.opacity = '';
        celda.setAttribute('data-elegible', '1');
        celda.style.outline = '2px solid ' + VERDE;
        celda.style.outlineOffset = '-2px';
        celda.style.background = 'rgba(21, 128, 61, 0.10)';
        celda.style.cursor = 'pointer';
        cabe++;
      }

      if (!select) {
        decir('Esa reserva no esta en la tabla de abajo (otro filtro o pagina). Cambia el filtro y vuelve a tocarla.', ROJO);
      } else if (!cabe) {
        decir(nombreDe(boton) + ': no hay pangas libres donde quepa ese dia.', ROJO);
      } else {
        decir(nombreDe(boton) + ' — toca una panga marcada en verde.', VERDE);
      }
    }

    function colocar(celda) {
      if (!elegido || !celda.hasAttribute('data-elegible')) return;
      var reserva = elegido.getAttribute('data-reserva');
      var select = selectorDe(reserva);
      if (!select) return;

      select.value = celda.getAttribute('data-embarcacion');
      select.dispatchEvent(new Event('change', { bubbles: true }));

      var fila = select.closest('tr');
      if (fila) {
        fila.style.transition = 'background 0.4s';
        fila.style.background = 'rgba(21, 128, 61, 0.15)';
        window.setTimeout(function () { fila.style.background = ''; }, 1600);
        if (fila.scrollIntoView) fila.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }

      var panga = select.options[select.selectedIndex].textContent.replace(/\s*\(.*$/, '');
      decir(nombreDe(elegido) + ' → ' + panga + '. Falta Guardar.', VERDE);

      /* La celda muestra ya el viaje, en verde y cursiva: asi se ve de un vistazo
       * que hay un cambio sin guardar, sin bajar a la tabla. */
      revertirTentativa(reserva);
      var hijos = [];
      while (celda.firstChild) hijos.push(celda.removeChild(celda.firstChild));
      tentativas[reserva] = { celda: celda, hijos: hijos };
      var marca = document.createElement('span');
      marca.setAttribute('data-tentativa', '1');
      marca.style.color = VERDE;
      marca.style.fontStyle = 'italic';
      marca.textContent = nombreDe(elegido).replace(/\s*·.*$/, '') + ' · sin guardar';
      celda.appendChild(marca);

      limpiarCeldas();
      elegido.style.background = 'transparent';
      elegido.style.color = VERDE;
      elegido.style.borderColor = VERDE;
      elegido = null;
    }

    for (var i = 0; i < pendientes.length; i++) {
      pendientes[i].addEventListener('click', function (evento) {
        evento.preventDefault();
        if (elegido === this) { soltar(); decir(''); } else { elegir(this); }
      });
    }
    for (var j = 0; j < celdas.length; j++) {
      celdas[j].addEventListener('click', function () { colocar(this); });
    }
    document.addEventListener('keydown', function (evento) {
      if (evento.key === 'Escape' && elegido) { soltar(); decir(''); }
    });
  }

  /* Contadores que reaccionan antes de guardar. Valen igual si se asigna desde la
   * cuadricula que desde los selectores de la tabla: miran los selectores, que son
   * lo unico que se guarda.
   *
   *  - "Sin panga (N)" baja con cada viaje al que ya se le puso panga.
   *  - El pie, junto a Guardar, dice cuantos viajes tienen un cambio sin guardar en
   *    vez del conteo de filas, que no informa nada. */
  function iniciarContadores(panel) {
    var guardar = document.querySelector('button[name="_save"]');
    var pie = guardar && guardar.parentElement ? guardar.parentElement.previousElementSibling : null;
    var textoPie = pie ? pie.textContent.replace(/\s+/g, ' ').trim() : '';
    var etiqueta = panel.querySelector('[data-sin-panga]');
    var inicial = etiqueta ? parseInt(etiqueta.getAttribute('data-sin-panga'), 10) : 0;
    var chips = panel.querySelectorAll('[data-pendiente]');
    var selects = document.querySelectorAll('select[name$="-embarcacion"], select[name$="-capitan"]');
    if (!selects.length) return;

    for (var i = 0; i < selects.length; i++) {
      selects[i].setAttribute('data-original', selects[i].value);
    }

    function actualizar() {
      var filas = {};
      for (var i = 0; i < selects.length; i++) {
        if (selects[i].value !== selects[i].getAttribute('data-original')) {
          filas[selects[i].name.split('-').slice(0, 2).join('-')] = true;
        }
      }
      var cambios = Object.keys(filas).length;

      if (pie) {
        pie.textContent = cambios
          ? cambios + (cambios === 1 ? ' cambio sin guardar' : ' cambios sin guardar')
          : textoPie;
        pie.style.color = cambios ? VERDE : '';
        pie.style.fontWeight = cambios ? '600' : '';
      }

      if (etiqueta) {
        var asignados = 0;
        for (var j = 0; j < chips.length; j++) {
          var select = selectorDe(chips[j].getAttribute('data-reserva'));
          if (select && select.value) asignados++;
        }
        var faltan = Math.max(inicial - asignados, 0);
        etiqueta.textContent = faltan ? 'Sin panga (' + faltan + ')' : 'Todos con panga';
        etiqueta.style.color = faltan ? ROJO : VERDE;
      }
    }

    for (var k = 0; k < selects.length; k++) {
      selects[k].addEventListener('change', actualizar);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.querySelector('[data-panorama]');
    if (!panel) return;
    recordarApertura(panel);
    iniciarAsignacion(panel);
    iniciarContadores(panel);
  });
})();
