import { API_BASE } from '@/api/config';

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  data?: unknown;
  header?: Record<string, string>;
}

const TOKEN_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';
const USER_KEY = 'bearpi_user';
export const AUTH_CLEARED_EVENT = 'bearpi-auth-cleared';

let refreshPromise: Promise<string | null> | null = null;

function clearSession() {
  uni.removeStorageSync(TOKEN_KEY);
  uni.removeStorageSync(REFRESH_KEY);
  uni.removeStorageSync(USER_KEY);
  uni.$emit(AUTH_CLEARED_EVENT);
}

function rawRequest<T>(path: string, options: RequestOptions, token: string | null): Promise<{ statusCode: number; data: T }> {
  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.header ?? {})
  };
  if (token) header.Authorization = `Bearer ${token}`;
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE}${path}`,
      method: (options.method ?? 'GET') as UniNamespace.RequestOptions['method'],
      data: options.data as Record<string, unknown> | string | undefined,
      header,
      timeout: 15000,
      success: (res) => resolve({ statusCode: res.statusCode, data: res.data as T }),
      fail: (err) => reject(new ApiError(err.errMsg || '网络异常'))
    });
  });
}

function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;
  const refreshToken = uni.getStorageSync(REFRESH_KEY);
  if (!refreshToken) return Promise.resolve(null);

  refreshPromise = rawRequest<{ access?: string; access_token?: string }>(
    '/auth/refresh',
    { method: 'POST', data: { refresh: refreshToken } },
    null
  )
    .then((res) => {
      if (res.statusCode < 200 || res.statusCode >= 300) {
        clearSession();
        return null;
      }
      const next = res.data?.access ?? res.data?.access_token ?? null;
      if (next) uni.setStorageSync(TOKEN_KEY, next);
      return next;
    })
    .catch(() => {
      clearSession();
      return null;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = uni.getStorageSync(TOKEN_KEY);
  let res = await rawRequest<T>(path, options, token || null);

  if (res.statusCode === 401 && !path.startsWith('/auth/')) {
    const nextToken = await refreshAccessToken();
    if (nextToken) {
      res = await rawRequest<T>(path, options, nextToken);
    }
  }

  if (res.statusCode >= 200 && res.statusCode < 300) {
    if (res.statusCode === 204) return undefined as T;
    return res.data;
  }

  const rawData = res.data as unknown;
  let message = `请求失败：${res.statusCode}`;
  if (rawData && typeof rawData === 'object') {
    const body = rawData as Record<string, unknown>;
    const candidates = [body.error, body.detail, body.message];
    if (Array.isArray(body.non_field_errors)) {
      candidates.push(body.non_field_errors.join(', '));
    }
    const found = candidates.find((v) => typeof v === 'string' && (v as string).length > 0);
    if (found) message = found as string;
  } else if (typeof rawData === 'string' && rawData.length > 0) {
    message = rawData.slice(0, 500);
  }
  if (res.statusCode === 401) clearSession();
  throw new ApiError(message, res.statusCode);
}
