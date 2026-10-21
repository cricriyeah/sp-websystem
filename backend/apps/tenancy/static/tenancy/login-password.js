// El ojo del login: muestra u oculta la contrasena mientras se escribe.
(function () {
  function iniciar() {
    var entrada = document.getElementById('id_password');
    if (!entrada || entrada.dataset.ojo) return;
    entrada.dataset.ojo = '1';

    var envoltura = document.createElement('div');
    envoltura.style.position = 'relative';
    entrada.parentNode.insertBefore(envoltura, entrada);
    envoltura.appendChild(entrada);
    entrada.style.paddingRight = '3rem';

    var boton = document.createElement('button');
    boton.type = 'button';
    boton.setAttribute('aria-pressed', 'false');
    boton.setAttribute('aria-label', 'Mostrar contraseña');
    boton.style.cssText = 'position:absolute;top:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;width:3rem;background:none;border:0;cursor:pointer;color:inherit;opacity:.7';
    var icono = document.createElement('span');
    icono.className = 'material-symbols-outlined';
    icono.setAttribute('aria-hidden', 'true');
    icono.textContent = 'visibility';
    boton.appendChild(icono);
    envoltura.appendChild(boton);

    boton.addEventListener('click', function () {
      var visible = entrada.type === 'password';
      entrada.type = visible ? 'text' : 'password';
      icono.textContent = visible ? 'visibility_off' : 'visibility';
      boton.setAttribute('aria-pressed', visible ? 'true' : 'false');
      boton.setAttribute('aria-label', visible ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
