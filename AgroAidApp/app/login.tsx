import { Link, router } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';

import { colors } from '@/constants/colors';
import { ApiError } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    setError(null);
    setIsSubmitting(true);

    try {
      await login({ email: email.trim(), password });
      router.replace('/(tabs)' as never);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'No pudimos iniciar sesion. Revisa tus datos.'
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  const disabled = isSubmitting || !email.trim() || !password;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={styles.screen}
    >
      <View style={styles.card}>
        <Text style={styles.title}>AgroAid</Text>
        <Text style={styles.subtitle}>Ingreso de productores</Text>

        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          onChangeText={setEmail}
          placeholder="Email"
          placeholderTextColor={colors.text.secondary}
          style={styles.input}
          value={email}
        />

        <TextInput
          autoCapitalize="none"
          onChangeText={setPassword}
          placeholder="Password"
          placeholderTextColor={colors.text.secondary}
          secureTextEntry
          style={styles.input}
          value={password}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          disabled={disabled}
          onPress={handleSubmit}
          style={[styles.button, disabled && styles.buttonDisabled]}
        >
          {isSubmitting ? (
            <ActivityIndicator color={colors.text.inverse} />
          ) : (
            <Text style={styles.buttonText}>Entrar</Text>
          )}
        </Pressable>

        <Link href="/register" style={styles.link}>
          Crear cuenta
        </Link>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    flex: 1,
    justifyContent: 'center',
    padding: 24
  },
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 14,
    padding: 20
  },
  title: {
    color: colors.text.primary,
    fontSize: 30,
    fontWeight: '700'
  },
  subtitle: {
    color: colors.text.secondary,
    fontSize: 16,
    marginBottom: 8
  },
  input: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: 14
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    minHeight: 48,
    justifyContent: 'center'
  },
  buttonDisabled: {
    opacity: 0.55
  },
  buttonText: {
    color: colors.text.inverse,
    fontSize: 16,
    fontWeight: '700'
  },
  error: {
    color: colors.risk.critical,
    fontSize: 14
  },
  link: {
    color: colors.brand.primary,
    fontSize: 15,
    fontWeight: '700',
    textAlign: 'center'
  }
});
