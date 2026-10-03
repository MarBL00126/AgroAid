import { StyleSheet, Text, View } from 'react-native';

import { RiesgoChip } from '@/components/RiesgoChip';
import { colors } from '@/constants/colors';
import type { ConsultaResponse } from '@/services/consultas';

type Props = {
  consulta: ConsultaResponse;
};

export function ConsultaCard({ consulta }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>Consulta #{consulta.consulta_id}</Text>
        <RiesgoChip nivel={consulta.nivel_riesgo} />
      </View>

      <Text style={styles.meta}>
        Iteracion {consulta.iteracion} de {consulta.max_iteraciones} -
        Confianza {consulta.confianza}%
      </Text>

      {consulta.justificacion ? (
        <Text style={styles.body}>{consulta.justificacion}</Text>
      ) : null}

      {consulta.riesgos_detectados.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Riesgos detectados</Text>
          {consulta.riesgos_detectados.map((riesgo) => (
            <Text key={riesgo} style={styles.item}>
              - {riesgo}
            </Text>
          ))}
        </View>
      ) : null}

      {consulta.preguntas_seguimiento.length > 0 ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Preguntas de seguimiento</Text>
          {consulta.preguntas_seguimiento.map((pregunta) => (
            <Text key={pregunta} style={styles.item}>
              - {pregunta}
            </Text>
          ))}
        </View>
      ) : null}

      {consulta.completado && consulta.evaluacion_final ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Evaluacion final</Text>
          <Text style={styles.body}>{consulta.evaluacion_final}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 14
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    justifyContent: 'space-between'
  },
  title: {
    color: colors.text.primary,
    flex: 1,
    fontSize: 18,
    fontWeight: '700'
  },
  meta: {
    color: colors.text.secondary,
    fontSize: 13
  },
  body: {
    color: colors.text.primary,
    fontSize: 15,
    lineHeight: 21
  },
  section: {
    gap: 6
  },
  sectionTitle: {
    color: colors.text.primary,
    fontWeight: '700'
  },
  item: {
    color: colors.text.secondary,
    lineHeight: 20
  }
});
