/* eslint-disable @typescript-eslint/no-require-imports */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { urlVideo } = require(path.join(process.env.MEDIA_TEST_OUT, 'lib/media.js'));

const BASE = 'https://media.ejemplo.com';

test('sin base los videos siguen saliendo de public', () => {
  assert.equal(urlVideo('/videos/videohub.webm', undefined), '/videos/videohub.webm');
  assert.equal(urlVideo('/videos/videohub.webm', ''), '/videos/videohub.webm');
  assert.equal(urlVideo('/videos/videohub.webm', '   '), '/videos/videohub.webm');
});

test('con base cada video va a la carpeta de su sede en el bucket', () => {
  assert.equal(urlVideo('/videos/videohub.webm', BASE), `${BASE}/hub/videohub.mp4`);
  assert.equal(urlVideo('/videos/videonuevonuevolapaz.mp4', BASE), `${BASE}/lapaz/videonuevonuevolapaz-20s.mp4`);
  assert.equal(urlVideo('/videos/ventana-hero.webm', BASE), `${BASE}/laventana/videolaventana-0025-0045.mp4`);
});

test('la barra final de la base no duplica separadores', () => {
  assert.equal(urlVideo('/videos/videohub.webm', `${BASE}/`), `${BASE}/hub/videohub.mp4`);
  assert.equal(urlVideo('/videos/videohub.webm', `${BASE}///`), `${BASE}/hub/videohub.mp4`);
});

test('un video que no está en el bucket se sirve desde public', () => {
  assert.equal(urlVideo('/videos/videohero.webm', BASE), '/videos/videohero.webm');
});

test('lo que no es un video del sitio no se toca', () => {
  assert.equal(urlVideo('/photos/foto.webp', BASE), '/photos/foto.webp');
  assert.equal(urlVideo('https://otro.com/v.mp4', BASE), 'https://otro.com/v.mp4');
});
