// Turnstile en el inicio de sesion del backoffice (apps/cuentas/login.py).
// El script de Cloudflare se carga en modo explicito y llama a esta funcion cuando esta listo: aqui el widget se
// mueve DENTRO del formulario, justo antes del boton de entrar, para que `cf-turnstile-response` viaje con el POST.
(function () {
  'use strict';

  var ESPERA_MS = 10000;

  function colocar(caja) {
    var formulario = document.getElementById('login-form');
    if (!formulario) return;
    var boton = formulario.querySelector('.submit-row');
    var bloque = boton && boton.parentNode !== formulario ? boton.parentNode : boton;
    if (bloque && bloque.parentNode === formulario) {
      formulario.insertBefore(caja, bloque);
    } else {
      formulario.appendChild(caja);
    }
    caja.hidden = false;
  }

  // Sin la verificacion no se puede entrar: si Cloudflare no carga (bloqueador de anuncios, sin conexion), la persona
  // tiene que enterarse en vez de ver un formulario al que "no le pasa nada".
  function avisarQueNoCargo() {
    var caja = document.getElementById('login-turnstile');
    if (!caja || caja.querySelector('iframe')) return;
    colocar(caja);
    caja.textContent = 'No se pudo cargar la verificación de seguridad. Revisa tu conexión, desactiva el bloqueador ' +
      'de anuncios para este sitio y recarga la página.';
  }

  window.turnstileLoginNoCargo = avisarQueNoCargo;

  window.cargaTurnstileLogin = function () {
    var caja = document.getElementById('login-turnstile');
    if (!caja || !window.turnstile) return;
    colocar(caja);
    window.turnstile.render(caja, { sitekey: caja.getAttribute('data-sitekey'), action: 'login' });
  };

  window.setTimeout(avisarQueNoCargo, ESPERA_MS);
})();
