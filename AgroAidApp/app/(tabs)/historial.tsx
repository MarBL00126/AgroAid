import { useEffect, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View
} from 'react-native';
import { RiesgoChip } from '@/components/RiesgoChip';
import { colors } from '@/constants/colors';
import {
  getHistorial,
  type HistorialItem,
  type HistorialResponse
} from '@/services/historial';
export default function HistorialTab() {
  const [data, setData] = useState<HistorialResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function load(page = 1) {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getHistorial({ page, per_page: 20 });
      setData(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No se pudo cargar el historial.'
      );
    } finally {
      setIsLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  function renderItem({ item }: { item: HistorialItem }) {
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
             <Text style={styles.cardTitle}>Consulta #{item.consulta_id}</Text>
          <RiesgoChip nivel={item.nivel_riesgo} />
        </View>
        <Text style={styles.date}>{new Date(item.fecha_consulta).toLocaleString()}</Text>
        <Text style={styles.query}>{item.consulta_inicial}</Text>
        <Text style={styles.meta}>
          Confianza {item.confianza_final}% - Iteraciones {item.iteraciones}
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>Historial</Text>
        <Pressable onPress={() => load()} style={styles.reloadButton}>
          <Text style={styles.reloadText}>Actualizar</Text>
        </Pressable>
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <FlatList
        contentContainerStyle={styles.list}
        data={data?.items ?? []}
        keyExtractor={(item) => String(item.consulta_id)}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={() => load()} />
        }
        renderItem={renderItem}
        ListEmptyComponent={
          !isLoading ? (
            <Text style={styles.empty}>Todavia no hay consultas para mostrar.</Text>
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
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 14
  },
  title: {
    color: colors.text.primary,
    fontSize: 24,
       fontWeight: '700'
  },
  reloadButton: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8
  },
  reloadText: {
    color: colors.brand.primary,
    fontWeight: '700'
  },
  list: {
    gap: 12,
    paddingBottom: 24
  },
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 8,
    padding: 14
  },
  cardHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 10
  },
  cardTitle: {
    color: colors.text.primary,
    flex: 1,
    fontSize: 17,
    fontWeight: '700'
  },
  date: {
    color: colors.text.secondary,
    fontSize: 13
  },
  query: {
    color: colors.text.primary,
    lineHeight: 20
  },
  meta: {
    color: colors.text.secondary,
    fontSize: 13
  },
  error: {
    color: colors.risk.critical,
    marginBottom: 10
  },
  empty: {
    color: colors.text.secondary,
    marginTop: 24,
        textAlign: 'center'
  }
});