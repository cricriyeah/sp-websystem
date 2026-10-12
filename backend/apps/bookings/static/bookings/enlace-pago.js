/**
 * Interactividad minima para la pantalla de generacion de enlace de pago por WhatsApp.
 *
 * 1. Copia la URL al portapapeles con navigator.clipboard y fallback clasico.
 * 2. Muestra u oculta los campos de fecha, hora y personas segun se elija un servicio o un paquete.
 */
(function () {
    'use strict';

    function actualizarVisibilidadCampos() {
        var selectProducto = document.getElementById('id_producto');
        if (!selectProducto) {
            return;
        }

        var valor = selectProducto.value || '';
        var esPaquete = valor.indexOf('paquete:') === 0;

        var camposServicio = document.querySelectorAll('[data-campo-servicio]');
        for (var i = 0; i < camposServicio.length; i++) {
            camposServicio[i].style.display = esPaquete ? 'none' : '';
        }
    }

    function obtenerMapaLimites() {
        var script = document.getElementById('limites-servicios');
        if (!script) {
            return {};
        }
        try {
            return JSON.parse(script.textContent) || {};
        } catch (e) {
            return {};
        }
    }

    var mapaLimites = obtenerMapaLimites();
    var inputHoraOriginal = null;

    function actualizarLimites() {
        var selectProducto = document.getElementById('id_producto');
        if (!selectProducto) {
            return;
        }

        var valor = selectProducto.value || '';
        var limites = mapaLimites[valor];

        // 1. Número de personas
        var inputPersonas = document.getElementById('id_personas');
        if (inputPersonas) {
            var contenedorPersonas = inputPersonas.closest('[data-campo-servicio]') || inputPersonas.parentElement;
            var ayudaPersonas = contenedorPersonas ? contenedorPersonas.querySelector('.enlace-pago-ayuda') : null;
            if (ayudaPersonas && !ayudaPersonas.hasAttribute('data-ayuda-original')) {
                ayudaPersonas.setAttribute('data-ayuda-original', ayudaPersonas.textContent);
            }

            if (limites) {
                inputPersonas.min = limites.min_personas || 1;
                inputPersonas.max = limites.max_personas;
                if (ayudaPersonas) {
                    ayudaPersonas.textContent = 'De ' + (limites.min_personas || 1) + ' a ' + limites.max_personas + ' personas';
                }
            } else {
                inputPersonas.min = 1;
                inputPersonas.removeAttribute('max');
                if (ayudaPersonas && ayudaPersonas.hasAttribute('data-ayuda-original')) {
                    ayudaPersonas.textContent = ayudaPersonas.getAttribute('data-ayuda-original');
                }
            }
        }

        // 2. Hora
        var elHora = document.getElementById('id_hora');
        if (elHora) {
            var contenedorHora = elHora.closest('[data-campo-servicio]') || elHora.parentElement;
            var ayudaHora = contenedorHora ? contenedorHora.querySelector('.enlace-pago-ayuda') : null;
            if (ayudaHora && !ayudaHora.hasAttribute('data-ayuda-original')) {
                ayudaHora.setAttribute('data-ayuda-original', ayudaHora.textContent);
            }

            if (limites) {
                if (limites.apertura && limites.cierre) {
                    if (ayudaHora) {
                        ayudaHora.textContent = 'Entre ' + limites.apertura + ' y ' + limites.cierre;
                    }
                } else if (!limites.pide_hora) {
                    if (ayudaHora) {
                        ayudaHora.textContent = 'No requiere hora de salida';
                    }
                }

                if (limites.horas && limites.horas.length > 0) {
                    var valorHoraActual = elHora.value || '';
                    if (elHora.tagName === 'INPUT') {
                        inputHoraOriginal = elHora;
                        var selectHora = document.createElement('select');
                        selectHora.name = elHora.name;
                        selectHora.id = 'id_hora';
                        selectHora.className = elHora.className;

                        var optVacia = document.createElement('option');
                        optVacia.value = '';
                        optVacia.textContent = '---------';
                        selectHora.appendChild(optVacia);

                        for (var j = 0; j < limites.horas.length; j++) {
                            var h = limites.horas[j];
                            var opt = document.createElement('option');
                            opt.value = h;
                            opt.textContent = h;
                            if (h === valorHoraActual) {
                                opt.selected = true;
                            }
                            selectHora.appendChild(opt);
                        }
                        elHora.parentNode.replaceChild(selectHora, elHora);
                    } else if (elHora.tagName === 'SELECT') {
                        elHora.innerHTML = '';
                        var optDef = document.createElement('option');
                        optDef.value = '';
                        optDef.textContent = '---------';
                        elHora.appendChild(optDef);

                        for (var k = 0; k < limites.horas.length; k++) {
                            var horaOpt = limites.horas[k];
                            var o = document.createElement('option');
                            o.value = horaOpt;
                            o.textContent = horaOpt;
                            if (horaOpt === valorHoraActual) {
                                o.selected = true;
                            }
                            elHora.appendChild(o);
                        }
                    }
                } else {
                    if (elHora.tagName === 'SELECT' && inputHoraOriginal) {
                        inputHoraOriginal.value = elHora.value || '';
                        elHora.parentNode.replaceChild(inputHoraOriginal, elHora);
                        elHora = inputHoraOriginal;
                    }
                    if (elHora.tagName === 'INPUT') {
                        if (limites.apertura && limites.cierre) {
                            elHora.min = limites.apertura;
                            elHora.max = limites.cierre;
                            elHora.step = 900;
                        } else {
                            elHora.removeAttribute('min');
                            elHora.removeAttribute('max');
                            elHora.removeAttribute('step');
                        }
                    }
                }
            } else {
                if (elHora.tagName === 'SELECT' && inputHoraOriginal) {
                    inputHoraOriginal.value = elHora.value || '';
                    elHora.parentNode.replaceChild(inputHoraOriginal, elHora);
                    elHora = inputHoraOriginal;
                }
                if (elHora.tagName === 'INPUT') {
                    elHora.removeAttribute('min');
                    elHora.removeAttribute('max');
                    elHora.removeAttribute('step');
                }
                if (ayudaHora && ayudaHora.hasAttribute('data-ayuda-original')) {
                    ayudaHora.textContent = ayudaHora.getAttribute('data-ayuda-original');
                }
            }
        }
    }

    function alCambiarProducto() {
        actualizarVisibilidadCampos();
        actualizarLimites();
    }

    function inicializarBotonCopiar() {
        var boton = document.getElementById('btn-copiar-enlace');
        var input = document.getElementById('input-enlace-pago');
        if (!boton || !input) {
            return;
        }

        boton.addEventListener('click', function () {
            var url = input.value;
            if (!url) {
                return;
            }

            function feedbackCopiado() {
                var textoOriginal = boton.innerText;
                boton.innerText = '¡Copiado!';
                setTimeout(function () {
                    boton.innerText = textoOriginal;
                }, 2000);
            }

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url)
                    .then(feedbackCopiado)
                    .catch(function () {
                        input.select();
                        try {
                            document.execCommand('copy');
                            feedbackCopiado();
                        } catch (err) {
                            // Si ambos fallan, el texto sigue seleccionado para Ctrl+C manual
                        }
                    });
            } else {
                input.select();
                try {
                    document.execCommand('copy');
                    feedbackCopiado();
                } catch (err) {
                    // Fallback silencioso con texto seleccionado
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            var selectProducto = document.getElementById('id_producto');
            if (selectProducto) {
                selectProducto.addEventListener('change', alCambiarProducto);
                alCambiarProducto();
            }
            inicializarBotonCopiar();
        });
    } else {
        var selectProducto = document.getElementById('id_producto');
        if (selectProducto) {
            selectProducto.addEventListener('change', alCambiarProducto);
            alCambiarProducto();
        }
        inicializarBotonCopiar();
    }
})();
