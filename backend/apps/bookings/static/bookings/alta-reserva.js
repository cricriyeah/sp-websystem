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

    var scriptIds = document.getElementById('servicios-transporte-ids');
    var serviciosTransporteIds = [];
    if (scriptIds) {
      try {
        serviciosTransporteIds = JSON.parse(scriptIds.textContent);
      } catch (e) {
        serviciosTransporteIds = [];
      }
    }

    var scriptLimites = document.getElementById('limites-servicios');
    var mapaLimitesServicios = {};
    if (scriptLimites) {
      try {
        mapaLimitesServicios = JSON.parse(scriptLimites.textContent) || {};
      } catch (e) {
        mapaLimitesServicios = {};
      }
    }

    var elTipoTraslado = document.getElementById('id_detalle_transporte-0-tipo_traslado');
    var elZona = document.getElementById('id_detalle_transporte-0-zona');

    function obtenerGrupoDetalleTransporte() {
      var grupo = document.getElementById('detalle_transporte-group');
      if (grupo) {
        return grupo;
      }
      var totalForms = document.getElementById('id_detalle_transporte-TOTAL_FORMS');
      if (totalForms) {
        return totalForms.closest('.inline-group') || totalForms.closest('.js-inline-admin-formset') || totalForms.closest('fieldset') || totalForms.parentElement;
      }
      return null;
    }

    function esServicioTransporte(idServicio) {
      if (!idServicio) {
        return false;
      }
      return serviciosTransporteIds.some(function (id) {
        return String(id) === String(idServicio);
      });
    }

    function actualizarVisibilidadDetalleTransporte() {
      var grupo = obtenerGrupoDetalleTransporte();
      if (!grupo) {
        return;
      }
      var servicioVal = elServicio ? elServicio.value : '';
      var esTransporte = esServicioTransporte(servicioVal);
      grupo.style.display = esTransporte ? '' : 'none';
    }

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

      if (esServicioTransporte(servicioVal)) {
        var elTipoActual = elTipoTraslado || document.getElementById('id_detalle_transporte-0-tipo_traslado');
        var elZonaActual = elZona || document.getElementById('id_detalle_transporte-0-zona');
        var tipoTrasladoVal = elTipoActual ? elTipoActual.value : '';
        var zonaVal = elZonaActual ? elZonaActual.value : '';
        if (tipoTrasladoVal) url.searchParams.set('tipo_traslado', tipoTrasladoVal);
        if (zonaVal) url.searchParams.set('zona', zonaVal);
        if (personasVal) url.searchParams.set('personas_traslado', personasVal);
      }

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
    var camposObservados = [elServicio, elPaquete, elPersonas, elMoneda, elFecha, elTipoTraslado, elZona];
    camposObservados.forEach(function (campo) {
      if (campo) {
        campo.addEventListener('change', pedirSugerenciaDebounced);
        campo.addEventListener('input', pedirSugerenciaDebounced);
      }
    });

    var elHora = document.getElementById('id_hora');

    function obtenerElementoAyuda(input) {
      if (!input) return null;
      var contenedor = input.closest('.form-row') || input.closest('div') || input.parentElement;
      var ayuda = contenedor ? (contenedor.querySelector('.help') || contenedor.querySelector('[data-ayuda-limite]')) : null;
      if (!ayuda && contenedor) {
        ayuda = document.createElement('p');
        ayuda.setAttribute('data-ayuda-limite', '');
        ayuda.className = 'help text-xs text-font-subtle mt-1';
        if (input.nextSibling) {
          input.parentNode.insertBefore(ayuda, input.nextSibling);
        } else {
          input.parentNode.appendChild(ayuda);
        }
      }
      return ayuda;
    }

    function actualizarLimitesServicio() {
      var idServicio = elServicio ? elServicio.value : '';
      var limites = idServicio ? mapaLimitesServicios[idServicio] : null;

      // 1. Número de personas (#id_numero_personas)
      if (elPersonas) {
        var ayudaPersonas = obtenerElementoAyuda(elPersonas);
        if (ayudaPersonas && !ayudaPersonas.hasAttribute('data-ayuda-original')) {
          ayudaPersonas.setAttribute('data-ayuda-original', ayudaPersonas.textContent || '');
        }

        if (limites) {
          elPersonas.min = limites.min_personas || 1;
          elPersonas.max = limites.max_personas;
          if (ayudaPersonas) {
            ayudaPersonas.textContent = 'De ' + (limites.min_personas || 1) + ' a ' + limites.max_personas + ' personas';
            ayudaPersonas.style.display = '';
          }
        } else {
          elPersonas.min = 1;
          elPersonas.removeAttribute('max');
          if (ayudaPersonas) {
            var origP = ayudaPersonas.getAttribute('data-ayuda-original') || '';
            ayudaPersonas.textContent = origP;
            if (!origP && ayudaPersonas.hasAttribute('data-ayuda-limite')) {
              ayudaPersonas.style.display = 'none';
            }
          }
        }
      }

      // 2. Hora (#id_hora)
      if (elHora) {
        var ayudaHora = obtenerElementoAyuda(elHora);
        if (ayudaHora && !ayudaHora.hasAttribute('data-ayuda-original')) {
          ayudaHora.setAttribute('data-ayuda-original', ayudaHora.textContent || '');
        }

        if (limites) {
          if (limites.apertura && limites.cierre) {
            elHora.min = limites.apertura;
            elHora.max = limites.cierre;
            if (ayudaHora) {
              ayudaHora.textContent = 'Entre ' + limites.apertura + ' y ' + limites.cierre;
              ayudaHora.style.display = '';
            }
          } else if (!limites.pide_hora) {
            elHora.removeAttribute('min');
            elHora.removeAttribute('max');
            if (ayudaHora) {
              ayudaHora.textContent = 'No requiere hora de salida';
              ayudaHora.style.display = '';
            }
          } else {
            elHora.removeAttribute('min');
            elHora.removeAttribute('max');
          }
        } else {
          elHora.removeAttribute('min');
          elHora.removeAttribute('max');
          if (ayudaHora) {
            var origH = ayudaHora.getAttribute('data-ayuda-original') || '';
            ayudaHora.textContent = origH;
            if (!origH && ayudaHora.hasAttribute('data-ayuda-limite')) {
              ayudaHora.style.display = 'none';
            }
          }
        }
      }
    }

    if (elServicio) {
      elServicio.addEventListener('change', actualizarVisibilidadDetalleTransporte);
      elServicio.addEventListener('change', actualizarLimitesServicio);
    }

    // Si django.jQuery esta presente (widgets autocomplete de select2), enlazar tambien el evento change
    if (window.django && window.django.jQuery) {
      window.django.jQuery('#id_servicio, #id_paquete, #id_numero_personas, #id_moneda, #id_fecha, #id_detalle_transporte-0-tipo_traslado, #id_detalle_transporte-0-zona')
        .on('change', pedirSugerenciaDebounced);
      window.django.jQuery('#id_servicio').on('change', actualizarVisibilidadDetalleTransporte);
      window.django.jQuery('#id_servicio').on('change', actualizarLimitesServicio);
    }

    actualizarVisibilidadDetalleTransporte();
    actualizarLimitesServicio();

    // Consulta inicial en caso de que el formulario ya traiga campos precargados (p. ej. servicio por defecto)
    pedirSugerencia();

    // Toggle de visibilidad de monto_recibido segun opcion elegida en ya_pago
    function iniciarVisibilidadMontoRecibido() {
      var inputMonto = document.getElementById('id_monto_recibido');
      var contenedorMonto = document.querySelector('.field-monto_recibido') ||
        (inputMonto ? (inputMonto.closest('.form-row') || inputMonto.parentElement) : null);

      if (!contenedorMonto) {
        return;
      }

      function actualizarVisibilidadMonto() {
        var radioSeleccionado = document.querySelector('input[name="ya_pago"]:checked');
        var esAnticipo = radioSeleccionado && radioSeleccionado.value === 'anticipo_transferencia';
        contenedorMonto.style.display = esAnticipo ? '' : 'none';
      }

      var radiosYaPago = document.querySelectorAll('input[name="ya_pago"]');
      radiosYaPago.forEach(function (radio) {
        radio.addEventListener('change', actualizarVisibilidadMonto);
      });

      document.addEventListener('change', function (evento) {
        if (evento.target && evento.target.name === 'ya_pago') {
          actualizarVisibilidadMonto();
        }
      });

      actualizarVisibilidadMonto();
    }

    iniciarVisibilidadMontoRecibido();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
