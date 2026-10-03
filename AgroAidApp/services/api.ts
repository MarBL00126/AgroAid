import { config } from '@/constants/config';

export type AuthTokens = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  username: string;
  email: string;
  password: string;
  tenant_slug?: string;
};

type RequestOptions = RequestInit & {
  skipAuth?: boolean;
  skipRefresh?: boolean;
};

let getAccessToken: (() => string | null) | null = null;
let refreshAccessToken: (() => Promise<string | null>) | null = null;

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object' && 'detail' in detail
          ? String((detail as { detail: unknown }).detail)
          : `Error HTTP ${status}`;

    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

export function configureAuthTokenGetter(getter: () => string | null) {
  getAccessToken = getter;
}

export function configureTokenRefresh(handler: () => Promise<string | null>) {
  refreshAccessToken = handler;
}

function buildUrl(path: string) {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const baseUrl = config.apiBaseUrl.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  return `${baseUrl}${normalizedPath}`;
}

async function parseResponse(response: Response) {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { skipAuth, skipRefresh, headers, body, ...fetchOptions } = options;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), config.requestTimeoutMs);
  const token = getAccessToken?.();
  const requestHeaders = new Headers(headers);
  const isFormData =
    typeof FormData !== 'undefined' && body instanceof FormData;

  if (!isFormData && body && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  if (!skipAuth && token && !requestHeaders.has('Authorization')) {
    requestHeaders.set('Authorization', `Bearer ${token}`);
  }

  try {
    const response = await fetch(buildUrl(path), {
      ...fetchOptions,
      body,
      headers: requestHeaders,
      signal: controller.signal
    });

    if (
      response.status === 401 &&
      !skipAuth &&
      !skipRefresh &&
      refreshAccessToken
    ) {
      const nextToken = await refreshAccessToken();

      if (nextToken) {
        requestHeaders.set('Authorization', `Bearer ${nextToken}`);

        const retry = await fetch(buildUrl(path), {
          ...fetchOptions,
          body,
          headers: requestHeaders
        });

        if (!retry.ok) {
          throw new ApiError(retry.status, await parseResponse(retry));
        }

        return parseResponse(retry) as Promise<T>;
      }
    }

    if (!response.ok) {
      throw new ApiError(response.status, await parseResponse(response));
    }

    return parseResponse(response) as Promise<T>;
  } finally {
    clearTimeout(timeout);
  }
}

export function loginRequest(payload: LoginPayload) {
  return apiFetch<AuthTokens>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
    skipAuth: true
  });
}

export function registerRequest(payload: RegisterPayload) {
  return apiFetch<{ message: string; user: unknown }>('/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      tenant_slug: 'default',
      ...payload
    }),
    skipAuth: true
  });
}

export function refreshRequest(refreshToken: string) {
  return apiFetch<AuthTokens>('/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
    skipAuth: true,
    skipRefresh: true
  });
}
