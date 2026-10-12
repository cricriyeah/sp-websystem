/* Panorama de la agenda: recuerda si quedo abierto y deja asignar desde el.
 *
 * 1. Abierto o cerrado. El <details> abre y cierra solo, sin JavaScript; esto solo
 *    lo recuerda, porque la agenda recarga cada vez que se guarda una asignacion o
 *    se cambia de filtro. Abierto la primera vez, para que se descubra.
 *
 * 2. Asignar desde la cuadricula. Se toca un viaje sin panga (boton rojo de la fila
 *    "Sin panga"), las pangas libres ese dia donde cabe el grupo se marcan en verde,
 *    el resto se atenua, y al tocar una el viaje viaja hasta ella y se llena el
 *    selector de su fila. No guarda: Guardar sigue siendo el boton de la tabla.
 *    Tocar de nuevo el viaje ya colocado (o su celda) lo deshace.
 *
 *    Una panga solo se marca si su opcion existe en el selector de la fila: el
 *    servidor ya ofrece ahi nada mas las que estan libres y tienen lugar, asi que el
 *    selector es la fuente de verdad y esto no repite la regla.
 *
 * 3. Contadores y avisos antes de guardar: "Sin panga (N)", el pie junto a Guardar y
 *    una barra en las filas con cambio. Tras guardar, lo guardado destella en verde.
 *
 * Movimiento: solo explica lo que acaba de pasar (de donde salio el viaje y a donde
 * fue) y nunca retiene al usuario. El estado cambia primero y la animacion va
 * despues, asi que tocar otra cosa a medio vuelo no espera. Todo dura menos de
 * 400 ms, usa solo transform y opacity, y con `prefers-reduced-motion` se queda en
 * fundidos.
 */
