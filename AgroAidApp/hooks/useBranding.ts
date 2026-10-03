import {
  createContext,
  createElement,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from 'react';

import { colors } from '@/constants/colors';
import { apiFetch } from '@/services/api';

export type Branding = {
  logo_url: string | null;
  primary_color: string;
  accent_color: string;
  app_name: string;
  footer_text: string;
};

const defaultBranding: Branding = {
  logo_url: null,
  primary_color: colors.brand.primary,
  accent_color: colors.brand.secondary,
  app_name: 'AgroAid',
  footer_text: 'AgroAid - Seguridad agricola integral'
};

type BrandingContextValue = {
  branding: Branding;
  tenantSlug: string;
  isLoading: boolean;
  primaryColor: string;
  accentColor: string;
  setTenantSlug: (slug: string) => void;
  reloadBranding: (slug?: string) => Promise<void>;
};

const BrandingContext = createContext<BrandingContextValue | null>(null);

function normalizeBranding(data: Partial<Branding>): Branding {
  return {
    logo_url: data.logo_url ?? defaultBranding.logo_url,
    primary_color: data.primary_color ?? defaultBranding.primary_color,
    accent_color: data.accent_color ?? defaultBranding.accent_color,
    app_name: data.app_name ?? defaultBranding.app_name,
    footer_text: data.footer_text ?? defaultBranding.footer_text
  };
}

export function BrandingProvider({ children }: { children: ReactNode }) {
  const [branding, setBranding] = useState<Branding>(defaultBranding);
  const [tenantSlug, setTenantSlug] = useState('default');
  const [isLoading, setIsLoading] = useState(true);

   const reloadBranding = useCallback(
    async (slug = tenantSlug) => {
      const normalizedSlug = slug.trim() || 'default';
      setTenantSlug(normalizedSlug);
      setIsLoading(true);
      try {
        const params = new URLSearchParams({ slug: normalizedSlug });
        const data = await apiFetch<Branding>(`/api/branding?${params}`, {
          skipAuth: true
        });
        setBranding(normalizeBranding(data));
      } catch {
        setBranding(defaultBranding);
      } finally {
        setIsLoading(false);
      }
    },
    [tenantSlug]
  );
  useEffect(() => {
    reloadBranding('default');
  }, []);

  const value = useMemo<BrandingContextValue>(
    () => ({
      branding,
      tenantSlug,
      isLoading,
      primaryColor: branding.primary_color,
      accentColor: branding.accent_color,
      setTenantSlug,
      reloadBranding
    }),
    [branding, tenantSlug, isLoading, reloadBranding]
  );
  return createElement(BrandingContext.Provider, { value }, children);
}

export function useBranding() {
  const context = useContext(BrandingContext);

  if (!context) {
    throw new Error('useBranding debe usarse dentro de BrandingProvider');
  }

  return context;
}
