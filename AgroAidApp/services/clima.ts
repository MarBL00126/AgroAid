import { apiFetch } from '@/services/api';

export type ClimaResponse = {
  temperatura?: number;
  humedad?: number;
  viento_kmh?: number;
  descripcion?: string;
  alerta?: string | null;
  [key: string]: unknown;
};

export function getClima(lat: number, lon: number) {
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon)
  });

  return apiFetch<ClimaResponse>(`/api/clima?${params}`);
}
