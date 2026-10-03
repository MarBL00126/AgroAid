import { Audio } from 'expo-av';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { colors } from '@/constants/colors';
import type { ConsultaResponse } from '@/services/consultas';
import { vozConsulta } from '@/services/voz';
type Props = {
    disabled?: boolean;
  onResult: (consulta: ConsultaResponse) => void;
  onError?: (message: string) => void;
};
export function MicButton({ disabled, onResult, onError }: Props) {
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  async function startRecording() {
    const permission = await Audio.requestPermissionsAsync();
    if (!permission.granted) {
      onError?.('Permiso de microfono denegado.');
      return;
    }
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true
    });
    const { recording: nextRecording } = await Audio.Recording.createAsync(
      Audio.RecordingOptionsPresets.HIGH_QUALITY
    );
    setRecording(nextRecording);
  }
  async function stopRecording() {
    if (!recording) {
      return;
    }
    setIsSubmitting(true);
    try {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (!uri) {
        onError?.('No se pudo leer el audio grabado.');
        return;
      }
      const consulta = await vozConsulta(uri, 'audio/m4a');
      onResult(consulta);
    } catch (err) {
      onError?.(
        err instanceof Error ? err.message : 'No se pudo procesar el audio.'
      );
    } finally {
      setIsSubmitting(false);
    }
}
async function handlePress() {
    if (recording) {
      await stopRecording();
      return;
    }
    await startRecording();
  }
  const isDisabled = disabled || isSubmitting;
  return (
    <Pressable
      disabled={isDisabled}
      onPress={handlePress}
      style={[
        styles.button,
        recording && styles.recording,
        isDisabled && styles.disabled
      ]}
    >
      {isSubmitting ? (
        <ActivityIndicator color={colors.text.inverse} />
      ) : (
        <Text style={styles.text}>{recording ? 'Detener voz' : 'Voz'}</Text>
      )}
    </Pressable>
  );
}
const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.secondary,
    borderRadius: 8,
    flex: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: 12
  },
  recording: {
    backgroundColor: colors.risk.critical
  },
  disabled: {
    opacity: 0.55
  },
  text: {
    color: colors.text.inverse,
    fontWeight: '700'
  }
});