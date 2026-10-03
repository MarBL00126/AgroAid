import { StyleSheet, Text, View } from 'react-native';
import { colors } from '@/constants/colors';
export default function MapaTab() {
  return (
    <View style={styles.screen}>
      <Text style={styles.title}>Mapa colaborativo</Text>
      <Text style={styles.text}>
      </Text>
       </View>
  );
}
const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    flex: 1,
    padding: 20
  },
  title: {
    color: colors.text.primary,
    fontSize: 24,
    fontWeight: '700',
    marginBottom: 8
  },
  text: {
    color: colors.text.secondary,
    fontSize: 16,
    lineHeight: 22
  }
});
