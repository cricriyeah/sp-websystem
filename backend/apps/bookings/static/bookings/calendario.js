/* Calendario del backoffice: popover de detalle (Semana y Dia) y selector de empresa.

   Sin librerias ni CDN. Cada evento es un enlace a su reserva, asi que sin JavaScript
   todo sigue funcionando (abre la ficha). Con JavaScript, el clic abre un popover con el
   detalle que viaja en un <template> de la pagina; Esc lo cierra y el foco regresa al
   evento. Un clic con Ctrl/Cmd/Mayus o con el boton del medio conserva el enlace normal.
   En menos de 640px el CSS lo vuelve una hoja que sube desde abajo. */
(function () {
  'use strict';

  var selector = document.querySelector('[data-auto-enviar]');
  if (selector) {
    selector.addEventListener('change', function () { selector.form.submit(); });
  }

  var popover = document.getElementById('cal-popover');
  var velo = document.getElementById('cal-velo');
  if (!popover) { return; }

  var abierto = null;

  function cerrar(devolverFoco) {
    if (!abierto) { return; }
    var disparador = abierto;
    abierto = null;
    popover.hidden = true;
    if (velo) { velo.hidden = true; }
    popover.replaceChildren();
    disparador.removeAttribute('aria-expanded');
    if (devolverFoco) { disparador.focus(); }
  }

  function posicionar(disparador) {
    var caja = disparador.getBoundingClientRect();
    var ancho = popover.offsetWidth;
    var izquierda = caja.left + window.pageXOffset;
    var tope = window.pageXOffset + document.documentElement.clientWidth - ancho - 8;
    popover.style.left = Math.max(window.pageXOffset + 8, Math.min(izquierda, tope)) + 'px';
    popover.style.top = (caja.bottom + window.pageYOffset + 6) + 'px';
  }

  function abrir(disparador) {
    var plantilla = document.getElementById(disparador.getAttribute('data-detalle'));
    if (!plantilla) { return; }
    cerrar(false);

    popover.replaceChildren(plantilla.content.cloneNode(true));
    var equis = document.createElement('button');
    equis.type = 'button';
    equis.className = 'cal-det-cerrar';
    equis.setAttribute('aria-label', 'Cerrar');
    equis.textContent = '×';
    equis.addEventListener('click', function () { cerrar(true); });
    popover.appendChild(equis);

    popover.hidden = false;
    if (velo) { velo.hidden = false; }
    posicionar(disparador);
    disparador.setAttribute('aria-expanded', 'true');
    abierto = disparador;

    var primera = popover.querySelector('a, button');
    (primera || popover).focus();
  }

  document.addEventListener('click', function (evento) {
    var disparador = evento.target.closest ? evento.target.closest('[data-detalle]') : null;
    var normal = evento.button === 0 && !evento.ctrlKey && !evento.metaKey && !evento.shiftKey && !evento.altKey;
    if (disparador && normal) {
      evento.preventDefault();
      if (abierto === disparador) { cerrar(true); } else { abrir(disparador); }
      return;
    }
    if (abierto && !popover.contains(evento.target)) { cerrar(false); }
  });

  document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape' && abierto) {
      evento.preventDefault();
      cerrar(true);
    }
  });

  window.addEventListener('resize', function () { cerrar(false); });
})();
