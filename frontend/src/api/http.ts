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
  if (typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
}

export async function request<T>(path: string, options: RequestInit = {}, signal?: AbortSignal | null): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY);
  let response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: buildHeaders(options, token),
    signal: signal ?? undefined
  });

  if (response.status === 401 && !path.startsWith('/auth/')) {
    const nextToken = await refreshAccessToken();
    if (nextToken) {
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: buildHeaders(options, nextToken),
        signal: signal ?? undefined
      });
    }
  }

  if (!response.ok) {
    let message = `请求失败：${response.status}`;
    try {
      const text = await response.text();
      if (text && text.length > 0) {
        try {
          const body = JSON.parse(text);
          if (typeof body === 'object' && body !== null) {
            const candidates = [body.error, body.detail, body.message];
            if (Array.isArray(body.non_field_errors)) {
              candidates.push(body.non_field_errors.join(', '));
            }
            let found = candidates.find((v) => typeof v === 'string' && v.length > 0);
            if (!found) {
              for (const value of Object.values(body)) {
                if (typeof value === 'string' && value.length > 0) {
                  found = value;
                  break;
                }
                if (Array.isArray(value) && typeof value[0] === 'string') {
                  found = value[0];
                  break;
                }
              }
            }
            message = found ?? message;
          } else if (typeof body === 'string' && body.length > 0) {
            message = body.slice(0, 500);
          }
        } catch {
          // Body is not JSON; use the raw text as the error message.
          message = text.slice(0, 500);
        }
      }
    } catch {
      // Keep the generic message when the server did not return readable body.
    }
    if (response.status === 401) {
      clearSession();
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) return null as unknown as T;
  return response.json() as Promise<T>;
}
