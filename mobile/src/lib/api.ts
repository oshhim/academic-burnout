import { UploadType, type File } from 'expo-file-system';

// Shared HTTP client for the EMPath+ backend (frontend guide, section 6).
// The development key is an administrator key for the whole database: fine for a
// trusted local test, never for a shipped app.

export type Connection = { baseUrl: string; apiKey: string };

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId: string | null,
  ) {
    super(message);
  }
}

const STATUS_HINTS: Record<number, string> = {
  401: 'API key does not match the backend .env.',
  403: 'Blocked by consent or research-mode settings.',
  404: 'Participant or record not found. Register on the Profile tab.',
  409: 'Conflicts with an existing record or lifecycle state.',
  413: 'Request or file is too large.',
  422: 'The backend rejected a field value.',
  503: 'The model is unavailable on the backend.',
};

function describe(status: number, body: any): { code: string; message: string } {
  const error = body?.error;
  if (!error) return { code: 'http_error', message: STATUS_HINTS[status] ?? `HTTP ${status}` };
  if (Array.isArray(error.issues)) {
    const issues = error.issues.map((i: any) => `${(i.loc ?? []).slice(1).join('.') || 'request'}: ${i.message}`);
    return { code: error.code, message: issues.join('\n') };
  }
  return { code: error.code ?? 'http_error', message: error.message ?? STATUS_HINTS[status] ?? `HTTP ${status}` };
}

export function apiRoot(connection: Connection) {
  return connection.baseUrl.replace(/\/+$/, '');
}

function unreachable(connection: Connection, cause: unknown) {
  const detail = cause instanceof Error && cause.message ? ` (${cause.message})` : '';
  return new ApiError(0, 'network_error', `Cannot reach ${apiRoot(connection)}${detail}. Is the backend running with --host 0.0.0.0 on the same Wi-Fi?`, null);
}

export async function api<T = any>(
  connection: Connection,
  path: string,
  options: { method?: 'GET' | 'POST' | 'DELETE'; body?: unknown } = {},
): Promise<T> {
  const { method = options.body ? 'POST' : 'GET', body } = options;
  let response: Response;
  try {
    response = await fetch(`${apiRoot(connection)}/api/v1${path}`, {
      method,
      headers: { 'X-API-Key': connection.apiKey, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw unreachable(connection, e);
  }
  const result = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const { code, message } = describe(response.status, result);
    throw new ApiError(response.status, code, message, response.headers.get('X-Request-ID'));
  }
  return result as T;
}

/**
 * Multipart upload of a local file with extra form fields, done natively by
 * expo-file-system (more reliable for file parts than fetch + FormData in React Native).
 */
export async function uploadFile<T = any>(connection: Connection, path: string, file: File, fieldName: string, parameters: Record<string, string>, mimeType: string): Promise<T> {
  let response: { status: number; body: string; headers: Record<string, string> };
  try {
    response = await file.upload(`${apiRoot(connection)}/api/v1${path}`, {
      uploadType: UploadType.MULTIPART,
      fieldName,
      mimeType,
      parameters,
      headers: { 'X-API-Key': connection.apiKey },
    });
  } catch (e) {
    throw unreachable(connection, e);
  }
  let result: any = null;
  try {
    result = JSON.parse(response.body);
  } catch {}
  if (response.status < 200 || response.status >= 300) {
    const { code, message } = describe(response.status, result);
    const requestId = Object.entries(response.headers).find(([k]) => k.toLowerCase() === 'x-request-id')?.[1] ?? null;
    throw new ApiError(response.status, code, message, requestId);
  }
  return result as T;
}

/** Public, non-/api/v1 routes such as /health. */
export async function getPublic<T = any>(connection: Connection, path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiRoot(connection)}${path}`);
  } catch (e) {
    throw unreachable(connection, e);
  }
  if (!response.ok) throw new ApiError(response.status, 'http_error', `HTTP ${response.status} for ${path}`, null);
  return response.json();
}

export function uid(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}
