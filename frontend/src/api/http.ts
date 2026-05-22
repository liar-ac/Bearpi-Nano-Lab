import { API_BASE } from '@/api/config';

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message);
  }
}

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';
const USER_KEY = 'bearpi_user';
export const AUTH_CLEARED_EVENT = 'bearpi-auth-cleared';

let refreshPromise: Promise<string | null> | null = null;

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;

  refreshPromise = (async () => {
    try {
      const resp = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken })
      });
      if (!resp.ok) {
        clearSession();
        return null;
      }
      const data = (await resp.json()) as { access?: string; access_token?: string };
      const next = data.access ?? data.access_token ?? null;
      if (next) localStorage.setItem(TOKEN_KEY, next);
      return next;
    } catch {
      clearSession();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event(AUTH_CLEARED_EVENT));
}

function buildHeaders(options: RequestInit, token: string | null) {
  const headers = new Headers(options.headers);
  if (options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  let response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: buildHeaders(options, token)
  });

  if (response.status === 401 && !path.startsWith('/auth/')) {
    const nextToken = await refreshAccessToken();
    if (nextToken) {
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: buildHeaders(options, nextToken)
      });
    }
  }

  if (!response.ok) {
    let message = `请求失败：${response.status}`;
    try {
      const body = await response.json();
      message = body.detail ?? body.message ?? message;
    } catch {
      // Keep the generic message when the server did not return JSON.
    }
    if (response.status === 401) {
      clearSession();
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
