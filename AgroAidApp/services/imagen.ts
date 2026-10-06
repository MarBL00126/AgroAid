import { apiFetch } from './api';
import type { ConsultaResponse } from './consultas';

export type EtiquetaParseada = {
  producto: string | null;
  principio_activo: string | null;
  cultivos_o_especies_permitidos: string[] | null;
  dosis_recomendada: string | null;
  intervalo_carencia_dias: number | null;
  epp_requerido: string[] | null;
  categoria_toxicologica: string | null;
  frases_de_seguridad: string[] | null;
  texto_completo_visible: string | null;
};

export type ImagenConsultaResult = {
  etiqueta_parseada: EtiquetaParseada;
  consulta_generada: string;
  evaluacion: ConsultaResponse;
};

/**
 * Envía una foto de etiqueta de agroquímico al backend.
 * Gemini Vision extrae los datos y corre el safety chain.
 * @param imageUri   URI local de la imagen (expo-camera / expo-image-picker)
 * @param mimeType   MIME type — 'image/jpeg' por defecto
 */
export async function analizarEtiqueta(
  imageUri: string,
  mimeType = 'image/jpeg'
): Promise<ImagenConsultaResult> {
  const formData = new FormData();
  const filename = imageUri.split('/').pop() ?? 'etiqueta.jpg';

  formData.append('file', {
    uri: imageUri,
    type: mimeType,
    name: filename,
  } as unknown as Blob);

  return apiFetch<ImagenConsultaResult>('/api/consulta/imagen', {
    method: 'POST',
    body: formData,
  });
}
