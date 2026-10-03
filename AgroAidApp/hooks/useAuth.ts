import * as SecureStore from 'expo-secure-store';
import {
  createElement,
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import { Platform } from 'react-native';

import {
  configureAuthTokenGetter,
  configureTokenRefresh,
  loginRequest,
  refreshRequest,
  registerRequest,
  type LoginPayload,
  type RegisterPayload
} from '@/services/api';

const ACCESS_TOKEN_KEY = 'agroaid.accessToken';
const REFRESH_TOKEN_KEY = 'agroaid.refreshToken';

type AuthContextValue = {
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function getStoredItem(key: string) {
  if (Platform.OS === 'web') {
    if (typeof window === 'undefined') {
      return null;
    }

    return window.localStorage.getItem(key);
  }

  return SecureStore.getItemAsync(key);
}

async function setStoredItem(key: string, value: string) {
  if (Platform.OS === 'web') {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(key, value);
    return;
  }

  await SecureStore.setItemAsync(key, value);
}

async function deleteStoredItem(key: string) {
  if (Platform.OS === 'web') {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.removeItem(key);
    return;
  }

  await SecureStore.deleteItemAsync(key);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const accessTokenRef = useRef<string | null>(null);
  const refreshTokenRef = useRef<string | null>(null);

  const persistTokens = useCallback(
    async (tokens: { access_token: string; refresh_token?: string }) => {
      accessTokenRef.current = tokens.access_token;
      setAccessToken(tokens.access_token);
      await setStoredItem(ACCESS_TOKEN_KEY, tokens.access_token);

      if (tokens.refresh_token) {
        refreshTokenRef.current = tokens.refresh_token;
        await setStoredItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
      }
    },
    []
  );

  const logout = useCallback(async () => {
    accessTokenRef.current = null;
    refreshTokenRef.current = null;
    setAccessToken(null);
    await Promise.all([
      deleteStoredItem(ACCESS_TOKEN_KEY),
      deleteStoredItem(REFRESH_TOKEN_KEY)
    ]);
  }, []);

  const refreshSession = useCallback(async () => {
    const refreshToken = refreshTokenRef.current;

    if (!refreshToken) {
      await logout();
      return null;
    }

    try {
      const tokens = await refreshRequest(refreshToken);
      await persistTokens({
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token ?? refreshToken
      });
      return tokens.access_token;
    } catch {
      await logout();
      return null;
    }
  }, [logout, persistTokens]);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const tokens = await loginRequest(payload);
      await persistTokens(tokens);
    },
    [persistTokens]
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      await registerRequest(payload);
      await login({
        email: payload.email,
        password: payload.password
      });
    },
    [login]
  );

  useEffect(() => {
    configureAuthTokenGetter(() => accessTokenRef.current);
    configureTokenRefresh(refreshSession);
  }, [refreshSession]);

  useEffect(() => {
    let mounted = true;

    async function hydrateSession() {
      try {
        const [storedAccessToken, storedRefreshToken] = await Promise.all([
          getStoredItem(ACCESS_TOKEN_KEY),
          getStoredItem(REFRESH_TOKEN_KEY)
        ]);

        if (!mounted) {
          return;
        }

        accessTokenRef.current = storedAccessToken;
        refreshTokenRef.current = storedRefreshToken;
        setAccessToken(storedAccessToken);
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    }

    hydrateSession();

    return () => {
      mounted = false;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken,
      isAuthenticated: Boolean(accessToken),
      isLoading,
      login,
      logout,
      refreshSession,
      register
    }),
    [accessToken, isLoading, login, logout, refreshSession, register]
  );

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }

  return context;
}
