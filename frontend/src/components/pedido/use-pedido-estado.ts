import { useReducer, type Dispatch } from 'react';
import type { PaqueteCatalogo } from '@/lib/api';
import {
  estadoInicial, reducirPedido, type AccionPedido, type EstadoPedido, type OpcionesEstadoInicial,
} from '@/lib/pedido-estado';

export function usePedidoEstado(
  paquete: PaqueteCatalogo,
  opciones: OpcionesEstadoInicial,
): [EstadoPedido, Dispatch<AccionPedido>] {
  return useReducer(reducirPedido, undefined, () => estadoInicial(paquete, opciones));
}
