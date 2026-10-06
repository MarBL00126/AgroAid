import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';

import { RiesgoChip } from '@/components/RiesgoChip';
import { colors } from '@/constants/colors';
import { useLocation } from '@/hooks/useLocation';
import {
  getEventos,
  reportarEvento,
  type EventoMapa,
  type EventoTipo
} from '@/services/mapa';

const DEFAULT_COORDS = { lat: -32.041, lon: -63.569 };
const EVENT_TYPES: EventoTipo[] = [
  'plaga',
  'enfermedad',
  'contaminacion',
  'incendio'
];

export default function MapaTab() {
  const [eventos, setEventos] = useState<EventoMapa[]>([]);
  const [tipo, setTipo] = useState<EventoTipo>('plaga');
  const [descripcion, setDescripcion] = useState('');
  const [radio, setRadio] = useState('5');
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { coords, error: locationError, isLoading: isLocating, requestLocation } =
    useLocation();

  const center = coords ?? DEFAULT_COORDS;

  const load = useCallback(async () => {
    setIsLoading(true);
    setMessage(null);

    try {
      setEventos(
        await getEventos({
          lat: center.lat,
          lon: center.lon,
          radio_km: 100
        })
      );
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : 'No se pudieron cargar eventos.'
      );
    } finally {
      setIsLoading(false);
    }
  }, [center.lat, center.lon]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUseLocation() {
    const next = await requestLocation();
    if (next) {
      setMessage('Ubicacion actualizada.');
    }
  }

  async function handleSubmit() {
    if (!descripcion.trim()) {
      setMessage('Agrega una descripcion del evento.');
      return;
    }

    setIsSubmitting(true);
    setMessage(null);

    try {
      await reportarEvento({
        lat: center.lat,
        lon: center.lon,
        tipo,
        radio_km: Number(radio) || 5,
        descripcion: descripcion.trim()
      });
      setDescripcion('');
      setRadio('5');
      setMessage('Evento reportado.');
      await load();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : 'No se pudo reportar el evento.'
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <FlatList
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.title}>Mapa colaborativo</Text>
          <Text style={styles.subtitle}>
            Reportes cercanos a {center.lat.toFixed(4)}, {center.lon.toFixed(4)}
          </Text>

          <Pressable
            disabled={isLocating}
            onPress={handleUseLocation}
            style={[styles.secondaryButton, isLocating && styles.disabled]}
          >
            <Text style={styles.secondaryButtonText}>
              {coords ? 'Actualizar ubicacion' : 'Usar mi ubicacion'}
            </Text>
          </Pressable>

          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Reportar evento</Text>
            <View style={styles.typeRow}>
              {EVENT_TYPES.map((item) => (
                <Pressable
                  key={item}
                  onPress={() => setTipo(item)}
                  style={[styles.typeButton, item === tipo && styles.typeActive]}
                >
                  <Text
                    style={[
                      styles.typeText,
                      item === tipo && styles.typeTextActive
                    ]}
                  >
                    {item}
                  </Text>
                </Pressable>
              ))}
            </View>
            <TextInput
              multiline
              onChangeText={setDescripcion}
              placeholder="Descripcion, cultivo afectado, zona o evidencia..."
              placeholderTextColor={colors.text.secondary}
              style={styles.textArea}
              value={descripcion}
            />
            <TextInput
              keyboardType="numeric"
              onChangeText={setRadio}
              placeholder="Radio estimado km"
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={radio}
            />
            <Pressable
              disabled={isSubmitting}
              onPress={handleSubmit}
              style={[styles.button, isSubmitting && styles.disabled]}
            >
              {isSubmitting ? (
                <ActivityIndicator color={colors.text.inverse} />
              ) : (
                <Text style={styles.buttonText}>Enviar reporte</Text>
              )}
            </Pressable>
          </View>

          {locationError ? <Text style={styles.error}>{locationError}</Text> : null}
          {message ? <Text style={styles.message}>{message}</Text> : null}
          <Text style={styles.sectionTitle}>Eventos cercanos</Text>
        </View>
      }
      contentContainerStyle={styles.screen}
      data={eventos}
      keyExtractor={(item) => String(item.id)}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={load} />}
      renderItem={({ item }) => <EventoCard evento={item} />}
      ListEmptyComponent={
        !isLoading ? (
          <Text style={styles.empty}>No hay eventos en el radio consultado.</Text>
        ) : null
      }
    />
  );
}

function EventoCard({ evento }: { evento: EventoMapa }) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.eventType}>{evento.tipo}</Text>
        <RiesgoChip nivel={evento.nivel_riesgo || 'MEDIO'} />
      </View>
      <Text style={styles.description}>
        {evento.descripcion || 'Sin descripcion.'}
      </Text>
      <Text style={styles.meta}>
        {Number(evento.distancia_km ?? 0).toFixed(1)} km - radio{' '}
        {Number(evento.radio_km).toFixed(0)} km
        {evento.verificado ? ' - verificado' : ''}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    gap: 12,
    padding: 20,
    paddingBottom: 32
  },
  header: {
    gap: 12
  },
  title: {
    color: colors.text.primary,
    fontSize: 24,
    fontWeight: '700'
  },
  subtitle: {
    color: colors.text.secondary,
    lineHeight: 20
  },
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 14
  },
  sectionTitle: {
    color: colors.text.primary,
    fontSize: 17,
    fontWeight: '700'
  },
  typeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8
  },
  typeButton: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8
  },
  typeActive: {
    backgroundColor: colors.brand.primary,
    borderColor: colors.brand.primary
  },
  typeText: {
    color: colors.text.secondary,
    fontWeight: '700'
  },
  typeTextActive: {
    color: colors.text.inverse
  },
  input: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 46,
    paddingHorizontal: 12
  },
  textArea: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 92,
    padding: 12,
    textAlignVertical: 'top'
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 46
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 44
  },
  secondaryButtonText: {
    color: colors.brand.primary,
    fontWeight: '700'
  },
  buttonText: {
    color: colors.text.inverse,
    fontWeight: '700'
  },
  disabled: {
    opacity: 0.55
  },
  message: {
    color: colors.text.secondary
  },
  error: {
    color: colors.risk.critical
  },
  cardHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between'
  },
  eventType: {
    color: colors.text.primary,
    fontSize: 16,
    fontWeight: '700',
    textTransform: 'capitalize'
  },
  description: {
    color: colors.text.secondary,
    lineHeight: 20
  },
  meta: {
    color: colors.text.secondary,
    fontSize: 12
  },
  empty: {
    color: colors.text.secondary,
    textAlign: 'center'
  }
});
