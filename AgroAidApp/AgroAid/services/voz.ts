import { apiFetch } from '@/services/api';
import type { ConsultaResponse } from '@/services/consultas';
export type TranscripcionResponse {
    text:string;
}
function createAudioData(uri:string,mimeType='audio/m4a'){
    const formData=new FormData();
    const extension=mimeType.split('/')[1] ?? 'm4a';
    formData.append(
        'file', {
            uri,
            name: `consulta-voz.${extension}`,
            type: mimeType
        } as unknown as Blob);
    return formData;
}
export function transcribirAudio(uri: string, mimeType = 'audio/m4a'){
    return apiFetch<TranscripcionResponse>('/api/voz/transcribir',{
        method:'POST',
        body:createAudioData(uri,mimeType)
    })
}
export function vozConsulta(uri: string, mimeType = 'audio/m4a'){
    return apiFetch<ConsultaResponse>('/api/voz/consulta',{
        method:'POST',
        body:createAudioData(uri,mimeType)
    })
}