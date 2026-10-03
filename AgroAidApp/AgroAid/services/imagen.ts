import { apiFetch } from '@/services/api';
import type { ConsultaResponse } from '@/services/consultas';
export type EtiquetaParseada = {
  producto?: string | null;
  principio_activo?: string | null;
  cultivos_o_especies_permitidos?: string[] | null;
  dosis_recomendada?: string | null;
  intervalo_carencia_dias?: number | null;
  epp_requerido?: string[] | null;
  categoria_toxicologica?: string | null;
  frases_de_seguridad?: string[] | null;
  texto_completo_visible?: string | null;
  [key: string]: unknown;
};
export type ImagenConsultaResponse = {
  etiqueta_parseada: EtiquetaParseada;
  consulta_generada: string;
  evaluacion: ConsultaResponse;
};
function createImageFormData(uri: string, mimeType = 'image/jpeg') {
  const formData = new FormData();
  const extension = mimeType.split('/')[1] ?? 'jpg';
  formData.append('file', {
    uri,
    name: `etiqueta.${extension}`,
    type: mimeType
  } as unknown as Blob);
  return formData;
}
export function analizarEtiqueta(uri: string, mimeType = 'image/jpeg') {
  return apiFetch<ImagenConsultaResponse>('/api/consulta/imagen', {
    method: 'POST',
    body: createImageFormData(uri, mimeType)
  });
}