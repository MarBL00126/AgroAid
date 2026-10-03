import * as Location from 'expo-location';
import { useCallback, useState } from 'react';

export type Coordinates = {
  lat: number;
  lon: number;
};

export function useLocation() {
  const [coords, setCoords] = useState<Coordinates | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requestLocation = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const permission = await Location.requestForegroundPermissionsAsync();

      if (permission.status !== 'granted') {
        setError('Permiso de ubicacion denegado.');
        return null;
      }

      const position = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced
      });

      const nextCoords = {
        lat: position.coords.latitude,
        lon: position.coords.longitude
      };

      setCoords(nextCoords);
      return nextCoords;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'No se pudo obtener ubicacion.';
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    coords,
    error,
    isLoading,
    requestLocation
  };
}
