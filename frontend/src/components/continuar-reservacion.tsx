'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, m, useReducedMotion } from 'framer-motion';
import type { Dictionary, Locale } from '@/app/[lang]/dictionaries';
import { cancelarOrdenPublica, getResumenOrden, getResumenReserva, type ResumenOrden, type ResumenReserva } from '@/lib/api';
import { tieneWhatsapp, whatsappHref } from '@/lib/contacto';
import { borrarPendiente, guardarPendiente, listarPendientes, type Pendiente } from '@/lib/pendientes';
import { textoDeSituacion } from '@/lib/pendientes-texto';
import { AlertDialog } from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';

type Resumen = ResumenReserva | ResumenOrden;
type Problema = 'sinConexion' | 'errorServidor';
type Props = { lang: Locale; dict: Pick<Dictionary, 'continuar'> };

function resumenNoExiste(p: Pendiente): Resumen {
  return {
    situacion: 'no_existe', producto: p.productoNombre, monto: null,
    moneda: 'MXN', forma_pago: '', folio: 0, vence_en: null,
  };
}

function rutaSegura(ruta: string, lang: Locale): string | null {
  try {
    const url = new URL(ruta, window.location.origin);
    if (url.origin !== window.location.origin || !/^\/(?:es|en)\/(?:reservar|traslados)\/?$/.test(url.pathname)) return null;
    url.pathname = url.pathname.replace(/^\/(?:es|en)\//, `/${lang}/`);
    return url.pathname + url.search;
  } catch {
    return null;
  }
}

function fechaRelativa(iso: string, dict: Dictionary['continuar']): string {
  const minutos = Math.max(1, Math.floor((Date.now() - Date.parse(iso)) / 60000));
  const horas = Math.floor(minutos / 60);
  return (horas ? dict.haceHoras : dict.haceMinutos).replace('{n}', String(horas || minutos));
}

function montoRetenido(resumen: Resumen, locale: string): string | null {
  if (!('montos' in resumen)) return null;
  const retenido = resumen.montos.find(m => m.estado === 'requires_capture' && m.monto !== null);
  if (!retenido?.monto || !Number.isFinite(Number(retenido.monto))) return null;
  try {
    return new Intl.NumberFormat(locale, { style: 'currency', currency: resumen.moneda }).format(Number(retenido.monto));
  } catch {
    return `${retenido.monto} ${resumen.moneda}`;
  }
}

export function ContinuarReservacion({ lang, dict }: Props) {
  const router = useRouter();
  const sinMovimiento = useReducedMotion();
  const [pendientes, setPendientes] = useState<Pendiente[]>([]);
  const [activo, setActivo] = useState<Pendiente | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [problema, setProblema] = useState<Problema | null>(null);
  const [listaAbierta, setListaAbierta] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const [deshecho, setDeshecho] = useState<Pendiente | null>(null);
  const secuencia = useRef(0);
  const timerDeshacer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timerOcultar = useRef<ReturnType<typeof setTimeout> | null>(null);

  const consultar = useCallback(async (p: Pendiente) => {
    const turno = ++secuencia.current;
    setResumen(null);
    setProblema(null);
    if (!navigator.onLine) {
      setProblema('sinConexion');
      return;
    }
    try {
      const respuesta = p.tipo === 'orden'
        ? await getResumenOrden(p.checkoutId, p.sedeSlug ?? '')
        : await getResumenReserva(p.checkoutId, p.empresaSlug);
      if (turno === secuencia.current) setResumen(respuesta);
    } catch (error) {
      if (turno !== secuencia.current) return;
      const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined;
      if (status === 404) setResumen(resumenNoExiste(p));
      else setProblema(status === 0 || !navigator.onLine ? 'sinConexion' : 'errorServidor');
    }
  }, []);

  useEffect(() => {
    const lista = listarPendientes();
    const secuenciaMontada = secuencia;
    // Lectura de localStorage solo tras hidratar: SSR y primer render son vacíos.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPendientes(lista);
    if (lista[0]) {
      setActivo(lista[0]);
      void consultar(lista[0]);
    }
    return () => { secuenciaMontada.current++; };
  }, [consultar]);

  useEffect(() => {
    const alVolver = () => { if (activo && problema === 'sinConexion') void consultar(activo); };
    window.addEventListener('online', alVolver);
    return () => window.removeEventListener('online', alVolver);
  }, [activo, problema, consultar]);

  useEffect(() => () => {
    if (timerDeshacer.current) clearTimeout(timerDeshacer.current);
    if (timerOcultar.current) clearTimeout(timerOcultar.current);
  }, []);

  const siguiente = (sin: string) => {
    const restantes = pendientes.filter(p => p.checkoutId !== sin);
    setPendientes(restantes);
    setActivo(restantes[0] ?? null);
    setResumen(null);
    setProblema(null);
    setListaAbierta(false);
    if (restantes[0]) void consultar(restantes[0]);
  };

  const cerrar = () => {
    if (!activo) return;
    borrarPendiente(activo.checkoutId);
    siguiente(activo.checkoutId);
  };

  // El checkout guarda su propio punto de reanudacion en sessionStorage, aparte
  // del puntero de esta banda. Descartar tiene que soltar los dos: si solo se
  // borraba el puntero, al volver al mismo producto el checkout se reanudaba
  // solo desde la sesion y volvia a escribir el puntero.
  const claveDeSesion = (p: Pendiente): string | null => {
    const ruta = rutaSegura(p.ruta, lang);
    if (!ruta) return null;
    const destino = new URL(ruta, window.location.origin);
    if (destino.pathname.endsWith('/traslados')) return 'salysol:traslados:checkout_id';
    if (destino.searchParams.has('paquete')) return `salysol:pedido:${p.productoSlug}`;
    return 'salysol:checkout-id';
  };

  const soltarSesion = (p: Pendiente) => {
    const clave = claveDeSesion(p);
    if (!clave) return;
    try {
      const guardado = sessionStorage.getItem(clave);
      if (!guardado) return;
      // Solo si es el checkout descartado: otro en curso del mismo producto no se toca.
      const id = guardado.startsWith('{') ? (JSON.parse(guardado) as { checkoutId?: string }).checkoutId : guardado;
      if (id === p.checkoutId) sessionStorage.removeItem(clave);
    } catch {
      // sessionStorage bloqueado o JSON invalido: no hay nada que reanudar.
    }
  };

  const restaurarSesion = (p: Pendiente) => {
    const clave = claveDeSesion(p);
    if (!clave) return;
    try {
      sessionStorage.setItem(
        clave,
        clave.startsWith('salysol:pedido:') ? JSON.stringify({ checkoutId: p.checkoutId, ordenId: p.ordenId }) : p.checkoutId,
      );
    } catch {
      // sin sessionStorage el puntero de la banda sigue funcionando.
    }
  };

  const descartar = () => {
    if (!activo) return;
    const guardado = activo;
    borrarPendiente(guardado.checkoutId);
    soltarSesion(guardado);
    setDeshecho(guardado);
    if (timerDeshacer.current) clearTimeout(timerDeshacer.current);
    timerDeshacer.current = setTimeout(() => setDeshecho(null), 8000);
    siguiente(guardado.checkoutId);
  };

  const deshacer = () => {
    if (!deshecho) return;
    guardarPendiente(deshecho);
    restaurarSesion(deshecho);
    if (timerDeshacer.current) clearTimeout(timerDeshacer.current);
    setDeshecho(null);
    const lista = listarPendientes();
    setPendientes(lista);
    setActivo(lista[0] ?? null);
    if (lista[0]) void consultar(lista[0]);
  };

  const navegar = (p: Pendiente, nueva: boolean) => {
    const ruta = rutaSegura(p.ruta, lang);
    if (!ruta) return;
    const destino = new URL(ruta, window.location.origin);
    if (nueva) {
      destino.searchParams.delete('retomar');
      borrarPendiente(p.checkoutId);
      if (destino.pathname.endsWith('/traslados')) sessionStorage.removeItem('salysol:traslados:checkout_id');
      else if (destino.searchParams.has('paquete')) sessionStorage.removeItem(`salysol:pedido:${p.productoSlug}`);
      else sessionStorage.removeItem('salysol:checkout-id');
    } else if (destino.searchParams.has('paquete')) {
      sessionStorage.setItem(`salysol:pedido:${p.productoSlug}`, JSON.stringify({ checkoutId: p.checkoutId, ordenId: p.ordenId }));
      // retomar sobreescribe el JSON y perdería ordenId: aquí manda la sesión sembrada.
      destino.searchParams.delete('retomar');
    } else if (destino.pathname.endsWith('/traslados')) {
      sessionStorage.setItem('salysol:traslados:checkout_id', p.checkoutId);
    } else {
      sessionStorage.setItem('salysol:checkout-id', p.checkoutId);
    }
    router.push(destino.pathname + destino.search);
  };

  const cancelar = async () => {
    const ordenId = activo?.ordenId ?? (resumen && 'montos' in resumen ? resumen.folio : null);
    if (!activo?.sedeSlug || !ordenId) {
      setConfirmando(false);
      setProblema('errorServidor');
      return;
    }
    setCancelando(true);
    try {
      const resultado = await cancelarOrdenPublica(activo.sedeSlug, ordenId, activo.checkoutId);
      setResumen(resultado);
      setProblema(null);
      setConfirmando(false);
      if (resultado.situacion === 'cancelada_liberada') {
        borrarPendiente(activo.checkoutId);
        const id = activo.checkoutId;
        setPendientes(actual => actual.filter(p => p.checkoutId !== id));
        timerOcultar.current = setTimeout(() => siguiente(id), 3000);
      }
    } catch (error) {
      const detail = error && typeof error === 'object' && 'detail' in error ? error.detail : null;
      if (detail && typeof detail === 'object' && 'situacion' in detail && 'montos' in detail) {
        setResumen(detail as ResumenOrden);
        setConfirmando(false);
      } else {
        setProblema(!navigator.onLine ? 'sinConexion' : 'errorServidor');
        setConfirmando(false);
      }
    } finally {
      setCancelando(false);
    }
  };

  const textos = dict.continuar;
  const situacion = resumen?.situacion;
  const contenido = resumen ? textoDeSituacion(textos, resumen) : null;
  const linea = problema && activo ? textos[problema].replace('{producto}', activo.productoNombre) : contenido?.linea1;
  const whatsapp = resumen && tieneWhatsapp
    ? whatsappHref((situacion === 'no_existe' ? textos.whatsappNoExiste : textos.whatsappFolio)
      .replace('{folio}', String(resumen.folio)).replace('{producto}', resumen.producto))
    : null;
  const principalWhatsApp = situacion === 'cancelada_devolucion_solicitada' || situacion === 'cancelada_devolucion_por_confirmar';
  const principal = problema ? textos.botonReintentar : principalWhatsApp && !whatsapp ? null : contenido?.principal;
  const secundaria = problema === 'errorServidor' ? textos.botonIrReservacion
    : problema ? null : situacion === 'no_existe' && !whatsapp ? null : contenido?.secundaria;
  const registro = contenido?.registro ?? 'informativo';
  const estilo = registro === 'con_dinero'
    ? 'border-accent bg-[color-mix(in_srgb,var(--accent)_10%,var(--superficie))]'
    : registro === 'en_curso' ? 'border-border-strong bg-surface' : 'border-border bg-superficie';
  const otros = pendientes.filter(p => p.checkoutId !== activo?.checkoutId).slice(0, 3);

  const principalClick = () => {
    if (!activo) return;
    if (problema) { void consultar(activo); return; }
    if (principalWhatsApp && whatsapp) { window.open(whatsapp, '_blank', 'noopener,noreferrer'); return; }
    if (situacion === 'no_existe' || situacion === 'cancelada_liberada' || situacion === 'expirada') {
      navegar(activo, true);
      if (situacion === 'no_existe') cerrar();
      return;
    }
    navegar(activo, false);
  };

  const secundariaClick = () => {
    if (!activo) return;
    if (problema === 'errorServidor') { navegar(activo, false); return; }
    if (situacion === 'sin_pago') { descartar(); return; }
    if (situacion === 'retenido_parcial') { setConfirmando(true); return; }
    if (situacion === 'no_existe') { if (whatsapp) window.open(whatsapp, '_blank', 'noopener,noreferrer'); cerrar(); return; }
    cerrar();
  };

  const aviso = activo && linea && (resumen || problema) ? (
    <div role="status" aria-live="polite" className={`border ${estilo} px-5 py-4 sm:px-8`}>
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-relaxed text-foreground">{linea}</p>
          <p className="mt-1 text-xs text-muted">{fechaRelativa(activo.actualizadoEn, textos)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {principal && <Button variante="libre" onClick={principalClick} className="min-h-11 bg-action px-4 py-2 text-sm font-semibold text-white hover:opacity-90">{principal}</Button>}
          {secundaria && <Button variante="libre" onClick={secundariaClick} className="min-h-11 border border-border-strong px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-deep">{secundaria}</Button>}
          {otros.length > 0 && <Button variante="libre" aria-expanded={listaAbierta} onClick={() => setListaAbierta(v => !v)} className="min-h-11 px-2 text-sm font-medium text-accent underline">{textos.yMas.replace('{n}', String(otros.length))}</Button>}
        </div>
      </div>
      {listaAbierta && otros.length > 0 && <div className="mx-auto mt-3 max-w-[1440px] border-t border-border pt-2">
        {otros.map(p => <Button key={p.checkoutId} variante="libre" onClick={() => { if (timerOcultar.current) clearTimeout(timerOcultar.current); setActivo(p); setListaAbierta(false); void consultar(p); }} className="flex min-h-11 w-full items-center justify-between gap-3 border-b border-border px-2 py-2 text-left text-sm text-foreground last:border-b-0 hover:bg-surface-deep"><span>{p.productoNombre}</span><span className="shrink-0 text-xs text-muted">{fechaRelativa(p.actualizadoEn, textos)}</span></Button>)}
      </div>}
    </div>
  ) : null;

  const deshacerAviso = deshecho && <div role="status" aria-live="polite" className="border border-border bg-surface px-5 py-3 text-sm text-foreground">
    {textos.descartada.replace('{producto}', deshecho.productoNombre)}{' '}
    <Button variante="libre" onClick={deshacer} className="font-semibold text-accent underline">{textos.deshacer}</Button>
  </div>;

  const montoCancelar = resumen ? montoRetenido(resumen, textos.locale) : null;
  const dialogo = <AlertDialog
    abierto={confirmando && !!resumen}
    titulo={textos.confirmarCancelarTitulo}
    cuerpo={(montoCancelar ? textos.confirmarCancelarCuerpo : textos.confirmarCancelarSinMonto).replace('{monto}', montoCancelar ?? '')}
    etiquetaSegura={textos.confirmarCancelarVolver}
    etiquetaDestructiva={textos.confirmarCancelarSi}
    onSegura={() => setConfirmando(false)}
    onDestructiva={() => { if (!cancelando) void cancelar(); }}
  />;

  if (!aviso && !deshacerAviso) return null;
  return <>
    <AnimatePresence initial={false}>
      {(aviso || deshacerAviso) && <m.div key="continuar-banda" initial={sinMovimiento ? false : { height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={sinMovimiento ? { opacity: 0 } : { height: 0, opacity: 0 }} transition={{ duration: sinMovimiento ? 0 : 0.25 }} className="overflow-hidden">
        {aviso}{deshacerAviso}
      </m.div>}
    </AnimatePresence>
    {dialogo}
  </>;
}
