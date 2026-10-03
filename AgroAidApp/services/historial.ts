import { apiFetch } from '@/services/api';

export type HistorialItem = {
  consulta_id: number;
  consulta_inicial: string;
  fecha_consulta: string;
  se_abstuvo: boolean;
  nivel_riesgo: string;
  confianza_final: number;
  evidencia_suficiente: boolean;
  iteraciones: number;
  duracion_seg: number;
};

export type HistorialResponse = {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
  items: HistorialItem[];
};

export type HistorialFilters = {
  page?: number;
  per_page?: number;
  fecha_desde?: string;
  fecha_hasta?: string;
  nivel_riesgo?: string;
};

type HistorialQuery = HistorialFilters & {
  format?: 'csv' | 'xlsx';
};

function buildQuery(filters: HistorialQuery = {}) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && String(value).trim() !== '') {
      params.set(key, String(value));
    }
  });

  const query = params.toString();
  return query ? `?${query}` : '';
}

export function getHistorial(filters: HistorialFilters = {}) {
  return apiFetch<HistorialResponse>(`/api/historial${buildQuery(filters)}`);
}

export function exportarCSV(
  filters: Omit<HistorialFilters, 'page' | 'per_page'> = {}
) {
  return apiFetch<string>(
    `/api/historial/export${buildQuery({ ...filters, format: 'csv' })}`
  );
}
