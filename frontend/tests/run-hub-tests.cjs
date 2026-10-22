/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');
const suites = {
  'content-sedes-indice': ['src/content/sedes-indice.ts', 'CONTENT_SEDES_INDICE_TEST_OUT'],
  'content-sedes-cuerpo': ['src/content/sedes-cuerpo.ts', 'CONTENT_SEDES_CUERPO_TEST_OUT'],
  'reconciliar-sedes': ['src/lib/reconciliar-sedes.ts', 'RECONCILIAR_TEST_OUT'],
  'booking-href': ['src/lib/booking-href.ts', 'BOOKING_HREF_TEST_OUT'],
  'calendario-paquete': ['src/lib/calendario-paquete.ts', 'CALENDARIO_TEST_OUT'],
  'tarifa-transporte': ['src/lib/tarifa-transporte.ts', 'TARIFA_TEST_OUT'],
  moneda: ['src/lib/moneda.ts', 'MONEDA_TEST_OUT'],
  iva: ['src/lib/iva.ts', 'IVA_TEST_OUT'],
  'pedido-paquete': ['src/lib/pedido-paquete.ts', 'PEDIDO_PAQUETE_TEST_OUT'],
  'pedido-payload': ['src/lib/pedido-payload.ts', 'PEDIDO_PAYLOAD_TEST_OUT'],
  'campo-validacion': ['src/lib/campo-validacion.ts', 'CAMPO_VALIDACION_TEST_OUT'],
  'pedido-estado': ['src/lib/pedido-estado.ts', 'PEDIDO_ESTADO_TEST_OUT'],
  'horario-servicio': ['src/lib/horario-servicio.ts', 'HORARIO_TEST_OUT'],
  'fallo-pago': ['src/lib/fallo-pago.ts', 'FALLO_PAGO_TEST_OUT'],
  'pasos-checkout': ['src/lib/pasos-checkout.ts', 'PASOS_CHECKOUT_TEST_OUT'],
  'ayuda-contextual': ['src/lib/ayuda-contextual.ts', 'AYUDA_CONTEXTUAL_TEST_OUT'],
  pendientes: ['src/lib/pendientes.ts', 'PENDIENTES_TEST_OUT'],
  'pendientes-texto': ['src/lib/pendientes-texto.ts', 'PENDIENTES_TEXTO_TEST_OUT'],
  'tokens-pago': ['src/lib/tokens-pago.ts', 'TOKENS_PAGO_TEST_OUT'],
  movimiento: ['src/lib/movimiento.ts', 'MOVIMIENTO_TEST_OUT'],
  personalizaciones: ['src/lib/pricing-paquete.ts', 'PERSONALIZACIONES_TEST_OUT'],
  variantes: ['src/components/ui/variantes.ts', 'VARIANTES_TEST_OUT'],
  'caja-campo': ['src/components/ui/caja-campo.ts', 'CAJA_CAMPO_TEST_OUT'],
  iniciales: ['src/lib/iniciales.ts', 'INICIALES_TEST_OUT'],
  'borrador-reserva': ['src/lib/borrador-reserva.ts', 'BORRADOR_TEST_OUT'],
  origen: ['src/lib/origen.ts', 'ORIGEN_TEST_OUT'],
  'campo-paso': ['src/lib/campo-paso.ts', 'CAMPO_PASO_TEST_OUT'],
  'validar-reserva': ['src/lib/validar-reserva.ts', 'VALIDAR_RESERVA_TEST_OUT'],
  'paso-url': ['src/lib/paso-url.ts', 'PASO_URL_TEST_OUT'],
  'texto-localizado': ['src/lib/texto-localizado.ts', 'TEXTO_LOCALIZADO_TEST_OUT'],
  'problema-reserva': ['src/lib/problema-reserva.ts', 'PROBLEMA_TEST_OUT'],
  'etiqueta-boton': ['src/lib/etiqueta-boton.ts', 'ETIQUETA_BOTON_TEST_OUT'],
  'pantallas-checkout': ['src/lib/pantallas-checkout.ts', 'PANTALLAS_CHECKOUT_TEST_OUT'],
  'control-fecha': ['src/lib/control-fecha.ts', 'CONTROL_FECHA_TEST_OUT'],
  'anticipacion': ['src/lib/anticipacion.ts', 'ANTICIPACION_TEST_OUT'],
  'rango-paquete': ['src/lib/rango-paquete.ts', 'RANGO_PAQUETE_TEST_OUT'],
  'calendario-mes': ['src/lib/calendario-mes.ts', 'CALENDARIO_MES_TEST_OUT'],
  'etiquetas-catalogo': ['src/lib/etiquetas-catalogo.ts', 'ETIQUETAS_TEST_OUT'],
  'imagenes-catalogo': ['src/content/imagenes-catalogo.ts', 'IMAGENES_TEST_OUT'],
  'color-actividad': ['src/lib/color-actividad.ts', 'COLOR_ACTIVIDAD_TEST_OUT'],
  'temporada-actual': ['src/lib/temporada-actual.ts', 'TEMPORADA_TEST_OUT'],
  cifra: ['src/lib/cifra.ts', 'CIFRA_TEST_OUT'],
  mosaico: ['src/lib/mosaico.ts', 'MOSAICO_TEST_OUT'],
  'fila-arrastrable': ['src/lib/fila-arrastrable.ts', 'FILA_ARRASTRABLE_TEST_OUT'],
  'secciones-sede': ['src/lib/secciones-sede.ts', 'SECCIONES_TEST_OUT'],
  empresas: ['src/content/empresas.ts', 'EMPRESAS_TEST_OUT'],
};
const chosen = process.argv.length > 2 ? process.argv.slice(2) : Object.keys(suites);
for (const name of chosen) {
  if (!Object.hasOwn(suites, name)) throw new Error('Suite desconocida: ' + name);
}
const outDir = fs.mkdtempSync(path.join(os.tmpdir(), 'hub-multisede-tests-'));
const loaded = ts.readConfigFile(path.join(root, 'tsconfig.json'), ts.sys.readFile);
const formatHost = {
  getCanonicalFileName: (file) => file,
  getCurrentDirectory: () => root,
  getNewLine: () => '\n',
};
if (loaded.error) throw new Error(ts.formatDiagnostics([loaded.error], formatHost));
const config = ts.parseJsonConfigFileContent({
  ...loaded.config,
  files: chosen.map((name) => suites[name][0]),
  include: [],
  exclude: [],
}, ts.sys, root);
const options = {
  ...config.options,
  rootDir: path.join(root, 'src'), outDir,
  noEmit: false, noEmitOnError: true, incremental: false,
  tsBuildInfoFile: undefined,
  module: ts.ModuleKind.CommonJS,
  moduleResolution: ts.ModuleResolutionKind.Node10,
};
const program = ts.createProgram(config.fileNames, options);
const diagnostics = [...config.errors, ...ts.getPreEmitDiagnostics(program)];
if (diagnostics.length) {
  process.stderr.write(ts.formatDiagnostics(diagnostics, formatHost));
  process.exit(1);
}
const result = program.emit();
if (result.emitSkipped) {
  process.stderr.write(ts.formatDiagnostics(result.diagnostics, formatHost));
  process.exit(1);
}
const env = { ...process.env };
for (const name of chosen) {
  env[suites[name][1]] = name === 'personalizaciones' ? path.join(outDir, 'lib') : outDir;
}
const tests = chosen.map((name) => path.join(root, 'tests', name + '.test.cjs'));
const run = spawnSync(process.execPath, ['--test', ...tests], { cwd: root, env, stdio: 'inherit' });
if (run.error) throw run.error;
process.exitCode = run.status ?? 1;
