import { router } from 'expo-router';
import { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { colors } from '@/constants/colors';
import { useAuth } from '@/hooks/useAuth';

export default function IndexScreen() {
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) {
      return;
    }

    router.replace(isAuthenticated ? ('/(tabs)' as never) : '/login');
  }, [isAuthenticated, isLoading]);

  return (
    <View style={styles.container}>
      <ActivityIndicator color={colors.brand.primary} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    backgroundColor: colors.surface.background,
    flex: 1,
    justifyContent: 'center'
  }
});
