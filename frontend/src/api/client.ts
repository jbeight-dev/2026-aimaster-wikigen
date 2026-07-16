const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const TOKEN_STORAGE_KEY = 'wikigen.token';

let token: string | null = localStorage.getItem(TOKEN_STORAGE_KEY);

export function getToken(): string | null {
  return token;
}

export function setToken(next: string | null): void {
  token = next;
  if (next) {
    localStorage.setItem(TOKEN_STORAGE_KEY, next);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  query?: Record<string, string | undefined>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(API_BASE_URL + path);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, value);
    }
  }

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }

  const res = await fetch(url.toString(), {
    method: options.method ?? 'GET',
    headers,
    body,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const errorBody = data?.error;
    throw new ApiError(
      res.status,
      errorBody?.code ?? 'UNKNOWN',
      errorBody?.message ?? '요청 처리 중 오류가 발생했어요.',
    );
  }

  return data as T;
}

export const apiClient = {
  get: <T>(path: string, query?: Record<string, string | undefined>) =>
    request<T>(path, { method: 'GET', query }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  postForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', formData }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
