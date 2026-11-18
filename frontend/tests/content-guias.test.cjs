/* eslint-disable @typescript-eslint/no-require-imports */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const m = require(path.join(process.env.CONTENT_GUIAS_TEST_OUT, 'content/guias.js'));
const raiz = path.resolve(__dirname, '..');
const IDIOMAS = ['es', 'en'];
const SEDES = ['la-paz', 'la-ventana', 'puerto-chale'];

const cadaTexto = () => m.GUIAS.flatMap((guia) => IDIOMAS.map((idioma) => ({ guia, idioma, textos: guia.textos[idioma] })));

// Una marca del catálogo (`{duracion:…}`) se mide con el largo de su valor más largo de hoy.
const LARGO_MARCA = { duracion: 11, maximo: 2, personas: 2, anticipo: 4, salida: 31, hora: 7, horario: 26, precio: 32, extra: 32 };
const largo = (texto) => texto.replace(/\{([a-z]+):[a-z0-9-]+\/[a-z0-9-]+\}/g, (_, campo) => 'x'.repeat(LARGO_MARCA[campo] ?? 32)).length;

test('el titulo de la pestaña y la descripcion caben en lo que Google muestra', () => {
  for (const { textos } of cadaTexto()) {
    assert.ok(largo(textos.metaTitulo) <= 62, `${largo(textos.metaTitulo)}: ${textos.metaTitulo}`);
    assert.ok(largo(textos.metaDescripcion) <= 155, `${largo(textos.metaDescripcion)}: ${textos.metaDescripcion}`);
  }
});

test('ningun slug, id ni titulo se repite, y el slug es una ruta limpia', () => {
  assert.equal(new Set(m.GUIAS.map((guia) => guia.id)).size, m.GUIAS.length);
  // Un slug repetido entre idiomas rompería la redirección al cambiar de idioma: se revisan todos juntos.
  const slugs = cadaTexto().map(({ textos }) => textos.slug);
  assert.equal(new Set(slugs).size, slugs.length, 'slugs repetidos');
  for (const slug of slugs) assert.match(slug, /^[a-z0-9]+(?:-[a-z0-9]+)*$/);
  for (const idioma of IDIOMAS) {
    for (const campo of ['titulo', 'metaTitulo', 'metaDescripcion']) {
      const valores = m.GUIAS.map((guia) => guia.textos[idioma][campo]);
      assert.equal(new Set(valores).size, valores.length, `${campo} repetido en ${idioma}`);
    }
  }
});

test('las dos versiones de una guia tienen la misma forma', () => {
  for (const guia of m.GUIAS) {
    const { es, en } = guia.textos;
    assert.equal(es.datos.length, en.datos.length, guia.id);
    assert.equal(es.secciones.length, en.secciones.length, guia.id);
    assert.equal(es.faq.length, en.faq.length, guia.id);
    assert.equal(Boolean(es.calendario), Boolean(en.calendario), guia.id);
    es.secciones.forEach((seccion, i) => {
      assert.equal(seccion.parrafos.length, en.secciones[i].parrafos.length, `${guia.id} seccion ${i}`);
      assert.equal(seccion.lista?.length ?? 0, en.secciones[i].lista?.length ?? 0, `${guia.id} lista ${i}`);
    });
    if (es.calendario) {
      // Los meses son datos, no texto: no pueden decir una cosa en español y otra en inglés.
      const meses = (calendario) => calendario.filas.map((fila) => [fila.meses, fila.fuertes ?? [], fila.fuente ?? null]);
      assert.deepEqual(meses(es.calendario), meses(en.calendario), guia.id);
    }
  }
});

test('cada guia trae lo que la plantilla pinta: respuesta, datos, secciones, preguntas y que reservar', () => {
  for (const { guia, textos } of cadaTexto()) {
    assert.ok(textos.titulo.trim() && textos.respuesta.trim(), guia.id);
    assert.ok(textos.datos.length >= 2 && textos.datos.length <= 4, `${guia.id}: ${textos.datos.length} datos`);
    assert.ok(textos.secciones.length >= 2, guia.id);
    assert.ok(textos.faq.length >= 3 && textos.faq.length <= 8, `${guia.id}: ${textos.faq.length} preguntas`);
    assert.ok(textos.producto.titulo.trim() && textos.producto.texto.trim(), guia.id);
    // La plantilla usa el título de sección, el párrafo y la pregunta como `key`.
    assert.equal(new Set(textos.secciones.map((s) => s.titulo)).size, textos.secciones.length, guia.id);
    assert.equal(new Set(textos.faq.map((p) => p.q)).size, textos.faq.length, guia.id);
    for (const seccion of textos.secciones) {
      assert.equal(new Set(seccion.parrafos).size, seccion.parrafos.length, `${guia.id}: ${seccion.titulo}`);
    }
  }
});

test('los calendarios marcan meses reales y los fuertes estan dentro de la temporada', () => {
  for (const { guia, textos } of cadaTexto()) {
    if (!textos.calendario) continue;
    assert.ok(textos.calendario.filas.length > 0 && textos.calendario.nota.trim(), guia.id);
    assert.equal(new Set(textos.calendario.filas.map((fila) => fila.nombre)).size, textos.calendario.filas.length, guia.id);
    for (const fila of textos.calendario.filas) {
      assert.ok(fila.meses.length > 0, `${guia.id}: ${fila.nombre}`);
      for (const mes of fila.meses) assert.ok(Number.isInteger(mes) && mes >= 1 && mes <= 12, `${fila.nombre}: ${mes}`);
      for (const mes of fila.fuertes ?? []) assert.ok(fila.meses.includes(mes), `${fila.nombre}: fuerte fuera de temporada (${mes})`);
    }
  }
});

