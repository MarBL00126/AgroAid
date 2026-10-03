import { useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { RecetaCard } from '@/components/RecetaCard';
import { colors } from '@/constants/colors';
import { getRecetas, type Receta } from '@/services/recetas';

export default function RecetasTab() {
  const [recetas, setRecetas] = useState<Receta[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  async function load() {
    setIsLoading(true);

    try {
      setRecetas(await getRecetas());
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <View style={styles.screen}>
      <Text style={styles.title}>Recetas agronomicas</Text>
      <FlatList
        contentContainerStyle={styles.list}
        data={recetas}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={isLoading} onRefresh={load} />}
        renderItem={({ item }) => <RecetaCard receta={item} />}
        ListEmptyComponent={
          !isLoading ? (
            <Text style={styles.empty}>Todavia no hay recetas disponibles.</Text>
          ) : null
        }
      />
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
    marginBottom: 14
  },
  list: {
    gap: 12,
    paddingBottom: 24
  },
  empty: {
    color: colors.text.secondary,
    marginTop: 24,
    textAlign: 'center'
  }
});