(function () {
  'use strict';

  var CLAVE = 'agenda:panorama-abierto';
  var CLAVE_GUARDADO = 'agenda:guardado';
  var VERDE = '#15803d';
  var ROJO = '#dc2626';
  var GRIS = '#6b7280';
  /* Casi un resorte criticamente amortiguado: arranca rapido y asienta sin rebote.
   * No hay gesto con impulso, asi que rebotar estaria de mas. */
  var SUAVE = 'cubic-bezier(0.22, 1, 0.36, 1)';

  var sinMovimiento = !!(window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  /* Animacion nativa. Con "reducir movimiento" se queda solo con opacidad y color:
   * se sigue viendo que cambio, pero nada se desplaza. Devuelve null si no anima. */
  function animar(el, cuadros, opciones) {
    if (!el || !el.animate) return null;
    var usar = cuadros;
    if (sinMovimiento) {
      usar = [];
      var hay = false;
      for (var i = 0; i < cuadros.length; i++) {
        var c = {};
        if ('opacity' in cuadros[i]) { c.opacity = cuadros[i].opacity; hay = true; }
        if ('backgroundColor' in cuadros[i]) { c.backgroundColor = cuadros[i].backgroundColor; hay = true; }
        if ('offset' in cuadros[i]) c.offset = cuadros[i].offset;
        usar.push(c);
      }
      if (!hay) return null;
    }
    var config = { easing: SUAVE, duration: 250 };
    for (var k in opciones) if (Object.prototype.hasOwnProperty.call(opciones, k)) config[k] = opciones[k];
    return el.animate(usar, config);
  }

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

    /* Lo que se puso en una celda y todavia no se guarda, por reserva: la celda, lo
     * que tenia y el boton del viaje. Sirve para deshacer. */
    var tentativas = {};

    var i;
    for (i = 0; i < pendientes.length; i++) {
      pendientes[i].setAttribute('data-texto', pendientes[i].textContent.replace(/\s+/g, ' ').trim());
    }

    function decir(texto, color) {
      if (!ayuda) return;
      ayuda.hidden = !texto;
      ayuda.textContent = texto || '';
      ayuda.style.color = color || '';
    }

    function limpiarCeldas() {
      for (var c = 0; c < celdas.length; c++) {
        celdas[c].removeAttribute('data-elegible');
        celdas[c].style.boxShadow = '';
        celdas[c].style.background = '';
        celdas[c].style.cursor = '';
        celdas[c].style.opacity = '';
      }
    }

    function pintarPendiente(boton) {
      boton.removeAttribute('data-asignado');
      boton.style.background = 'transparent';
      boton.style.color = ROJO;
      boton.style.borderColor = ROJO;
      boton.style.borderStyle = 'solid';
      boton.style.fontWeight = '600';
      boton.textContent = boton.getAttribute('data-texto');
    }

    function pintarElegido(boton) {
      boton.style.background = ROJO;
      boton.style.color = '#fff';
    }

    function pintarAsignado(boton, panga) {
      boton.setAttribute('data-asignado', '1');
      boton.style.background = 'transparent';
      boton.style.color = GRIS;
      boton.style.borderColor = '#9ca3af';
      boton.style.borderStyle = 'dashed';
      boton.style.fontWeight = '500';
      boton.textContent = '✓ ' + panga;
      boton.title = boton.getAttribute('data-texto') + ' → ' + panga + ' (sin guardar) — toca para deshacer';
    }

    function soltar() {
      panel.removeAttribute('data-asignando');
      limpiarCeldas();
      for (var p = 0; p < pendientes.length; p++) {
        if (!pendientes[p].hasAttribute('data-asignado')) pintarPendiente(pendientes[p]);
      }
      elegido = null;
    }

    function nombreDe(boton) {
      return boton.getAttribute('data-texto');
    }

    function elegir(boton) {
      soltar();
      elegido = boton;
      panel.setAttribute('data-asignando', '1');
      pintarElegido(boton);

      var reserva = boton.getAttribute('data-reserva');
      var fecha = boton.getAttribute('data-fecha');
      var personas = parseInt(boton.getAttribute('data-personas'), 10);
      var select = selectorDe(reserva);
      var cabe = 0;

      for (var c = 0; c < celdas.length; c++) {
        var celda = celdas[c];
        /* Lo que no sirve se atenua: con 70 celdas, las pocas que si sirven
         * tienen que destacar contra todo lo demas. La transicion va en CSS. */
        celda.style.opacity = '0.3';
        if (celda.getAttribute('data-fecha') !== fecha) continue;
        if (celda.hasAttribute('data-ocupada') || celda.hasAttribute('data-fuera')) continue;
        if (celda.querySelector('[data-tentativa]')) continue;
        if (parseInt(celda.getAttribute('data-capacidad'), 10) < personas) continue;
        if (select && !tieneOpcion(select, celda.getAttribute('data-embarcacion'))) continue;
        celda.style.opacity = '';
        celda.setAttribute('data-elegible', '1');
        celda.style.boxShadow = 'inset 0 0 0 2px ' + VERDE;
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

    /* El viaje sale de su boton y llega a la celda: asi se ve a donde fue, en vez de
     * desaparecer de un sitio y aparecer en otro. Es una copia que vuela y se
     * descarta; el estado ya cambio antes de empezar y no espera a la animacion. */
    function vuelo(boton, desde, hasta, marca, alTerminar) {
      var fueraDePantalla = hasta.bottom < 0 || hasta.top > window.innerHeight;
      if (sinMovimiento || fueraDePantalla || !boton.animate) {
        animar(marca, [{ opacity: 0 }, { opacity: 1 }], { duration: 200 });
        alTerminar();
        return;
      }

      var fantasma = boton.cloneNode(true);
      fantasma.removeAttribute('data-pendiente');
      fantasma.style.cssText = boton.style.cssText;
      fantasma.style.position = 'fixed';
      fantasma.style.left = desde.left + 'px';
      fantasma.style.top = desde.top + 'px';
      fantasma.style.width = desde.width + 'px';
      fantasma.style.height = desde.height + 'px';
      fantasma.style.margin = '0';
      fantasma.style.pointerEvents = 'none';
      fantasma.style.zIndex = '10000';
      fantasma.style.transition = 'none';
      document.body.appendChild(fantasma);

      var dx = hasta.left + 6 - desde.left;
      var dy = hasta.top + (hasta.height - desde.height) / 2 - desde.top;
      var vuela = fantasma.animate([
        { transform: 'translate(0, 0)', opacity: 1 },
        { transform: 'translate(' + dx + 'px, ' + dy + 'px)', opacity: 1, offset: 0.75 },
        { transform: 'translate(' + dx + 'px, ' + dy + 'px)', opacity: 0 }
      ], { duration: 360, easing: SUAVE, fill: 'forwards' });

      /* La marca de la celda aparece justo cuando llega la copia. */
      animar(marca, [{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: 200, fill: 'backwards' });

      var terminado = false;
      function terminar() {
        if (terminado) return;
        terminado = true;
        if (fantasma.parentNode) fantasma.parentNode.removeChild(fantasma);
        alTerminar();
      }
      vuela.onfinish = terminar;
      vuela.oncancel = terminar;
    }

    function revertirCelda(reserva) {
      var previa = tentativas[reserva];
      if (!previa) return;
      while (previa.celda.firstChild) previa.celda.removeChild(previa.celda.firstChild);
      for (var h = 0; h < previa.hijos.length; h++) previa.celda.appendChild(previa.hijos[h]);
      previa.celda.removeAttribute('title');
      delete tentativas[reserva];
    }

    function deshacer(reserva) {
      var previa = tentativas[reserva];
      if (!previa) return;
      revertirCelda(reserva);
      var select = selectorDe(reserva);
      if (select) {
        select.value = '';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      pintarPendiente(previa.boton);
      previa.boton.title = '';
      animar(previa.boton, [{ opacity: 0.3 }, { opacity: 1 }], { duration: 200 });
      decir('');
    }

    function colocar(celda) {
      if (!elegido || !celda.hasAttribute('data-elegible')) return;
      var boton = elegido;
      var reserva = boton.getAttribute('data-reserva');
      var select = selectorDe(reserva);
      if (!select) return;

      var desde = boton.getBoundingClientRect();
      var hasta = celda.getBoundingClientRect();

      /* 1. El estado primero. */
      select.value = celda.getAttribute('data-embarcacion');
      select.dispatchEvent(new Event('change', { bubbles: true }));

      var hijos = [];
      while (celda.firstChild) hijos.push(celda.removeChild(celda.firstChild));
      tentativas[reserva] = { celda: celda, hijos: hijos, boton: boton };
      var marca = document.createElement('span');
      marca.setAttribute('data-tentativa', '1');
      marca.style.color = VERDE;
      marca.style.fontStyle = 'italic';
      marca.textContent = nombreDe(boton).replace(/\s*·.*$/, '') + ' · sin guardar';
      celda.appendChild(marca);
      celda.title = 'Toca para deshacer';

      var panga = select.options[select.selectedIndex].textContent.replace(/\s*\(.*$/, '');
      decir(nombreDe(boton) + ' → ' + panga + '. Falta Guardar.', VERDE);

      var fila = select.closest('tr');
      if (fila) {
        animar(fila, [{ backgroundColor: 'rgba(21, 128, 61, 0.15)' }, { backgroundColor: 'rgba(21, 128, 61, 0)' }], { duration: 1600 });
      }

      limpiarCeldas();
      elegido = null;
      boton.style.visibility = 'hidden';

      /* 2. Despues, la animacion: el boton reaparece ya como "asignado". */
      vuelo(boton, desde, hasta, marca, function () {
        pintarAsignado(boton, panga);
        boton.style.visibility = '';
        animar(boton, [{ opacity: 0 }, { opacity: 1 }], { duration: 180 });
      });
    }

    for (i = 0; i < pendientes.length; i++) {
      pendientes[i].addEventListener('click', function (evento) {
        evento.preventDefault();
        var reserva = this.getAttribute('data-reserva');
        if (this.hasAttribute('data-asignado')) { deshacer(reserva); return; }
        if (elegido === this) { soltar(); decir(''); } else { elegir(this); }
      });
    }
    for (var j = 0; j < celdas.length; j++) {
      celdas[j].addEventListener('click', function () {
        var marca = this.querySelector('[data-tentativa]');
        if (marca && !elegido) {
          for (var reserva in tentativas) {
            if (tentativas[reserva].celda === this) { deshacer(reserva); return; }
          }
        }
        colocar(this);
      });
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
   *    vez del conteo de filas, que no informa nada.
   *  - Las filas con cambio llevan una barra verde a la izquierda.
   *  - Al guardar se anota que viajes eran, para celebrarlos al recargar. */
  function iniciarContadores(panel) {
    var guardar = document.querySelector('button[name="_save"]');
    var pie = guardar && guardar.parentElement ? guardar.parentElement.previousElementSibling : null;
    var textoPie = pie ? pie.textContent.replace(/\s+/g, ' ').trim() : '';
    var etiqueta = panel.querySelector('[data-sin-panga]');
    var resumen = panel.querySelector('[data-resumen]');
    var inicial = etiqueta ? parseInt(etiqueta.getAttribute('data-sin-panga'), 10) : 0;
    var chips = panel.querySelectorAll('[data-pendiente]');
    var selects = document.querySelectorAll('select[name$="-embarcacion"], select[name$="-capitan"]');
    if (!selects.length) return;

    var i;
    for (i = 0; i < selects.length; i++) {
      selects[i].setAttribute('data-original', selects[i].value);
    }
    var habiaCambios = false;

    function filasConCambio() {
      var filas = {};
      for (var s = 0; s < selects.length; s++) {
        if (selects[s].value !== selects[s].getAttribute('data-original')) {
          filas[selects[s].name.split('-').slice(0, 2).join('-')] = selects[s].closest('tr');
        }
      }
      return filas;
    }

    function actualizar() {
      var filas = filasConCambio();
      var cambios = Object.keys(filas).length;

      /* Barra de la fila: la que tiene cambio la lleva, las demas no. */
      var todas = document.querySelectorAll('select[name$="-embarcacion"]');
      for (var t = 0; t < todas.length; t++) {
        var tr = todas[t].closest('tr');
        var primera = tr ? tr.querySelector('.field-dia') : null;
        if (!primera) continue;
        var clave = todas[t].name.split('-').slice(0, 2).join('-');
        primera.style.boxShadow = filas[clave] ? 'inset 3px 0 0 ' + VERDE : '';
      }

      if (pie) {
        pie.textContent = cambios
          ? cambios + (cambios === 1 ? ' cambio sin guardar' : ' cambios sin guardar')
          : textoPie;
        pie.style.color = cambios ? VERDE : '';
        pie.style.fontWeight = cambios ? '600' : '';
        if (cambios && !habiaCambios) {
          animar(pie, [{ transform: 'translateY(6px)', opacity: 0 }, { transform: 'none', opacity: 1 }], { duration: 220 });
          /* Un solo pulso en Guardar: es lo siguiente que hay que hacer. */
          if (guardar) animar(guardar, [{ transform: 'scale(1)' }, { transform: 'scale(1.06)' }, { transform: 'scale(1)' }], { duration: 320, delay: 120 });
        }
      }
      habiaCambios = cambios > 0;

      if (etiqueta) {
        var asignados = 0;
        for (var j = 0; j < chips.length; j++) {
          var select = selectorDe(chips[j].getAttribute('data-reserva'));
          if (select && select.value) asignados++;
        }
        var faltan = Math.max(inicial - asignados, 0);
        var nuevo = faltan ? 'Sin panga (' + faltan + ')' : 'Todos con panga';
        if (etiqueta.textContent !== nuevo) {
          etiqueta.textContent = nuevo;
          etiqueta.style.color = faltan ? ROJO : VERDE;
          animar(etiqueta, [{ opacity: 0.2 }, { opacity: 1 }], { duration: 180 });
        }

        /* El resumen del titulo dice lo mismo que la etiqueta de la fila: no puede
         * quedarse atras. "Todo asignado" solo cuando tampoco queda otra cosa mala. */
        if (resumen) {
          var otros = parseInt(resumen.getAttribute('data-otros'), 10) || 0;
          var pieza = resumen.querySelector('[data-pieza-sin-panga]');
          var numero = resumen.querySelector('[data-n-sin-panga]');
          var todo = resumen.querySelector('[data-todo-asignado]');
          if (numero) numero.textContent = faltan;
          if (pieza) pieza.hidden = !faltan;
          if (todo) todo.hidden = !(faltan === 0 && otros === 0);
        }
      }
    }

    for (var k = 0; k < selects.length; k++) {
      selects[k].addEventListener('change', actualizar);
    }

    /* Al guardar, se anota que viajes eran: la pagina recarga y al volver se celebran. */
    var forma = document.getElementById('changelist-form');
    if (forma) {
      forma.addEventListener('submit', function () {
        var filas = filasConCambio();
        var ids = [];
        for (var clave in filas) {
          var campo = document.querySelector('input[type="hidden"][name="' + clave + '-id"]');
          if (campo) ids.push(campo.value);
        }
        try {
          window.sessionStorage.setItem(CLAVE_GUARDADO, JSON.stringify({ ids: ids, t: Date.now() }));
        } catch (e) { /* sin almacenamiento: no hay destello, y ya */ }
      });
    }
  }

  /* Tras guardar, lo guardado destella en verde y se apaga: confirma que quedo, sin
   * un cartel que haya que cerrar. Solo destella lo que de verdad quedo con panga: si
   * el guardado fallo, la celda no existe y la fila no tiene valor, asi que no hay
   * falsa confirmacion. */
  function celebrarGuardado() {
    var crudo = null;
    try {
      crudo = window.sessionStorage.getItem(CLAVE_GUARDADO);
      window.sessionStorage.removeItem(CLAVE_GUARDADO);
    } catch (e) { return; }
    if (!crudo) return;

    var anotado;
    try { anotado = JSON.parse(crudo); } catch (e) { return; }
    if (!anotado || !anotado.ids || Date.now() - anotado.t > 30000) return;

    var destello = [
      { backgroundColor: 'rgba(21, 128, 61, 0.30)' },
      { backgroundColor: 'rgba(21, 128, 61, 0)' }
    ];
    for (var i = 0; i < anotado.ids.length; i++) {
      var id = anotado.ids[i];
      var celda = document.querySelector('[data-celda][data-reserva="' + id + '"]');
      if (celda) animar(celda, destello, { duration: 1400 });
      var select = selectorDe(id);
      if (select && select.value) {
        var fila = select.closest('tr');
        if (fila) animar(fila, destello, { duration: 1400 });
      }
    }
  }

  // Disponibilidad: cerrar/reabrir un dia y marcar una panga fuera, sin salir de la agenda.
  // Escribe en los mismos modelos que sus pantallas de siempre (Cupo diario, Pangas fuera
  // de servicio) y recarga: el panorama, el pie y el selector de cada fila salen del
  // servidor y no hay que mantenerlos sincronizados a mano. Confirmaciones, motivo y
  // errores van en un dialogo propio de la pagina, no en los cuadros del navegador.
  function iniciarDisponibilidad(panel) {
    var url = panel.getAttribute('data-disponibilidad-url');
    var token = document.querySelector('input[name="csrfmiddlewaretoken"]');
    var dialogo = document.querySelector('[data-dialogo]');
    if (!url || !token || !dialogo || typeof dialogo.showModal !== 'function') return;

    var titulo = dialogo.querySelector('[data-dialogo-titulo]');
    var texto = dialogo.querySelector('[data-dialogo-texto]');
    var cajaMotivo = dialogo.querySelector('[data-dialogo-motivo-caja]');
    var campoMotivo = dialogo.querySelector('[data-dialogo-motivo]');
    var error = dialogo.querySelector('[data-dialogo-error]');
    var aceptar = dialogo.querySelector('[data-dialogo-aceptar]');
    var cancelar = dialogo.querySelector('[data-dialogo-cancelar]');
    var alAceptar = null;

    function enviar(datos) {
      var cuerpo = new URLSearchParams(datos);
      var empresa = panel.getAttribute('data-empresa');
      if (empresa) cuerpo.set('empresa', empresa);
      return fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': token.value, 'Content-Type': 'application/x-www-form-urlencoded' },
        body: cuerpo.toString(),
        credentials: 'same-origin',
      }).then(function (respuesta) {
        return respuesta.json().catch(function () { return {}; }).then(function (cuerpoJson) {
          if (!respuesta.ok) throw new Error(cuerpoJson.detail || 'No se pudo guardar.');
        });
      });
    }

    // `config`: titulo, texto, pedirMotivo, etiqueta del boton, soloCerrar y alAceptar(motivo).
    function abrir(config) {
      titulo.textContent = config.titulo;
      texto.textContent = config.texto || '';
      texto.hidden = !config.texto;
      cajaMotivo.hidden = !config.pedirMotivo;
      campoMotivo.value = '';
      error.hidden = true;
      error.textContent = '';
      aceptar.hidden = !!config.soloCerrar;
      aceptar.textContent = config.aceptar || 'Aceptar';
      aceptar.disabled = false;
      cancelar.textContent = config.soloCerrar ? 'Cerrar' : 'Cancelar';
      alAceptar = config.alAceptar || null;
      dialogo.showModal();
      if (config.pedirMotivo) campoMotivo.focus();
    }

    function ejecutar() {
      if (!alAceptar) return;
      aceptar.disabled = true;
      error.hidden = true;
      Promise.resolve(alAceptar(campoMotivo.value.trim())).then(function () {
        window.location.reload();
      }).catch(function (fallo) {
        error.textContent = fallo.message || 'No se pudo guardar.';
        error.hidden = false;
        aceptar.disabled = false;
      });
    }

    aceptar.addEventListener('click', ejecutar);
    cancelar.addEventListener('click', function () { dialogo.close(); });
    campoMotivo.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter') { evento.preventDefault(); ejecutar(); }
    });

    function sinConfirmar(datos) {
      // Reabrir y devolver una panga no necesitan confirmacion; si fallan, se dice por que.
      enviar(datos).then(function () { window.location.reload(); }).catch(function (fallo) {
        abrir({ titulo: 'No se pudo guardar', texto: fallo.message, soloCerrar: true });
      });
    }

    function fechaLarga(iso) {
      var partes = iso.split('-');
      var fecha = new Date(+partes[0], +partes[1] - 1, +partes[2]);
      return fecha.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' });
    }

    panel.addEventListener('click', function (evento) {
      // Encabezado del dia: cerrar o reabrir.
      var boton = evento.target.closest('[data-accion-dia]');
      if (boton && panel.contains(boton)) {
        evento.stopPropagation();
        var dia = boton.closest('[data-cupo-dia]');
        var fecha = dia.getAttribute('data-fecha');
        if (boton.getAttribute('data-accion-dia') === 'cerrar_dia') {
          abrir({
            titulo: 'Cerrar el ' + fechaLarga(fecha),
            texto: 'No se aceptarán más reservas ese día. Las que ya existen no se tocan.',
            aceptar: 'Cerrar el día',
            alAceptar: function () { return enviar({ accion: 'cerrar_dia', fecha: fecha }); },
          });
        } else {
          sinConfirmar({ accion: 'abrir_dia', fecha: fecha });
        }
        return;
      }

      // Celda tocable: vacia (sacar la panga ese dia) o "fuera" (devolverla). Mientras se
      // asigna un viaje, el toque es para asignar y lo atiende `iniciarAsignacion`.
      var celda = evento.target.closest('[data-celda][data-tocable]');
      if (!celda || !panel.contains(celda) || panel.hasAttribute('data-asignando')) return;
      if (celda.hasAttribute('data-ocupada') || celda.querySelector('[data-tentativa]')) return;
      evento.stopPropagation();

      var panga = celda.getAttribute('data-panga');
      var datos = {
        fecha: celda.getAttribute('data-fecha'),
        embarcacion: celda.getAttribute('data-embarcacion'),
      };
      if (celda.hasAttribute('data-fuera')) {
        abrir({
          titulo: 'Volver a poner ' + panga + ' en servicio',
          texto: 'Vuelve a contar para el cupo el ' + fechaLarga(datos.fecha) + '.',
          aceptar: 'Volver a servicio',
          alAceptar: function () {
            return enviar({ accion: 'panga_vuelve', fecha: datos.fecha, embarcacion: datos.embarcacion });
          },
        });
      } else {
        abrir({
          titulo: 'Sacar ' + panga + ' el ' + fechaLarga(datos.fecha),
          texto: 'No saldrá ese día y dejará de contar para el cupo.',
          pedirMotivo: true,
          aceptar: 'Sacar la panga',
          alAceptar: function (motivo) {
            return enviar({
              accion: 'panga_fuera', fecha: datos.fecha, embarcacion: datos.embarcacion, motivo: motivo,
            });
          },
        });
      }
    }, true);
  }

  // En movil las pestañas de empresa se desplazan de lado: la elegida arranca a la vista.
  function mostrarPestanaElegida() {
    var barra = document.querySelector('[data-empresas]');
    var actual = barra && barra.querySelector('[aria-current="page"]');
    if (actual) barra.scrollLeft = actual.offsetLeft - barra.offsetLeft - 16;
  }

  document.addEventListener('DOMContentLoaded', function () {
    mostrarPestanaElegida();
    var panel = document.querySelector('[data-panorama]');
    if (!panel) return;
    recordarApertura(panel);
    iniciarDisponibilidad(panel);
    iniciarAsignacion(panel);
    iniciarContadores(panel);
    celebrarGuardado();
  });
})();
