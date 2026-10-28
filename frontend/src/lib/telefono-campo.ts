// Estado del campo de teléfono con selector de país: qué se muestra, qué se guarda y cómo
// cambia al teclear, pegar, elegir país o salir del campo. Lógica pura (sin React) para
// probarla sin navegador; la interfaz es checkout/telefono-campo.tsx.
//
// El valor que sube al formulario es el compacto de telefono.ts (`+<código><lo tecleado>`, ''
// sin dígitos). El país elegido vive aparte y NUNCA se recalcula desde la biblioteca cuando el
// código ya coincide: +1, +7 y +44 los comparten varios países y `07911 123456` con GB devolvería
// GG (ARCH-telefono-con-pais, caso 5).
import { PAIS_POR_DEFECTO, aE164, compactar, formatearTelefono, resolverCodigo, restaurarTelefono } from './telefono';
import { codigoDePais, listarPaises, paisPrincipal } from './paises-telefono';

/** Nombre del país por sigla, en el idioma pedido; para `lineaDeTelefono`. */
export function nombradorDePaises(lang: string): (iso: string) => string | undefined {
  const nombres = new Map(listarPaises(lang).map((pais) => [pais.iso, pais.nombre]));
  return (iso) => nombres.get(iso);
}

const ISLAS_DEL_44 = ['GG', 'IM', 'JE'];

/**
 * Teléfono para el resumen y «Tus datos»: `+52 612 123 4567 · México`. Si no se puede formatear
 * (incompleto, basura) devuelve el valor tal cual, para no esconder lo que escribió el cliente.
 */
export function lineaDeTelefono(valor: string, nombrePais: (iso: string) => string | undefined): string {
  const f = formatearTelefono(valor);
  if (!f) return valor;
  // Los móviles británicos caen en rangos de las islas (07911 es Guernsey para la biblioteca): al
  // cliente se le muestra Reino Unido, que es lo que eligió.
  const iso = f.iso && ISLAS_DEL_44.includes(f.iso) ? 'GB' : f.iso;
  const nombre = iso ? nombrePais(iso) : undefined;
  return nombre ? `${f.texto} · ${nombre}` : f.texto;
}

export type EstadoTelefono = {
  /** País elegido en el selector (sigla ISO). */
  iso: string;
  /** Lo que se ve en la caja del número, sin el código de país. */
  texto: string;
  /** Lo que sube al formulario. */
  valor: string;
};

// Respaldo si la biblioteca falla y no se conoce el código del país elegido.
const CODIGO_RESPALDO = '52';

function codigoElegido(iso: string): string {
  return codigoDePais(iso) ?? CODIGO_RESPALDO;
}

function empiezaConMas(texto: string): boolean {
  const t = texto.trimStart();
  return t.startsWith('+') || t.startsWith('00');
}

// Solo dígitos y `+ ( ) - . espacio`; el `+` solo vale al principio. Las letras se descartan.
function limpiarTecleo(crudo: string): string {
  return crudo.replace(/[^\p{Nd}+().\-\s]/gu, '').replace(/(?!^)\+/g, '');
}

function nacionalDe(valor: string, codigo: string): string {
  return valor.startsWith('+' + codigo) ? valor.slice(1 + codigo.length) : '';
}

// Arma el estado de un texto ya sin código resuelto. Un texto que empieza con `+` o `00` y cuyo
// código aún no existe (`+3`, `+999…`) sube como `+<dígitos>`: así `evaluar` lo reconoce como
// código desconocido en vez de leerlo como un número mexicano.
function armar(iso: string, crudo: string): EstadoTelefono {
  if (empiezaConMas(crudo)) {
    const sinPrefijo = crudo.trimStart().replace(/^(\+|00)/, '');
    return { iso, texto: limpiarTecleo(crudo), valor: compactar('', sinPrefijo) };
  }
  const codigo = codigoElegido(iso);
  const valor = compactar(codigo, crudo);
  const limpio = limpiarTecleo(crudo);
  // Si el valor quedó más corto que lo escrito (extensión cortada o tope de 15 dígitos), el texto
  // muestra lo que de verdad se guardó: sin esto el cliente creería que su número está completo.
  const escritos = compactar('', limpio).slice(1);
  const guardados = nacionalDe(valor, codigo);
  return { iso, texto: escritos === guardados ? limpio : guardados, valor };
}

/** Estado al montar con un valor que ya existía (borrador, reanudación, servidor). Nunca borra. */
export function estadoInicial(valor: string): EstadoTelefono {
  const restaurado = restaurarTelefono(valor);
  if (restaurado === '') return { iso: PAIS_POR_DEFECTO, texto: '', valor: '' };
  const separado = resolverCodigo(restaurado);
  if (separado) {
    return { iso: paisPrincipal(separado.codigo) ?? PAIS_POR_DEFECTO, texto: separado.resto, valor: restaurado };
  }
  // No se entiende: queda visible en el campo con México y el error de siempre.
  return { iso: PAIS_POR_DEFECTO, texto: restaurado, valor: restaurado };
}

/** Cada cambio de la caja del número (teclear, pegar, autocompletar). Sin formato en vivo. */
export function alEscribir(iso: string, crudo: string): EstadoTelefono {
  const separado = resolverCodigo(crudo);
  if (!separado) return armar(iso, crudo);
  const mismoCodigo = codigoDePais(iso) === separado.codigo;
  const isoNuevo = mismoCodigo ? iso : (paisPrincipal(separado.codigo) ?? iso);
  return armar(isoNuevo, separado.resto);
}

/** Elegir otro país de la lista: se conserva lo escrito y cambia solo el código. */
export function alCambiarPais(texto: string, iso: string): EstadoTelefono {
  const e = armar(iso, texto);
  // `armar` limpia y puede cortar; aquí el texto ya estaba limpio y no se toca.
  return { ...e, texto };
}

/** Al salir de la caja: si es un número posible se canoniza y se muestra con formato nacional. */
export function alSalir(estado: EstadoTelefono): EstadoTelefono {
  const e164 = aE164(estado.valor);
  if (!e164) return estado;
  const formato = formatearTelefono(e164, estado.iso);
  if (!formato) return estado;
  const prefijo = '+' + formato.codigo + ' ';
  const texto = formato.texto.startsWith(prefijo) ? formato.texto.slice(prefijo.length) : nacionalDe(e164, formato.codigo);
  return { iso: estado.iso, texto, valor: e164 };
}
