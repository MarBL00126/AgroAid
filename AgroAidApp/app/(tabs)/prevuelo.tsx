import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';

import { colors } from '@/constants/colors';
import { useLocation } from '@/hooks/useLocation';
import { downloadAndSharePdf } from '@/services/files';
import {
  evaluarPreAplicacion,
  preAplicacionPdfUrl,
  type PreAplicacionResponse
} from '@/services/prevuelo';

const EPP_OPTIONS = ['guantes', 'mascara', 'antiparras', 'botas', 'traje'];
const EQUIPOS = ['terrestre', 'drone', 'aereo'];

export default function PrevueloTab() {
  const [producto, setProducto] = useState('');
  const [cultivo, setCultivo] = useState('');
  const [dosis, setDosis] = useState('');
  const [distanciaAgua, setDistanciaAgua] = useState('');
  const [equipo, setEquipo] = useState('terrestre');
  const [epp, setEpp] = useState<string[]>([]);
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<PreAplicacionResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { error: locationError, isLoading: isLocating, requestLocation } =
    useLocation();

  async function handleUseLocation() {
    const coords = await requestLocation();
    if (coords) {
      setLat(coords.lat.toFixed(6));
      setLon(coords.lon.toFixed(6));
      setMessage('Ubicacion agregada.');
    }
  }

  function toggleEpp(item: string) {
    setEpp((current) =>
      current.includes(item)
        ? current.filter((value) => value !== item)
        : [...current, item]
    );
  }

  async function handleSubmit() {
    if (!producto.trim() || !lat.trim() || !lon.trim() || !distanciaAgua.trim()) {
      setMessage('Producto, ubicacion y distancia al agua son obligatorios.');
      return;
    }

    setIsSubmitting(true);
    setMessage('Consultando clima y evaluando...');

    try {
      const response = await evaluarPreAplicacion({
        lat: Number(lat),
        lon: Number(lon),
        producto: producto.trim(),
        cultivo: cultivo.trim() || null,
        dosis_l_ha: dosis.trim() ? Number(dosis) : null,
        distancia_agua_m: Number(distanciaAgua),
        tipo_equipo: equipo,
        epp_disponible: epp
      });
      setResult(response);
      setMessage(null);
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : 'No se pudo evaluar la aplicacion.'
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openPdf() {
    if (result?.registro) {
      try {
        await downloadAndSharePdf(
          preAplicacionPdfUrl(result.registro),
          `pre_aplicacion_${result.registro.id}.pdf`
        );
      } catch (err) {
        setMessage(err instanceof Error ? err.message : 'No se pudo abrir el PDF.');
      }
    }
  }

  const isGo = result?.evaluacion.resultado_global === 'GO';

  return (
    <ScrollView contentContainerStyle={styles.screen}>
      <Text style={styles.title}>Chequeo pre-aplicacion</Text>

      <View style={styles.card}>
        <TextInput
          onChangeText={setProducto}
          placeholder="Producto"
          placeholderTextColor={colors.text.secondary}
          style={styles.input}
          value={producto}
        />
        <View style={styles.row}>
          <TextInput
            onChangeText={setCultivo}
            placeholder="Cultivo"
            placeholderTextColor={colors.text.secondary}
            style={[styles.input, styles.rowInput]}
            value={cultivo}
          />
          <TextInput
            keyboardType="numeric"
            onChangeText={setDosis}
            placeholder="Dosis L/ha"
            placeholderTextColor={colors.text.secondary}
            style={[styles.input, styles.rowInput]}
            value={dosis}
          />
        </View>
        <TextInput
          keyboardType="numeric"
          onChangeText={setDistanciaAgua}
          placeholder="Distancia al agua en metros"
          placeholderTextColor={colors.text.secondary}
          style={styles.input}
          value={distanciaAgua}
        />

        <Text style={styles.label}>Equipo</Text>
        <View style={styles.optionRow}>
          {EQUIPOS.map((item) => (
            <Pressable
              key={item}
              onPress={() => setEquipo(item)}
              style={[styles.option, equipo === item && styles.optionActive]}
            >
              <Text
                style={[
                  styles.optionText,
                  equipo === item && styles.optionTextActive
                ]}
              >
                {item}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.label}>EPP disponible</Text>
        <View style={styles.optionRow}>
          {EPP_OPTIONS.map((item) => {
            const active = epp.includes(item);
            return (
              <Pressable
                key={item}
                onPress={() => toggleEpp(item)}
                style={[styles.option, active && styles.optionActive]}
              >
                <Text
                  style={[styles.optionText, active && styles.optionTextActive]}
                >
                  {item}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.row}>
          <TextInput
            keyboardType="numeric"
            onChangeText={setLat}
            placeholder="Latitud"
            placeholderTextColor={colors.text.secondary}
            style={[styles.input, styles.rowInput]}
            value={lat}
          />
          <TextInput
            keyboardType="numeric"
            onChangeText={setLon}
            placeholder="Longitud"
            placeholderTextColor={colors.text.secondary}
            style={[styles.input, styles.rowInput]}
            value={lon}
          />
        </View>
        <Pressable
          disabled={isLocating}
          onPress={handleUseLocation}
          style={[styles.secondaryButton, isLocating && styles.disabled]}
        >
          <Text style={styles.secondaryButtonText}>Usar mi ubicacion</Text>
        </Pressable>

        <Pressable
          disabled={isSubmitting}
          onPress={handleSubmit}
          style={[styles.button, isSubmitting && styles.disabled]}
        >
          {isSubmitting ? (
            <ActivityIndicator color={colors.text.inverse} />
          ) : (
            <Text style={styles.buttonText}>Evaluar GO / NO-GO</Text>
          )}
        </Pressable>
      </View>

      {locationError ? <Text style={styles.error}>{locationError}</Text> : null}
      {message ? <Text style={styles.message}>{message}</Text> : null}

      {result ? (
        <View style={styles.card}>
          <View
            style={[
              styles.resultBanner,
              { backgroundColor: isGo ? colors.risk.low : colors.risk.critical }
            ]}
          >
            <Text style={styles.resultTitle}>
              {result.evaluacion.resultado_global}
            </Text>
            <Text style={styles.resultText}>{result.evaluacion.recomendacion}</Text>
          </View>

          {result.evaluacion.checks.map((check) => (
            <View key={`${check.check}-${check.resultado}`} style={styles.check}>
              <Text style={styles.checkTag}>{check.resultado}</Text>
              <View style={styles.checkBody}>
                <Text style={styles.checkTitle}>{check.check}</Text>
                <Text style={styles.checkText}>{check.detalle}</Text>
              </View>
            </View>
          ))}

          <Text style={styles.message}>{formatClima(result.evaluacion.clima)}</Text>
          <Pressable onPress={openPdf} style={styles.secondaryButton}>
            <Text style={styles.secondaryButtonText}>Abrir PDF</Text>
          </Pressable>
        </View>
      ) : null}
    </ScrollView>
  );
}

function formatClima(clima: Record<string, unknown>) {
  const temperature = clima.temperature ?? '-';
  const wind = clima.wind ?? '-';
  const rain = clima.rain ?? '-';
  return `Clima: ${temperature} C, viento ${wind} km/h, lluvia ${rain} mm`;
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    gap: 12,
    padding: 20,
    paddingBottom: 32
  },
  title: {
    color: colors.text.primary,
    fontSize: 24,
    fontWeight: '700'
  },
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 14
  },
  row: {
    flexDirection: 'row',
    gap: 10
  },
  rowInput: {
    flex: 1
  },
  input: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 46,
    paddingHorizontal: 12
  },
  label: {
    color: colors.text.primary,
    fontWeight: '700'
  },
  optionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8
  },
  option: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 8
  },
  optionActive: {
    backgroundColor: colors.brand.primary,
    borderColor: colors.brand.primary
  },
  optionText: {
    color: colors.text.secondary,
    fontWeight: '700'
  },
  optionTextActive: {
    color: colors.text.inverse
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48
  },
  buttonText: {
    color: colors.text.inverse,
    fontWeight: '700'
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
  disabled: {
    opacity: 0.55
  },
  error: {
    color: colors.risk.critical
  },
  message: {
    color: colors.text.secondary
  },
  resultBanner: {
    borderRadius: 8,
    gap: 4,
    padding: 14
  },
  resultTitle: {
    color: colors.text.inverse,
    fontSize: 28,
    fontWeight: '800'
  },
  resultText: {
    color: colors.text.inverse,
    fontWeight: '700'
  },
  check: {
    borderTopColor: colors.surface.border,
    borderTopWidth: 1,
    flexDirection: 'row',
    gap: 10,
    paddingTop: 10
  },
  checkTag: {
    color: colors.brand.primary,
    fontSize: 12,
    fontWeight: '800',
    width: 86
  },
  checkBody: {
    flex: 1,
    gap: 2
  },
  checkTitle: {
    color: colors.text.primary,
    fontWeight: '700'
  },
  checkText: {
    color: colors.text.secondary,
    lineHeight: 20
  }
});
