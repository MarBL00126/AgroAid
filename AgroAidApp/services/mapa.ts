import { apiFetch } from '@/services/api';

export type EventoTipo = 'plaga' | 'enfermedad' | 'contaminacion' | 'incendio';

export type EventoMapa = {
  id: number;
  tenant_id: number;
  user_id: number | null;
  tipo: EventoTipo;
  descripcion: string | null;
  lat: number;
  lon: number;
  nivel_riesgo: 'BAJO' | 'MEDIO' | 'ALTO' | 'CRITICO' | string;
  radio_km: number;
  verificado: boolean;
  created_at: string;
  distancia_km?: number;
};

export type EventoCreate = {
  lat: number;
  lon: number;
  tipo: EventoTipo;
  descripcion?: string | null;
  nivel_riesgo?: string | null;
  radio_km?: number;
};

export function getEventos(params: {
  lat: number;
  lon: number;
  radio_km?: number;
}) {
  const search = new URLSearchParams({
    lat: String(params.lat),
    lon: String(params.lon),
    radio_km: String(params.radio_km ?? 100)
  });

  return apiFetch<EventoMapa[]>(`/api/mapa/eventos?${search.toString()}`);
}

export function reportarEvento(evento: EventoCreate) {
  return apiFetch<EventoMapa>('/api/mapa/eventos', {
    method: 'POST',
    body: JSON.stringify(evento)
  });
}
