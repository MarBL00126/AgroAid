import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { Linking, Platform } from 'react-native';

import { getAuthHeaders } from '@/services/api';

export async function downloadAndSharePdf(url: string, filename: string) {
  if (Platform.OS === 'web') {
    await Linking.openURL(url);
    return;
  }

  const baseDir = FileSystem.cacheDirectory ?? FileSystem.documentDirectory;

  if (!baseDir) {
    throw new Error('No hay almacenamiento disponible para guardar el PDF.');
  }

  const safeFilename = filename.replace(/[^a-zA-Z0-9_.-]+/g, '_');
  const target = `${baseDir}${safeFilename}`;
  const result = await FileSystem.downloadAsync(url, target, {
    headers: getAuthHeaders()
  });

  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(result.uri, {
      mimeType: 'application/pdf',
      UTI: 'com.adobe.pdf'
    });
    return;
  }

  await Linking.openURL(result.uri);
}
