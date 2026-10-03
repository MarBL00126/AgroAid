import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { colors } from '@/constants/colors';

type Props = {
  value: string;
  onChangeText: (value: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
};

export function RespuestaInput({
  value,
  onChangeText,
  onSubmit,
  disabled
}: Props) {
  const isDisabled = disabled || !value.trim();

  return (
    <View style={styles.wrapper}>
      <TextInput
        multiline
        onChangeText={onChangeText}
        placeholder="Responde con datos concretos: producto, dosis, cultivo, clima, zona..."
        placeholderTextColor={colors.text.secondary}
        style={styles.input}
        value={value}
      />
      <Pressable
        disabled={isDisabled}
        onPress={onSubmit}
        style={[styles.button, isDisabled && styles.buttonDisabled]}
      >
        <Text style={styles.buttonText}>Enviar respuesta</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    gap: 10
  },
  input: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 120,
    padding: 14,
    textAlignVertical: 'top'
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48
  },
  buttonDisabled: {
    opacity: 0.55
  },
  buttonText: {
    color: colors.text.inverse,
    fontWeight: '700'
  }
});
