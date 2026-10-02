# Preguntas pendientes para el cliente — La Ventana Travel

Fecha: 2026-10-01. Todo lo de abajo hoy está cargado con **datos demo** en la base local
(`seed_catalogo_real`) y debe confirmarse antes de vender. Lo marcado con ★ bloquea cargar
los paquetes.

## 1. Los paquetes

Ya confirmado por el dueño: paquete A = 5 noches, mar los días 2 a 5; paquete B = 7 noches,
mar los días 2 a 7; días seguidos, sin descanso; el día 1 es solo llegada.

- ★ **¿Qué se hace cada día de mar?** ¿Pesca con mosca todos los días, avistamiento todos los
  días, o una mezcla? ¿El cliente elige la actividad de cada día o ya viene fija en el paquete?
- ★ **$45,000 y $52,500 por persona: ¿en qué ocupación?** ¿Habitación compartida de dos?
  ¿Cuánto cuesta una persona sola (suplemento individual)? ¿Hay precio para niños?
- **¿Cuántas personas mínimo y máximo por paquete?**
- **¿Qué incluye el precio?** Comidas, licencia de pesca, equipo de pesca con mosca, carnada o
  señuelos, propinas, impuestos.
- **¿Se puede pagar un anticipo?** ¿De qué porcentaje? ¿Cuándo se paga el resto?
- **¿Qué fechas de llegada se aceptan?** ¿Cualquier día del año, solo en temporada, solo
  ciertos días de la semana?
- **Cancelación y mal clima:** ¿se reembolsa completo, se reprograma, o se pierde la salida? ¿Y
  si el cliente cancela por su cuenta?
- **¿Algún paquete más adelante?** (por ejemplo, de 3 días o por temporada).

## 2. Hospedaje

La Ventana Travel es dueña del hotel. Hoy hay 4 habitaciones demo (3 de 2 personas y 1 de 4).

- ★ **¿Cuántas habitaciones hay y de qué capacidad cada una?** ¿Qué tipo de camas?
- **¿El hospedaje se vende suelto**, sin paquete? Si sí, ¿a qué precio por noche, en MXN y USD?
  Hoy tiene 2,500 MXN / 145 USD por noche solo como demo.
- **Hora de entrada y salida.**
- **¿Incluye desayuno u otras comidas?**
- **Política de niños y de mascotas.**
- **¿Se bloquean habitaciones por mantenimiento o por temporada?**

## 3. Traslado de aeropuerto

Lo da La Ventana Travel. Hoy hay dos tarifas demo de "redondo con aeropuerto": 1 a 4 personas
a 3,500 MXN y 5 o más a 6,500 MXN.

- ★ **¿Qué aeropuerto es?** (La Paz, Los Cabos u otro.) ¿Es el mismo para llegar y para salir?
- ★ **Tarifa real** por rango de personas, en MXN.
- **¿Cuántas personas caben por vehículo y cuántos vehículos hay?**
- **¿Cómo avisa el cliente su vuelo y su hora?** ¿Se pide el número de vuelo al reservar?
- **Qué pasa si el vuelo se retrasa o se cancela.**

## 4. Servicios sueltos

Cada uno hoy tiene precio y flota demo.

**Pesca con mosca** (hoy 6,000 MXN / 350 USD por grupo, 2 personas incluidas, máximo 3):
- ¿Se cobra por grupo o por persona? Precio real en MXN y USD.
- Personas incluidas y máximo por embarcación. Cargo por persona extra.
- Horario de salida y duración.
- ¿Incluye equipo, carnada, licencia, comida?
- Cuántas embarcaciones y capitanes hay, y de qué capacidad.

**Avistamiento de ballenas y orcas** (hoy 1,200 MXN / 70 USD por persona, máximo 12):
- ¿Se cobra por persona? Precio real. ¿Es el mismo precio para ballenas y para orcas?
- ¿Cuándo es temporada de cada una? ¿Se vende todo el año?
- Capacidad por lancha y cuántas lanchas hay.
- Horario y duración.
- **¿Qué pasa si no se ve ningún animal?** ¿Hay reprogramación o reembolso?
- ¿Mínimo de personas para que salga?

## 5. Dinero y datos de la empresa

- ★ **Tipo de cambio para los precios en USD de los paquetes.** El dueño pidió convertir de
  pesos a dólares y redondear hacia abajo los centavos; falta el tipo de cambio y si se
  actualiza o queda fijo.
- **Cuenta de Stripe propia de La Ventana Travel.** Cada empresa cobra directo: necesitamos sus
  llaves (secreta, publicable y secreto del webhook) y el webhook configurado en su cuenta.
- **Datos fiscales** para facturar, si aplica.
- **WhatsApp y correo de contacto** de la empresa, para los avisos al cliente.

## 6. Contenido del sitio

- **Fotos** de los servicios, del hotel y de los paquetes (las fotos van por el backoffice).
- **Textos de la página de La Ventana**, hoy "próximamente".
- **Deslinde y términos** propios de la empresa, si los tiene distintos a los de Sal y Sol.

---

# Pendientes de otras empresas (datos demo hoy)

**Piratas Adventures (Puerto Chale):** precios reales de safari marino (hoy 900/55 por
persona), avistamiento de ballenas (1,100/65) y pesca deportiva (5,000/290 por grupo); flota
real; cupo y horarios; llaves de Stripe (hoy placeholder, el checkout responde 503 hasta
cargarlas); si habrá paquetes y de qué tipo.

**DLS Transporte (La Paz):** tarifas reales de los 3 traslados (hoy son demo); puntos de
encuentro reales; si el nombre del sitio sigue siendo "Transportes La Paz" o pasa a "DLS".

**Sal y Sol Sportfishing:** confirmar que pesca deportiva es su único servicio y que los
precios del catálogo ya son los reales.

## Decisiones del dueño (2026-10-01)

- Cada día de mar es UNA sola actividad: avistamiento de ballenas y orcas (un solo servicio). Sin elección por día.
- No hay precio para niños. Habitaciones y capacidades demo por ahora.
- Traslado y hospedaje no bajan el precio si alguien no los usa: el precio es por persona fija.
- Tipo de cambio: se actualizará según el cambio actual; por ahora 1 USD = 18 MXN, centavos hacia abajo (A = 2,500.00 USD, B = 2,916.66 USD).
- Paquetes sembrados en local: `paquete-5-noches` y `paquete-7-noches` (capacidad demo 10 personas).
