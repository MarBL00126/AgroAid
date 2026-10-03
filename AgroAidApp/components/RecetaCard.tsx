import { Pressable, StyleSheet, Text, View } from 'react-native';

import { RiesgoChip } from '@/components/RiesgoChip';
import { colors } from '@/constants/colors';
import type { Receta } from '@/services/recetas';

type Props = {
  receta: Receta;
  onDownload?: (receta: Receta) => void;
};

export function RecetaCard({ receta, onDownload }: Props) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>{receta.titulo}</Text>
        <RiesgoChip nivel={receta.riesgo} />
      </View>

      <Text style={styles.crop}>{receta.cultivo}</Text>
      <Text style={styles.description}>{receta.descripcion}</Text>

      <Pressable
        disabled={!onDownload}
        onPress={() => onDownload?.(receta)}
        style={[styles.button, !onDownload && styles.buttonDisabled]}
      >
        <Text style={styles.buttonText}>Descargar PDF</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 9,
    padding: 14
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between'
  },
  title: {
    color: colors.text.primary,
    flex: 1,
    fontSize: 17,
    fontWeight: '700'
  },
  crop: {
    color: colors.brand.primary,
    fontWeight: '700'
  },
  description: {
    color: colors.text.secondary,
    lineHeight: 20
  },
  button: {
    alignItems: 'center',
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 42
  },
  buttonDisabled: {
    opacity: 0.55
  },
  buttonText: {
    color: colors.brand.primary,
    fontWeight: '700'
  }
});
