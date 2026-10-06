import { apiFetch, buildUrl } from '@/services/api';

export type PreAplicacionRequest = {
  lat: number;
  lon: number;
  producto: string;
  dosis_l_ha?: number | null;
  cultivo?: string | null;
  distancia_agua_m: number;
  hora_aplicacion?: string | null;
  tipo_equipo?: string;
  epp_disponible?: string[];
};

export type PreAplicacionCheck = {
  check: string;
  resultado: 'GO' | 'NO-GO' | 'PRECAUCION' | string;
  detalle: string;
};

export type PreAplicacionEvaluacion = {
  resultado_global: 'GO' | 'NO-GO' | string;
  hora_evaluacion: string;
  clima: Record<string, unknown>;
  checks: PreAplicacionCheck[];
  recomendacion: string;
};

export type PreAplicacionRegistro = {
  id: number;
  pdf_path: string | null;
  pdf_url?: string;
  resultado_global: string;
};

export type PreAplicacionResponse = {
  evaluacion: PreAplicacionEvaluacion;
  registro: PreAplicacionRegistro;
};

export function evaluarPreAplicacion(payload: PreAplicacionRequest) {
  return apiFetch<PreAplicacionResponse>('/api/pre-aplicacion', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function preAplicacionPdfUrl(registro: PreAplicacionRegistro) {
  return buildUrl(registro.pdf_url ?? `/api/pre-aplicacion/${registro.id}/pdf`);
}
