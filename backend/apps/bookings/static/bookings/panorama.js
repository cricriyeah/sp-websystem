/* Recuerda si el panorama de la agenda quedo abierto o cerrado.
 *
 * El <details> abre y cierra solo, sin JavaScript. Esto es lo unico que hace
 * falta: la agenda recarga cada vez que se guarda una asignacion o se cambia de
 * filtro, y sin esto volveria a su estado inicial cada vez.
 *
 * Abierto la primera vez, para que se descubra; despues manda la preferencia.
 */
(function () {
  'use strict';

  var CLAVE = 'agenda:panorama-abierto';

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.querySelector('[data-panorama]');
    if (!panel) return;

    var guardado = window.localStorage.getItem(CLAVE);
    if (guardado !== null) panel.open = guardado === '1';

    panel.addEventListener('toggle', function () {
      window.localStorage.setItem(CLAVE, panel.open ? '1' : '0');
    });
  });
})();
