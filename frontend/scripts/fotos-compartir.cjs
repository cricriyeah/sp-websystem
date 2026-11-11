/* eslint-disable @typescript-eslint/no-require-imports */
// Genera en public/compartir/ la imagen para compartir de cada servicio y paquete (1200×630, JPG): la foto
// principal de src/content/imagenes-catalogo.ts recortada al centro. Los JPG se commitean; sharp queda como
// devDependency solo para este script.
//
//   npm run fotos-compartir
//
// Es idempotente: vuelve a escribir todas (son pocas) e imprime cuáles cambió.
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const sharp = require('sharp');

const raiz = path.resolve(__dirname, '..');
const fuente = path.join(raiz, 'src', 'content', 'imagenes-catalogo.ts');
const texto = fs.readFileSync(fuente, 'utf8');

// El módulo es puro: se transpila y se carga como lo hace tests/run-hub-tests.cjs.
const js = ts.transpileModule(texto, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const modulo = { exports: {} };
new Function('module', 'exports', 'require', 'process', js)(modulo, modulo.exports, require, process);
const { fotoParaCompartir } = modulo.exports;

const claves = [...new Set([...texto.matchAll(/^ {2}'((?:servicio|paquete):[^']+)':/gm)].map((m) => m[1]))];
const destino = path.join(raiz, 'public', 'compartir');
fs.mkdirSync(destino, { recursive: true });

(async () => {
  for (const clave of claves) {
    const foto = fotoParaCompartir(clave);
    if (!foto) continue;
    const salida = path.join(raiz, 'public', foto.src);
    const antes = fs.existsSync(salida) ? fs.readFileSync(salida) : null;
    const origen = path.join(raiz, 'public', foto.origen);
    const { width, height } = await sharp(origen).metadata();
    let imagen = sharp(origen);
    // En una foto vertical la persona y su pez quedan casi siempre a media altura; «attention» se iba a los pies.
    if (height > width) {
      const banda = Math.round((width * 630) / 1200);
      const arriba = Math.max(0, Math.min(height - banda, Math.round(height * 0.47 - banda / 2)));
      imagen = imagen.extract({ left: 0, top: arriba, width, height: banda });
    }
    const jpg = await imagen
      .resize(1200, 630, { fit: 'cover', position: 'attention' })
      .jpeg({ quality: 80, mozjpeg: true })
      .toBuffer();
    if (antes && antes.equals(jpg)) continue;
    fs.writeFileSync(salida, jpg);
    console.log(`${foto.src} (${Math.round(jpg.length / 1024)} KB)`);
  }
  console.log(`${claves.length} productos revisados.`);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
