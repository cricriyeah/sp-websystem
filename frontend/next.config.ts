import type { NextConfig } from "next";

// El backend Django vive en otro origen (Render) y el checkout le habla directo
// desde el navegador: si su URL no esta en `connect-src`, el CSP tumba el
// checkout entero. Por eso se lee de la misma env var que usa src/lib/api.ts.
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Politica de contenido: define de donde puede cargar cosas la pagina, para que
// un script inyectado no pueda mandar los datos de la tarjeta a otro lado.
//
// Es una linea base, no una politica estricta: `'unsafe-inline'` en script-src
// sigue haciendo falta porque Next inyecta scripts en la hidratacion. Cerrarlo
// del todo exige migrar a nonces por peticion, que es un trabajo aparte.
const csp = [
  "default-src 'self'",
  // Stripe.js se sirve desde su CDN y monta los campos de tarjeta en un iframe
  // suyo — asi es como el numero de tarjeta nunca toca nuestro dominio y el
  // sistema se queda en alcance PCI-DSS SAQ-A.
  // challenges.cloudflare.com sirve el widget de Turnstile, el gate anti-bot
  // del checkout. Sin esto el CSP lo bloquea y el widget nunca da un token.
  "script-src 'self' 'unsafe-inline' https://js.stripe.com https://challenges.cloudflare.com",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${apiUrl} https://api.stripe.com https://challenges.cloudflare.com`,
  // Turnstile monta su reto en un iframe propio, igual que Stripe.
  "frame-src https://js.stripe.com https://hooks.stripe.com https://challenges.cloudflare.com",
  // Nadie debe poder meter el checkout dentro de un iframe: es como se monta un
  // clickjacking sobre un formulario de pago.
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

// En dev el CSP se queda fuera: Turbopack necesita `'unsafe-eval'` para el HMR y
// aflojar la politica para que pase el modo desarrollo la volveria mentira en
// produccion, que es donde importa.
const esProduccion = process.env.NODE_ENV === "production";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          // Impide que el navegador "adivine" el tipo de un archivo y termine
          // ejecutando como script algo que se subio como imagen.
          { key: "X-Content-Type-Options", value: "nosniff" },
          // No filtrar la ruta completa (que lleva ids de reserva) al salir a
          // otro dominio.
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Respaldo de `frame-ancestors` para navegadores viejos.
          { key: "X-Frame-Options", value: "DENY" },
          // Camara, microfono y ubicacion no se usan en ningun lado; apagarlos
          // evita que un script de terceros los pida en nuestro nombre. `payment`
          // se deja abierto a Stripe a proposito: es el permiso que necesita la
          // Payment Request API y cerrarlo apagaria Apple Pay / Google Pay dentro
          // del PaymentElement, sin ningun error visible.
          {
            key: "Permissions-Policy",
            value:
              'camera=(), microphone=(), geolocation=(), payment=(self "https://js.stripe.com")',
          },
          ...(esProduccion
            ? [{ key: "Content-Security-Policy", value: csp }]
            : []),
        ],
      },
    ];
  },
};

export default nextConfig;
