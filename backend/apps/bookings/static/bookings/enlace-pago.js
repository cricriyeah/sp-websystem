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
                selectProducto.addEventListener('change', actualizarVisibilidadCampos);
                actualizarVisibilidadCampos();
            }
            inicializarBotonCopiar();
        });
    } else {
        var selectProducto = document.getElementById('id_producto');
        if (selectProducto) {
            selectProducto.addEventListener('change', actualizarVisibilidadCampos);
            actualizarVisibilidadCampos();
        }
        inicializarBotonCopiar();
    }
})();
