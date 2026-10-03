import { apiFetch } from '@/services/api';
export type NivelRiesgo= 'BAJO' | 'MEDIO' | 'ALTO' | 'CRITICO' | string;
export type ConsultaResponse={
  consulta_id: number;
  iteracion: number;
  max_iteraciones: number;
  completado: boolean;
  confianza: number;
  nivel_riesgo: NivelRiesgo;
  evidencia_suficiente: boolean;
  dominios_detectados: string[];
  justificacion: string;
  riesgos_detectados: string[];
  informacion_faltante: string[];
  preguntas_seguimiento: string[];
  debe_abstenerse: boolean;
  marco_regulatorio_aplicable: string[];
  requiere_profesional: boolean;
  evaluacion_final: string | null;
  verificacion_evidencia: Record<string, unknown> | null;
  se_abstuvo_final: boolean;
}
export type IniciarConsultaPayload={
    consulta_inicial:string;
    tenent_slug?:string;
    lat?:number;
    lon?:number;
    umbral_confianza?:number;
    max_iteraciones?:number;
}
export function iniciarConsulta(payload:IniciarConsultaPayload){
    return apiFetch<ConsultaResponse>('api/consulta',{
        method:'POST',
        body:JSON.stringify({
            tenant_slug:'default',
            umbral_confianza:80,
            max_iteraciones:5,
            payload
        })
    });
}
export function responderConsulta(consultaId:number,respuesta:string){
    return apiFetch<ConsultaResponse>(`/api/consulta/${consultaId}/responder`,{
        method:'POST',
        body:JSON.stringify({
            respuesta
        })
    });
}
export function getConsulta(consultaId:number){
    return apiFetch<ConsultaResponse>(`/api/consulta/${consultaId}`);
}
export function descartarConsulta(consultaId: number) {
  return apiFetch<{ ok: boolean; consulta_id: number }>(
    `/api/consulta/${consultaId}`,
    { method: 'DELETE' }
  );
}