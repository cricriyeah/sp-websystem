// Numero de WhatsApp de la empresa, en digitos con lada de pais y sin signos
// (ej. 5216121234567). Se configura por entorno para no tenerlo quemado en el
// codigo y poder cambiarlo sin tocar componentes.
//
// Si no esta configurado, `tieneWhatsapp` es false y la interfaz simplemente no
// muestra el bloque: preferible a publicar un numero de relleno que le caeria a
// un desconocido.
const NUMERO = (process.env.NEXT_PUBLIC_WHATSAPP_NUMBER ?? '').replace(/\D/g, '');

export const tieneWhatsapp = NUMERO.length >= 11;

export const whatsappNumero = NUMERO;

/** Formato legible: +52 1 612 123 4567 / +52 612 123 4567. */
export function whatsappVisible() {
  if (!tieneWhatsapp) return '';

  // Mexico: 52 + (1 opcional de movil) + 10 digitos.
  if (NUMERO.startsWith('52')) {
    const resto = NUMERO.slice(2);
    const movil = resto.length === 11 && resto.startsWith('1');
    const diez = movil ? resto.slice(1) : resto;
    if (diez.length === 10) {
      const grupos = `${diez.slice(0, 3)} ${diez.slice(3, 6)} ${diez.slice(6)}`;
      return movil ? `+52 1 ${grupos}` : `+52 ${grupos}`;
    }
  }
  return `+${NUMERO}`;
}

/** Enlace a la conversacion, con el mensaje ya escrito para que el cliente no
 *  tenga que redactar nada. */
export function whatsappHref(mensaje: string) {
  return `https://wa.me/${NUMERO}?text=${encodeURIComponent(mensaje)}`;
}