test('la foto existe, la fecha es una fecha y la sede es una de las tres', () => {
  for (const guia of m.GUIAS) {
    assert.ok(fs.existsSync(path.join(raiz, 'public', guia.foto.src)), `falta ${guia.foto.src}`);
    assert.ok(guia.foto.alt.es.trim() && guia.foto.alt.en.trim(), guia.id);
    assert.match(guia.actualizado, /^\d{4}-\d{2}-\d{2}$/);
    assert.ok(!Number.isNaN(Date.parse(guia.actualizado)), guia.id);
    assert.ok(guia.sede === null || SEDES.includes(guia.sede), guia.id);
    assert.ok(guia.destinos.length > 0, `${guia.id}: sin nada que reservar`);
  }
});

test('cada seccion tiene su foto, todas existen y llevan descripcion en los dos idiomas', () => {
  for (const guia of m.GUIAS) {
    assert.equal(guia.fotos.length, guia.textos.es.secciones.length, `${guia.id}: una foto por seccion`);
    for (const foto of [guia.foto, guia.fotoFrase, ...guia.fotos]) {
      assert.ok(fs.existsSync(path.join(raiz, 'public', foto.src)), `falta ${foto.src}`);
      assert.ok(foto.alt.es.trim() && foto.alt.en.trim(), `${guia.id}: ${foto.src}`);
    }
    assert.ok(['mar', 'traslado', 'estancia'].includes(guia.tema), guia.id);
    for (const idioma of IDIOMAS) {
      const frase = guia.textos[idioma].frase;
      assert.ok(frase.trim() && frase.length <= 70, `${guia.id}: frase de ${frase.length}`);
    }
  }
});

test('el titulo se parte para el arranque: lo que nombra el tema y el resto', () => {
  assert.deepEqual(m.partesDeTitulo('Nado con orcas en La Ventana: cuándo ir y cómo es la salida'), { principal: 'Nado con orcas en La Ventana', resto: 'Cuándo ir y cómo es la salida' });
  assert.deepEqual(m.partesDeTitulo('Qué hacer en La Ventana, Baja California Sur'), { principal: 'Qué hacer en La Ventana', resto: 'Baja California Sur' });
  assert.deepEqual(m.partesDeTitulo('Cómo llegar a Puerto Chale desde La Paz y Los Cabos'), { principal: 'Cómo llegar a Puerto Chale', resto: 'Desde La Paz y Los Cabos' });
  assert.deepEqual(m.partesDeTitulo('How to get to Puerto Chale from La Paz and Los Cabos'), { principal: 'How to get to Puerto Chale', resto: 'From La Paz and Los Cabos' });
  assert.deepEqual(m.partesDeTitulo('Sin corte'), { principal: 'Sin corte', resto: null });
  // La parte grande va en mayúsculas sobre la foto: corta, para que quepa en pocas líneas.
  for (const { guia, textos } of cadaTexto()) {
    const { principal } = m.partesDeTitulo(textos.titulo);
    assert.ok(principal.length <= 50, `${guia.id}: ${principal.length} ${principal}`);
  }
});

test('nunca se habla de permisos ni de dependencias de gobierno (decision del dueño)', () => {
  const todo = JSON.stringify(m.GUIAS);
  assert.doesNotMatch(todo, /semarnat|profepa|conanp/i);
  assert.doesNotMatch(todo, /\bpermisos?\b|\bpermits?\b/i);
});

test('getGuia encuentra por slug e idioma, y slugEnIdioma traduce el del otro idioma', () => {
  const orcas = m.getGuia('nado-con-orcas-la-ventana', 'es');
  assert.equal(orcas.id, 'orcas-la-ventana');
  assert.equal(m.getGuia('nado-con-orcas-la-ventana', 'en'), undefined);
  assert.equal(m.slugEnIdioma('nado-con-orcas-la-ventana', 'en'), 'swim-with-orcas-la-ventana');
  assert.equal(m.slugEnIdioma('swim-with-orcas-la-ventana', 'es'), 'nado-con-orcas-la-ventana');
  assert.equal(m.slugEnIdioma('no-existe', 'es'), undefined);
});

test('las relacionadas no incluyen a la propia, son tres como mucho y empiezan por su sede', () => {
  for (const guia of m.GUIAS) {
    const otras = m.guiasRelacionadas(guia);
    assert.ok(otras.length <= 3 && otras.length > 0, guia.id);
    assert.ok(!otras.some((otra) => otra.id === guia.id), guia.id);
    const deSuSede = m.GUIAS.filter((otra) => otra.id !== guia.id && otra.sede === guia.sede);
    if (guia.sede && deSuSede.length > 0) assert.equal(otras[0].sede, guia.sede, guia.id);
  }
});

test('cada sede tiene guias para su fila «Antes de venir»', () => {
  for (const sede of SEDES) assert.ok(m.guiasDeSede(sede).length > 0, sede);
  assert.deepEqual(m.guiasDeSede('nadie'), []);
});
