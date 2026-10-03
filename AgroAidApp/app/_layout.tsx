import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { useColorScheme } from 'react-native';
import { BrandingProvider } from '@/hooks/useBranding';
import { AuthProvider } from '@/hooks/useAuth';
SplashScreen.preventAutoHideAsync();
function AuthGuard({ children }: { children: ReactNode }) {
  return children;
}
export default function RootLayout() {
  const colorScheme = useColorScheme();
  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <AuthProvider>
        <BrandingProvider>
          <AuthGuard>
            <Stack screenOptions={{ headerShown: false }} />
          </AuthGuard>
        </BrandingProvider>
      </AuthProvider>
      <StatusBar style="auto" />
    </ThemeProvider>
  );
}