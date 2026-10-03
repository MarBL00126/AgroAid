import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { colors } from '@/constants/colors';

export function LoadingOverlay({ visible }: { visible: boolean }) {
  if (!visible) {
    return null;
  }

  return (
    <View style={styles.overlay}>
      <ActivityIndicator color={colors.text.inverse} size="large" />
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    alignItems: 'center',
    backgroundColor: 'rgba(22, 35, 22, 0.42)',
    bottom: 0,
    justifyContent: 'center',
    left: 0,
    position: 'absolute',
    right: 0,
    top: 0,
    zIndex: 10
  }
});
