/** Thin typed fetch client for the Geospatial File Measurement API. */

import type {
  FileListResponse,
  FileRecord,
  HealthResponse,
  MeasurementListResponse,
  UploadResponse,
} from "../types";

/** Empty string means same-origin (used behind the Docker/nginx proxy). */
export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL ?? "").replace(
  /\/+$/,
  "",
);

const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 180_000;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractDetail(payload: unknown): string | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const body = payload as { detail?: unknown; status?: unknown; error_message?: unknown };

  if (typeof body.detail === "string" && body.detail.trim()) {
    return body.detail;
  }
  if (Array.isArray(body.detail)) {
    const messages = body.detail.map((entry) =>
      entry && typeof entry === "object" && "msg" in entry ? String(entry.msg) : String(entry),
    );
    if (messages.length > 0) {
      return messages.join("; ");
    }
  }
  // Phase-2 failures return the persisted FAILED record instead of {detail}.
  if (body.status === "FAILED" && typeof body.error_message === "string") {
    return `Processing failed: ${body.error_message}`;
  }
  return null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    clearTimeout(timer);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "The request timed out. Please try again.");
    }
    throw new ApiError(0, "Could not reach the API. Is the backend running?");
  }
  clearTimeout(timer);

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail = extractDetail(payload);
    throw new ApiError(
      response.status,
      detail ?? `Request failed with status ${response.status}.`,
    );
  }
  return payload as T;
}

export function uploadFile(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  return request<UploadResponse>(
    "/api/files/",
    { method: "POST", body: form },
    UPLOAD_TIMEOUT_MS,
  );
}

export function listFiles(limit = 20, offset = 0): Promise<FileListResponse> {
  return request<FileListResponse>(`/api/files/?limit=${limit}&offset=${offset}`);
}

export function getFile(fileId: string): Promise<FileRecord> {
  return request<FileRecord>(`/api/files/${fileId}/`);
}

export function getMeasurements(fileId: string): Promise<MeasurementListResponse> {
  return request<MeasurementListResponse>(`/api/files/${fileId}/measurements/`);
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function deleteFile(fileId: string): Promise<void> {
  return request<void>(`/api/files/${fileId}/`, { method: "DELETE" });
}
