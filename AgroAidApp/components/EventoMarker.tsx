import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, Text, View } from 'react-native';

import { RiesgoChip } from '@/components/RiesgoChip';
import { colors } from '@/constants/colors';
import type { EventoMapa, EventoTipo } from '@/services/mapa';

const icons: Record<EventoTipo, keyof typeof Ionicons.glyphMap> = {
  enfermedad: 'medkit-outline',
  incendio: 'flame-outline',
  plaga: 'bug-outline',
  contaminacion: 'warning-outline'
};

export function EventoMarker({ evento }: { evento: EventoMapa }) {
  return (
    <View style={styles.card}>
      <View style={styles.iconBox}>
        <Ionicons
          color={colors.brand.primary}
          name={icons[evento.tipo]}
          size={22}
        />
      </View>
      <View style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>{evento.tipo}</Text>
          <RiesgoChip nivel={evento.nivel_riesgo || 'MEDIO'} />
        </View>
        <Text style={styles.description}>
          {evento.descripcion || 'Sin descripcion.'}
        </Text>
        <Text style={styles.meta}>
          {evento.lat.toFixed(3)}, {evento.lon.toFixed(3)}
          {evento.distancia_km != null
            ? ` - ${Number(evento.distancia_km).toFixed(1)} km`
            : ''}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    padding: 12
  },
  iconBox: {
    alignItems: 'center',
    backgroundColor: colors.surface.muted,
    borderRadius: 8,
    height: 42,
    justifyContent: 'center',
    width: 42
  },
  content: {
    flex: 1,
    gap: 6
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between'
  },
  title: {
    color: colors.text.primary,
    flex: 1,
    fontWeight: '700'
  },
  description: {
    color: colors.text.secondary,
    lineHeight: 19
  },
  meta: {
    color: colors.text.secondary,
    fontSize: 12
  }
});
