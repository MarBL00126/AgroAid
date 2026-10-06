import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import { colors } from '@/constants/colors';
import { analizarEtiqueta, type ImagenConsultaResult } from '@/services/imagen';
type Props = {
  disabled?: boolean;
  onResult: (result: ImagenConsultaResult) => void;
  onError?: (message: string) => void;
};
export function CameraButton({ disabled, onResult, onError }: Props) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  async function handlePress() {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      onError?.('Permiso de camara denegado.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85
    });
    if (result.canceled) {
      return;
    }
    const asset = result.assets[0];
    if (!asset?.uri) {
      onError?.('No se pudo leer la imagen.');
      return;
    }
    setIsSubmitting(true);
    try {
      const analysis = await analizarEtiqueta(
        asset.uri,
        asset.mimeType ?? 'image/jpeg'
      );
      onResult(analysis);
    } catch (err) {
      onError?.(
        err instanceof Error ? err.message : 'No se pudo analizar la imagen.'
      );
    } finally {
      setIsSubmitting(false);
    }
}
const isDisabled = disabled || isSubmitting;
  return (
    <Pressable
      disabled={isDisabled}
      onPress={handlePress}
      style={[styles.button, isDisabled && styles.disabled]}
    >
      {isSubmitting ? (
        <ActivityIndicator color={colors.text.inverse} />
      ) : (
        <Text style={styles.text}>Camara</Text>
      )}
    </Pressable>
  );
}
const styles = StyleSheet.create({
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.accent,
    borderRadius: 8,
    flex: 1,
    justifyContent: 'center',
    minHeight: 44,
    paddingHorizontal: 12
  },
  disabled: {
    opacity: 0.55
  },
  text: {
    color: colors.text.inverse,
    fontWeight: '700'
  }
});
