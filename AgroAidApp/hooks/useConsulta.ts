import { useCallback, useState } from 'react';
import {
  descartarConsulta,
  getConsulta,
  iniciarConsulta,
  responderConsulta,
  type ConsultaResponse,
  type IniciarConsultaPayload
} from '@/services/consultas';

export function useConsulta() {
  const [consulta, setConsulta] = useState<ConsultaResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const iniciar = useCallback(async (payload: IniciarConsultaPayload) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await iniciarConsulta(payload);
      setConsulta(data);
      return data;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'No se pudo iniciar la consulta.';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const responder = useCallback(
    async (respuesta: string) => {
      if (!consulta) {
        return null;
      }

      setIsLoading(true);
      setError(null);

      try {
        const data = await responderConsulta(consulta.consulta_id, respuesta);
        setConsulta(data);
        return data;
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'No se pudo enviar la respuesta.';
        setError(message);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [consulta]
  );

  const cargar = useCallback(async (consultaId: number) => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getConsulta(consultaId);
      setConsulta(data);
      return data;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(async () => {
    if (consulta) {
      await descartarConsulta(consulta.consulta_id).catch(() => undefined);
    }

    setConsulta(null);
    setError(null);
  }, [consulta]);

  return {
    consulta,
    error,
    isLoading,
    iniciar,
    responder,
    cargar,
    reset
  };
}
