import { apiFetch } from './api';
import type { ConsultaResponse } from './consultas';

export type TranscripcionResult = {
  text: string;
};

/**
 * Envía un archivo de audio al backend (Gemini) y devuelve el texto transcripto.
 * @param audioUri  URI local del audio (resultado de expo-av)
 * @param mimeType  MIME type del audio — 'audio/m4a' (iOS) o 'audio/webm' (Android)
 */
export async function transcribirAudio(
  audioUri: string,
  mimeType = 'audio/m4a'
): Promise<TranscripcionResult> {
  const formData = new FormData();
  const filename = audioUri.split('/').pop() ?? 'audio.m4a';

  formData.append('file', {
    uri: audioUri,
    type: mimeType,
    name: filename,
  } as unknown as Blob);

  return apiFetch<TranscripcionResult>('/api/voz/transcribir', {
    method: 'POST',
    body: formData,
  });
}

/**
 * Transcribe el audio Y corre el flujo completo de consulta.
 * Devuelve la respuesta de la primera iteración (igual que POST /api/consulta).
 */
export async function vozConsulta(
  audioUri: string,
  mimeType = 'audio/m4a'
): Promise<ConsultaResponse> {
  const formData = new FormData();
  const filename = audioUri.split('/').pop() ?? 'audio.m4a';

  formData.append('file', {
    uri: audioUri,
    type: mimeType,
    name: filename,
  } as unknown as Blob);

  return apiFetch('/api/voz/consulta', {
    method: 'POST',
    body: formData,
  });
}
