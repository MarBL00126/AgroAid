import { useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';

import { CameraButton } from '@/components/CameraButton';
import { ConsultaCard } from '@/components/ConsultaCard';
import { LoadingOverlay } from '@/components/LoadingOverlay';
import { MicButton } from '@/components/MicButton';
import { RespuestaInput } from '@/components/RespuestaInput';
import { colors } from '@/constants/colors';
import { useConsulta } from '@/hooks/useConsulta';
import { useLocation } from '@/hooks/useLocation';
import type { ImagenConsultaResult } from '@/services/imagen';
import type { ConsultaResponse } from '@/services/consultas';

export default function ConsultaTab() {
  const [texto, setTexto] = useState('');
  const [respuesta, setRespuesta] = useState('');
  const [mediaError, setMediaError] = useState<string | null>(null);
  const { consulta, error, isLoading, iniciar, responder, reset,cargar } =
    useConsulta();
  const {
    coords,
    error: locationError,
    isLoading: isLocating,
    requestLocation
  } = useLocation();

  async function handleIniciar() {
    if (!texto.trim()) {
      return;
    }

    await iniciar({
      consulta_inicial: texto.trim(),
      lat: coords?.lat,
      lon: coords?.lon
    });
  }

  async function handleResponder() {
    if (!respuesta.trim()) {
      return;
    }

    await responder(respuesta.trim());
    setRespuesta('');
  }
  async function handleVozResult(result: ConsultaResponse) {
    setMediaError(null);
    await cargar(result.consulta_id);
  }
  async function handleImagenResult(result: ImagenConsultaResult) {
    setMediaError(null);
    setTexto(result.consulta_generada);
    await cargar(result.evaluacion.consulta_id);
  }
  function handleMediaError(message: string) {
    setMediaError(message);
  }

  return (
    <View style={styles.container}>
      <LoadingOverlay visible={isLoading || isLocating} />
      <ScrollView contentContainerStyle={styles.screen}>
        <Text style={styles.title}>Consulta agronomica</Text>

        {!consulta ? (
          <View style={styles.startPanel}>
            <TextInput
              multiline
              onChangeText={setTexto}
              placeholder="Describi el problema, cultivo, producto o riesgo..."
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={texto}
            />
            <View style={styles.mediaRow}>
              <MicButton
                disabled={isLoading}
                onError={handleMediaError}
                onResult={handleVozResult}
              />
              <CameraButton
                disabled={isLoading}
                onError={handleMediaError}
                onResult={handleImagenResult}
              />
            </View>
            <Pressable onPress={requestLocation} style={styles.secondaryButton}>
              <Text style={styles.secondaryButtonText}>
                {coords ? 'Ubicacion agregada' : 'Agregar ubicacion'}
              </Text>
            </Pressable>

            <Pressable
              disabled={isLoading || !texto.trim()}
              onPress={handleIniciar}
              style={[
                styles.button,
                (isLoading || !texto.trim()) && styles.disabled
              ]}
            >
              <Text style={styles.buttonText}>Iniciar consulta</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.flow}>
            <ConsultaCard consulta={consulta} />

            {!consulta.completado ? (
              <RespuestaInput
                disabled={isLoading}
                onChangeText={setRespuesta}
                onSubmit={handleResponder}
                value={respuesta}
              />
            ) : null}

            <Pressable onPress={reset} style={styles.secondaryButton}>
              <Text style={styles.secondaryButtonText}>Nueva consulta</Text>
            </Pressable>
          </View>
        )}

        {locationError ? <Text style={styles.warning}>{locationError}</Text> : null}
        {mediaError ? <Text style={styles.error}>{mediaError}</Text> : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1
  },
  screen: {
    backgroundColor: colors.surface.background,
    flexGrow: 1,
    gap: 14,
    padding: 20
  },
  title: {
    color: colors.text.primary,
    fontSize: 26,
    fontWeight: '700'
  },
  startPanel: {
    gap: 12
  },
  flow: {
    gap: 14
  },
  input: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 150,
    padding: 14,
    textAlignVertical: 'top'
  },
  mediaRow: {
    flexDirection: 'row',
    gap: 10
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48
  },
  disabled: {
    opacity: 0.55
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
  warning: {
    color: colors.risk.medium
  },
  error: {
    color: colors.risk.critical
  }
});
