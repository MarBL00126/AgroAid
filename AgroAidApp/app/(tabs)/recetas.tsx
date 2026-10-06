import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View
} from 'react-native';

import { RecetaCard } from '@/components/RecetaCard';
import { colors } from '@/constants/colors';
import { downloadAndSharePdf } from '@/services/files';
import {
  cambiarEstadoReceta,
  crearReceta,
  getRecetas,
  recetaPdfUrl,
  type Receta
} from '@/services/recetas';

export default function RecetasTab() {
  const [recetas, setRecetas] = useState<Receta[]>([]);
  const [producto, setProducto] = useState('');
  const [principioActivo, setPrincipioActivo] = useState('');
  const [cultivo, setCultivo] = useState('');
  const [lote, setLote] = useState('');
  const [superficie, setSuperficie] = useState('');
  const [dosis, setDosis] = useState('');
  const [volumenAgua, setVolumenAgua] = useState('');
  const [fechaAplicacion, setFechaAplicacion] = useState('');
  const [observaciones, setObservaciones] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function load() {
    setIsLoading(true);

    try {
      setRecetas(await getRecetas());
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'No se pudieron cargar recetas.');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate() {
    if (!producto.trim() || !cultivo.trim() || !dosis.trim()) {
      setMessage('Producto, cultivo y dosis son obligatorios.');
      return;
    }

    setIsSubmitting(true);
    setMessage('Generando receta y PDF...');

    try {
      const receta = await crearReceta({
        producto: producto.trim(),
        principio_activo: principioActivo.trim() || null,
        cultivo: cultivo.trim(),
        lote: lote.trim() || null,
        superficie_ha: superficie.trim() ? Number(superficie) : null,
        dosis: dosis.trim(),
        volumen_agua: volumenAgua.trim() || null,
        fecha_aplicacion: fechaAplicacion.trim() || null,
        observaciones: observaciones.trim() || null
      });
      setProducto('');
      setPrincipioActivo('');
      setCultivo('');
      setLote('');
      setSuperficie('');
      setDosis('');
      setVolumenAgua('');
      setFechaAplicacion('');
      setObservaciones('');
      setMessage(`Receta ${receta.numero_receta} creada.`);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'No se pudo crear la receta.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function openPdf(receta: Receta) {
    await downloadAndSharePdf(
      recetaPdfUrl(receta),
      `${receta.numero_receta || `receta_${receta.id}`}.pdf`
    );
  }

  async function changeState(receta: Receta, estado: 'emitir' | 'anular') {
    try {
      await cambiarEstadoReceta(receta.id, estado);
      await load();
    } catch (err) {
      Alert.alert(
        'No se pudo actualizar',
        err instanceof Error ? err.message : 'Revisa tus permisos.'
      );
    }
  }

  return (
    <FlatList
      ListHeaderComponent={
        <View style={styles.header}>
          <Text style={styles.title}>Recetas agronomicas</Text>
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Nueva receta</Text>
            <TextInput
              onChangeText={setProducto}
              placeholder="Producto"
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={producto}
            />
            <TextInput
              onChangeText={setPrincipioActivo}
              placeholder="Principio activo"
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={principioActivo}
            />
            <View style={styles.row}>
              <TextInput
                onChangeText={setCultivo}
                placeholder="Cultivo"
                placeholderTextColor={colors.text.secondary}
                style={[styles.input, styles.rowInput]}
                value={cultivo}
              />
              <TextInput
                onChangeText={setLote}
                placeholder="Lote"
                placeholderTextColor={colors.text.secondary}
                style={[styles.input, styles.rowInput]}
                value={lote}
              />
            </View>
            <View style={styles.row}>
              <TextInput
                keyboardType="numeric"
                onChangeText={setSuperficie}
                placeholder="Superficie ha"
                placeholderTextColor={colors.text.secondary}
                style={[styles.input, styles.rowInput]}
                value={superficie}
              />
              <TextInput
                onChangeText={setDosis}
                placeholder="Dosis"
                placeholderTextColor={colors.text.secondary}
                style={[styles.input, styles.rowInput]}
                value={dosis}
              />
            </View>
            <TextInput
              onChangeText={setVolumenAgua}
              placeholder="Volumen de agua"
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={volumenAgua}
            />
            <TextInput
              onChangeText={setFechaAplicacion}
              placeholder="Fecha aplicacion YYYY-MM-DD"
              placeholderTextColor={colors.text.secondary}
              style={styles.input}
              value={fechaAplicacion}
            />
            <TextInput
              multiline
              onChangeText={setObservaciones}
              placeholder="Observaciones"
              placeholderTextColor={colors.text.secondary}
              style={styles.textArea}
              value={observaciones}
            />
            <Pressable
              disabled={isSubmitting}
              onPress={handleCreate}
              style={[styles.button, isSubmitting && styles.disabled]}
            >
              {isSubmitting ? (
                <ActivityIndicator color={colors.text.inverse} />
              ) : (
                <Text style={styles.buttonText}>Generar receta y PDF</Text>
              )}
            </Pressable>
          </View>

          {message ? <Text style={styles.message}>{message}</Text> : null}
          <Text style={styles.sectionTitle}>Mis recetas</Text>
        </View>
      }
      contentContainerStyle={styles.screen}
      data={recetas}
      keyExtractor={(item) => String(item.id)}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={load} />}
      renderItem={({ item }) => (
        <View style={styles.itemWrap}>
          <RecetaCard receta={item} onDownload={openPdf} />
          <View style={styles.actions}>
            {item.estado === 'borrador' ? (
              <Pressable
                onPress={() => changeState(item, 'emitir')}
                style={styles.secondaryButton}
              >
                <Text style={styles.secondaryButtonText}>Emitir</Text>
              </Pressable>
            ) : null}
            {item.estado !== 'anulada' ? (
              <Pressable
                onPress={() => changeState(item, 'anular')}
                style={styles.dangerButton}
              >
                <Text style={styles.dangerText}>Anular</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      )}
      ListEmptyComponent={
        !isLoading ? (
          <Text style={styles.empty}>Todavia no hay recetas disponibles.</Text>
        ) : null
      }
    />
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: colors.surface.background,
    gap: 12,
    padding: 20,
    paddingBottom: 32
  },
  header: {
    gap: 12
  },
  title: {
    color: colors.text.primary,
    fontSize: 24,
    fontWeight: '700'
  },
  sectionTitle: {
    color: colors.text.primary,
    fontSize: 17,
    fontWeight: '700'
  },
  card: {
    backgroundColor: colors.surface.card,
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 10,
    padding: 14
  },
  row: {
    flexDirection: 'row',
    gap: 10
  },
  rowInput: {
    flex: 1
  },
  input: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 46,
    paddingHorizontal: 12
  },
  textArea: {
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text.primary,
    minHeight: 80,
    padding: 12,
    textAlignVertical: 'top'
  },
  button: {
    alignItems: 'center',
    backgroundColor: colors.brand.primary,
    borderRadius: 8,
    justifyContent: 'center',
    minHeight: 48
  },
  buttonText: {
    color: colors.text.inverse,
    fontWeight: '700'
  },
  disabled: {
    opacity: 0.55
  },
  itemWrap: {
    gap: 8
  },
  actions: {
    flexDirection: 'row',
    gap: 8
  },
  secondaryButton: {
    alignItems: 'center',
    borderColor: colors.surface.border,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    justifyContent: 'center',
    minHeight: 42
  },
  secondaryButtonText: {
    color: colors.brand.primary,
    fontWeight: '700'
  },
  dangerButton: {
    alignItems: 'center',
    backgroundColor: '#FEE2E2',
    borderRadius: 8,
    flex: 1,
    justifyContent: 'center',
    minHeight: 42
  },
  dangerText: {
    color: colors.risk.critical,
    fontWeight: '700'
  },
  message: {
    color: colors.text.secondary
  },
  empty: {
    color: colors.text.secondary,
    textAlign: 'center'
  }
});
