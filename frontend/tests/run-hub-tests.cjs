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
  'pedido-paquete': ['src/lib/pedido-paquete.ts', 'PEDIDO_PAQUETE_TEST_OUT'],
  'pedido-payload': ['src/lib/pedido-payload.ts', 'PEDIDO_PAYLOAD_TEST_OUT'],
  'pedido-estado': ['src/lib/pedido-estado.ts', 'PEDIDO_ESTADO_TEST_OUT'],
  'fallo-pago': ['src/lib/fallo-pago.ts', 'FALLO_PAGO_TEST_OUT'],
  'selector-experiencia': ['src/lib/selector-experiencia.ts', 'SELECTOR_TEST_OUT'],
  personalizaciones: ['src/lib/pricing-paquete.ts', 'PERSONALIZACIONES_TEST_OUT'],
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
