export type Receta = {
  id: string;
  titulo: string;
  cultivo: string;
  descripcion: string;
  riesgo: 'BAJO' | 'MEDIO' | 'ALTO' | 'CRITICO';
  pdfUrl?: string;
};

const recetasDemo: Receta[] = [
  {
    id: 'bpa-fit',
    titulo: 'Buenas practicas para fitosanitarios',
    cultivo: 'General',
    descripcion:
      'Checklist preventivo: etiqueta, EPP, viento, distancia a viviendas y asesor tecnico.',
    riesgo: 'ALTO'
  },
  {
    id: 'estres-termico',
    titulo: 'Prevencion de estres termico',
    cultivo: 'Ganaderia y campo',
    descripcion:
      'Pautas para ajustar horarios de trabajo y monitorear condiciones climaticas.',
    riesgo: 'MEDIO'
  }
];

export async function getRecetas(): Promise<Receta[]> {
  return recetasDemo;
}

export async function crearReceta(receta: Omit<Receta, 'id'>): Promise<Receta> {
  return {
    ...receta,
    id: `local-${Date.now()}`
  };
}

export async function descargarPDF(recetaId: string) {
  return recetasDemo.find((receta) => receta.id === recetaId)?.pdfUrl ?? null;
}
