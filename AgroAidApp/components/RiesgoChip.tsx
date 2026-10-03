import { StyleSheet, Text, View } from 'react-native';

import { colors } from '@/constants/colors';

const riskColors: Record<string, string> = {
  BAJO: colors.risk.low,
  LOW: colors.risk.low,
  MEDIO: colors.risk.medium,
  MEDIUM: colors.risk.medium,
  ALTO: colors.risk.high,
  HIGH: colors.risk.high,
  CRITICO: colors.risk.critical,
  CRITICAL: colors.risk.critical
};

export function RiesgoChip({ nivel }: { nivel: string }) {
  const normalized = nivel.toUpperCase();
  const backgroundColor = riskColors[normalized] ?? colors.text.secondary;

  return (
    <View style={[styles.chip, { backgroundColor }]}>
      <Text style={styles.text}>{normalized}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  text: {
    color: colors.text.inverse,
    fontSize: 12,
    fontWeight: '700'
  }
});
