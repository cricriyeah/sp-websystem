/* Sugerencia automatica de precio total en el formulario de alta de Reserva.
 *
 * Consulta el endpoint `precio-sugerido/` al cambiar servicio/paquete, personas
 * o moneda, y sugiere el monto calculado segun las reglas de tarificacion del checkout.
 * Permite a la vendedora sobreescribir el valor a mano en cualquier momento.
 */
(function () {
  'use strict';

  function iniciar() {
    // Solo aplica en el formulario de alta (/admin/bookings/reserva/add/)
    if (!window.location.pathname.endsWith('/add/')) {
      return;
    }

    var inputPrecio = document.getElementById('id_precio_total');
    if (!inputPrecio) {
      return;
    }

    var elServicio = document.getElementById('id_servicio');
    var elPaquete = document.getElementById('id_paquete');
    var elPersonas = document.getElementById('id_numero_personas');
    var elMoneda = document.getElementById('id_moneda');
    var elFecha = document.getElementById('id_fecha');

    // Si ya trae un valor inicial al cargar (p. ej. tras error de validacion POST), se respeta
    if (inputPrecio.value && inputPrecio.value.trim() !== '') {
      inputPrecio.setAttribute('data-editado', '1');
    }

    // Elemento visual para mostrar la etiqueta de precio sugerido
    var lineaSugerido = document.querySelector('p[data-precio-sugerido]');
    if (!lineaSugerido) {
      lineaSugerido = document.createElement('p');
      lineaSugerido.setAttribute('data-precio-sugerido', '');
      lineaSugerido.style.cssText = 'color:#6b7280; font-size:.8rem; margin-top:.25rem; display:none;';
      if (inputPrecio.nextSibling) {
        inputPrecio.parentNode.insertBefore(lineaSugerido, inputPrecio.nextSibling);
      } else {
        inputPrecio.parentNode.appendChild(lineaSugerido);
      }
    }

    var contadorPeticiones = 0;
    var debounceTimer = null;
    var ultimoPrecioSugerido = null;
    var ultimaEtiquetaSugerida = null;

    function renderizarLinea() {
      var servicioVal = elServicio ? elServicio.value : '';
      var paqueteVal = elPaquete ? elPaquete.value : '';
      var hayServicioOPaquete = Boolean(servicioVal || paqueteVal);

      if (!ultimoPrecioSugerido) {
        // Si precio es null: oculta la linea, o muestra aviso si ya se eligio servicio/paquete
        if (hayServicioOPaquete) {
          lineaSugerido.textContent = 'Sin sugerencia: escribe el precio.';
          lineaSugerido.style.display = 'block';
        } else {
          lineaSugerido.textContent = '';
          lineaSugerido.style.display = 'none';
        }
        return;
      }

      lineaSugerido.textContent = '';
      lineaSugerido.style.display = 'block';

      var texto = document.createTextNode(ultimaEtiquetaSugerida || ('Sugerido: ' + ultimoPrecioSugerido));
      lineaSugerido.appendChild(texto);

      // Si la vendedora edito el campo a mano y su valor difiere del sugerido, ofrecer restaurar
      var fueEditado = inputPrecio.getAttribute('data-editado') === '1';
      var difiere = inputPrecio.value !== ultimoPrecioSugerido;

      if (fueEditado && difiere) {
        var espacio = document.createTextNode(' ');
        var enlace = document.createElement('a');
        enlace.href = '#';
        enlace.textContent = 'usar sugerido';
        enlace.style.cssText = 'color:#2563eb; text-decoration:underline; margin-left:.5rem; cursor:pointer;';
        enlace.addEventListener('click', function (evento) {
          evento.preventDefault();
          inputPrecio.value = ultimoPrecioSugerido;
          inputPrecio.removeAttribute('data-editado');
          renderizarLinea();
        });
        lineaSugerido.appendChild(espacio);
        lineaSugerido.appendChild(enlace);
      }
    }

    function pedirSugerencia() {
      var servicioVal = elServicio ? elServicio.value : '';
      var paqueteVal = elPaquete ? elPaquete.value : '';
      var personasVal = elPersonas ? elPersonas.value : '';
      var monedaVal = elMoneda ? elMoneda.value : '';
      var fechaVal = elFecha ? elFecha.value : '';

      contadorPeticiones += 1;
      var miPeticion = contadorPeticiones;

      // Si no hay servicio ni paquete seleccionado, no se consulta
      if (!servicioVal && !paqueteVal) {
        ultimoPrecioSugerido = null;
        ultimaEtiquetaSugerida = null;
        renderizarLinea();
        return;
      }

      var rutaEndpoint = window.location.pathname.replace(/add\/$/, 'precio-sugerido/');
      var url = new URL(rutaEndpoint, window.location.origin);
      if (servicioVal) url.searchParams.set('servicio', servicioVal);
      if (paqueteVal) url.searchParams.set('paquete', paqueteVal);
      if (personasVal) url.searchParams.set('personas', personasVal);
      if (monedaVal) url.searchParams.set('moneda', monedaVal);
      if (fechaVal) url.searchParams.set('fecha', fechaVal);

      fetch(url.toString(), {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          if (miPeticion !== contadorPeticiones) {
            return; // Descartar respuesta vieja
          }
          ultimoPrecioSugerido = data.precio;
          ultimaEtiquetaSugerida = data.etiqueta;

          if (data.precio !== null && data.precio !== undefined) {
            // Solo auto-rellenar si la usuaria no ha editado el campo manualmente
            if (inputPrecio.getAttribute('data-editado') !== '1') {
              inputPrecio.value = data.precio;
            }
          }
          renderizarLinea();
        })
        .catch(function () {
          // Errores de red o endpoint caido no deben interrumpir el formulario
        });
    }

    function pedirSugerenciaDebounced() {
      if (debounceTimer) {
        clearTimeout(debounceTimer);
      }
      debounceTimer = setTimeout(pedirSugerencia, 300);
    }

    // Registrar cambios manuales en el input de precio
    inputPrecio.addEventListener('input', function () {
      inputPrecio.setAttribute('data-editado', '1');
      renderizarLinea();
    });

    // Escuchar cambios en los campos que determinan la cotizacion
    var camposObservados = [elServicio, elPaquete, elPersonas, elMoneda, elFecha];
    camposObservados.forEach(function (campo) {
      if (campo) {
        campo.addEventListener('change', pedirSugerenciaDebounced);
        campo.addEventListener('input', pedirSugerenciaDebounced);
      }
    });

    // Si django.jQuery esta presente (widgets autocomplete de select2), enlazar tambien el evento change
    if (window.django && window.django.jQuery) {
      window.django.jQuery('#id_servicio, #id_paquete, #id_numero_personas, #id_moneda, #id_fecha')
        .on('change', pedirSugerenciaDebounced);
    }

    // Consulta inicial en caso de que el formulario ya traiga campos precargados (p. ej. servicio por defecto)
    pedirSugerencia();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
