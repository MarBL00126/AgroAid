import { router } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors } from '@/constants/colors';
import { useAuth } from '@/hooks/useAuth';
import { useBranding } from '@/hooks/useBranding';
import { TextInput } from 'react-native-gesture-handler';

export default function PerfilTab() {
  const { isAuthenticated, logout } = useAuth();
   const {
    branding,
    tenantSlug,
    isLoading,
    setTenantSlug,
    reloadBranding
  } = useBranding();

  async function handleLogout() {
    await logout();
    router.replace('/login');
  }

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>Perfil</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Aplicacion</Text>
        <Text style={styles.value}>{branding.app_name}</Text>
        <Text style={styles.footer}>{branding.footer_text}</Text>
      </View>
      <View style={styles.card}>
        <Text style={styles.label}>Tenant</Text>
        <TextInput
          autoCapitalize="none"
          onChangeText={setTenantSlug}
          placeholder="default"
          placeholderTextColor={colors.text.secondary}
          style={styles.input}
          value={tenantSlug}
        />
        <Pressable
          disabled={isLoading}
          onPress={() => reloadBranding(tenantSlug)}
            style={[styles.secondaryButton, isLoading && styles.disabled]}
        >
          <Text style={styles.secondaryButtonText}>Actualizar branding</Text>
        </Pressable>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Sesion</Text>
        <Text style={styles.value}>
          {isAuthenticated ? 'Sesion activa' : 'Sin sesion'}
        </Text>
      </View>

      <Pressable onPress={() => reloadBranding()} style={styles.secondaryButton}>
        <Text style={styles.secondaryButtonText}>Actualizar branding</Text>
      </Pressable>

      <Pressable onPress={handleLogout} style={styles.button}>
        <Text style={styles.buttonText}>Cerrar sesion</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    flex: 1,
    gap: 14,
    padding: 20
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
    gap: 6,
    padding: 14
  },
  label: {
    color: colors.text.secondary,
    fontSize: 13,
    fontWeight: '700',
    textTransform: 'uppercase'
  },
  value: {
    color: colors.text.primary,
    fontSize: 17,
    fontWeight: '700'
  },
  footer: {
    color: colors.text.secondary,
    lineHeight: 20
  },
  input: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 44,
    paddingHorizontal: 12
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 46
  },
  secondaryButtonText: {
    color: colors.brand.primary,
    fontWeight: '700'
  },
  disabled: {
    opacity: 0.55
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.risk.critical,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48
  },
  buttonText: {
    color: colors.text.inverse,
    fontSize: 16,
    fontWeight: '700'
  }
});
