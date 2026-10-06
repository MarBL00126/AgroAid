import { apiFetch, buildUrl } from '@/services/api';

export type Receta = {
  id: number;
  numero_receta: string;
  producto: string;
  principio_activo: string | null;
  cultivo: string;
  lote: string | null;
  superficie_ha: number | null;
  dosis: string;
  volumen_agua: string | null;
  fecha_aplicacion: string | null;
  observaciones?: string | null;
  nivel_riesgo: string | null;
  estado: 'borrador' | 'emitida' | 'anulada' | string;
  pdf_path: string | null;
  pdf_url?: string;
  created_at?: string;
};

export type RecetaCreate = {
  consulta_id?: number | null;
  producto: string;
  principio_activo?: string | null;
  cultivo: string;
  lote?: string | null;
  superficie_ha?: number | null;
  dosis: string;
  volumen_agua?: string | null;
  fecha_aplicacion?: string | null;
  observaciones?: string | null;
  nivel_riesgo?: string | null;
};

export function getRecetas(page = 1, pageSize = 20) {
  return apiFetch<Receta[]>(
    `/api/recetas?page=${page}&page_size=${pageSize}`
  );
}

export function crearReceta(receta: RecetaCreate) {
  return apiFetch<Receta>('/api/recetas', {
    method: 'POST',
    body: JSON.stringify(receta)
  });
}

export function cambiarEstadoReceta(
  recetaId: number,
  estado: 'emitir' | 'anular'
) {
  return apiFetch<Receta>(`/api/recetas/${recetaId}/${estado}`, {
    method: 'PUT'
  });
}

export function recetaPdfUrl(receta: Pick<Receta, 'id' | 'pdf_url'>) {
  return buildUrl(receta.pdf_url ?? `/api/recetas/${receta.id}/pdf`);
}
