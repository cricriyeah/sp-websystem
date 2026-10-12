# Enlace de pago por WhatsApp (sin código nuevo)

Cuando una venta se cierra por WhatsApp o teléfono y el cliente quiere **pagar con tarjeta**, no se registra la reserva a mano: se le manda un enlace del sitio con el viaje ya precargado. El cliente llena su nombre, teléfono y correo, acepta el deslinde y paga por el checkout normal. Verificado el 12 de octubre de 2026 leyendo `frontend/src/app/[lang]/reservar/page.tsx`, `frontend/src/lib/dates.ts` y `frontend/src/lib/ref.ts`, y comprobado en el sitio local (la página sale con la fecha y las personas ya cargadas).

## La fórmula (servicio suelto, por ejemplo pesca)

```
https://<sitio>/es/reservar?servicio=<slug-del-servicio>&empresa=<slug-de-la-empresa>&day=<AAAA-MM-DD>&time=<HH:MM>&people=<N>&ref=<tu-codigo>
```

| Parte | Qué poner | Dónde se consulta |
|---|---|---|
| `<sitio>` | El dominio público del sitio (el que usan los clientes) | El jefe lo sabe |
| `/es/` | Idioma del cliente: `es` o `en` | — |
| `servicio` | El slug del servicio, p. ej. `pesca-deportiva` | Admin → Servicios → ficha del servicio |
| `empresa` | El slug de tu empresa, p. ej. `sal-y-sol` | El jefe o el operador |
| `day` | La fecha del viaje, `AAAA-MM-DD` | — |
| `time` | La hora de salida, `HH:MM` | Debe estar dentro del horario del servicio |
| `people` | Cuántas personas | — |
| `ref` | **Tu código de vendedora**: así la venta queda atribuida a ti | Admin → Vendedoras |

Ejemplo (pesca para 3 personas el 25 de octubre a las 6:00):

```
https://<sitio>/es/reservar?servicio=pesca-deportiva&empresa=sal-y-sol&day=2026-10-25&time=06:00&people=3&ref=ventas-ana
```

Reglas que aplica el sitio al abrir el enlace:

- La fecha debe ser **de mañana en adelante**; si es anterior o está mal escrita, el sitio pone la primera disponible.
- Las personas van de 1 al máximo del servicio; fuera de ese rango, el sitio las ajusta.
- Si la hora no es una de las que ofrece el servicio, el sitio pone la primera.
- Si falta `empresa` o `servicio`, el sitio usa los de su configuración por defecto: **escríbelos siempre**.

## Paquetes

```
https://<sitio>/es/reservar?paquete=<slug-del-paquete>&sede=<slug-de-la-sede>&ref=<tu-codigo>
```

Para paquetes el sitio **todavía no precarga** fecha, hora ni personas: el cliente las elige. El enlace sí lleva al paquete correcto y atribuye la venta.

## Lo que hay que saber antes de mandarlo

1. **Si mandas el enlace, NO registres la reserva a mano.** Si lo haces, el cliente pagará por la web y quedarán dos reservas del mismo viaje. El alta manual del admin es para las ventas que se pagan por **transferencia**.
2. **El precio es el del catálogo.** El sitio lo calcula solo; no se puede acordar un precio especial por WhatsApp salvo con un código promocional que ya exista.
3. **El deslinde lo acepta el cliente,** con su nombre; por eso la vendedora no llena el checkout por él.
4. **El enlace no caduca.** Si el cliente paga semanas después y ya no hay lugar ese día, el sistema le **reembolsa solo** el pago completo.
5. **El lugar se aparta al pagar,** no al abrir el enlace: otra persona puede ganar el último lugar mientras el cliente decide.
6. **No pongas datos del cliente en el enlace** (nombre, teléfono, correo): viajarían a la vista de cualquiera a quien se lo reenvíe.
7. **Tu `ref` dura 30 días en el navegador del cliente.** Si abre antes el enlace de otra vendedora, el último que abra es el que cuenta.

## Importante: no uses «Payment Links» de Stripe armados a mano

El sistema solo reconoce un pago de Stripe si trae la referencia de la reserva (`metadata.reserva_id`). Un cobro hecho con un Payment Link creado en el panel de Stripe **no la trae y el sistema lo reembolsa automáticamente**. Para cobrar con tarjeta usa siempre el enlace del sitio de arriba.
