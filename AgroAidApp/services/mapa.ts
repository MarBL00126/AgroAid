export type EventoTipo =
  | 'clima'
  | 'plaga'
  | 'enfermedad'
  | 'incendio'
  | 'agua'
  | 'otro';

export type EventoMapa = {
  id: string;
  tipo: EventoTipo;
  titulo: string;
  descripcion: string;
  lat: number;
  lon: number;
  fecha: string;
  riesgo: 'BAJO' | 'MEDIO' | 'ALTO' | 'CRITICO';
};

const eventosDemo: EventoMapa[] = [
  {
    id: 'demo-helada',
    tipo: 'clima',
    titulo: 'Riesgo de helada',
    descripcion: 'Productores reportaron descenso fuerte de temperatura.',
    lat: -34.6037,
    lon: -58.3816,
    fecha: new Date().toISOString(),
    riesgo: 'MEDIO'
  },
  {
    id: 'demo-plaga',
    tipo: 'plaga',
    titulo: 'Monitoreo de plaga',
    descripcion: 'Revisar lotes cercanos y confirmar con asesor tecnico.',
    lat: -34.72,
    lon: -58.26,
    fecha: new Date().toISOString(),
    riesgo: 'ALTO'
  }
];

export async function getEventos(): Promise<EventoMapa[]> {
  return eventosDemo;
}

export async function reportarEvento(evento: Omit<EventoMapa, 'id' | 'fecha'>) {
  return {
    ...evento,
    id: `local-${Date.now()}`,
    fecha: new Date().toISOString()
  };
}
