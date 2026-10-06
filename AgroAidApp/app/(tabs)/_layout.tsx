import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { colors } from '@/constants/colors';
import { useBranding } from '@/hooks/useBranding';

export default function TabsLayout() {
  const { branding } = useBranding();

  const activeColor =
    branding.primary_color || colors.brand.primary;

  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.surface.card,
        },
        headerTintColor: colors.text.primary,
        tabBarActiveTintColor: activeColor,
        tabBarInactiveTintColor: colors.text.secondary,
        tabBarStyle: {
          backgroundColor: colors.surface.card,
          borderTopColor: colors.surface.border,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Consulta',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="chatbubbles-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="mapa"
        options={{
          title: 'Mapa',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="map-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="historial"
        options={{
          title: 'Historial',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="time-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="prevuelo"
        options={{
          title: 'Pre-vuelo',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="airplane-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="recetas"
        options={{
          title: 'Recetas',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="document-text-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />

      <Tabs.Screen
        name="perfil"
        options={{
          title: 'Perfil',
          tabBarIcon: ({ color, size }) => (
            <Ionicons
              name="person-outline"
              color={color}
              size={size}
            />
          ),
        }}
      />
    </Tabs>
  );
}
