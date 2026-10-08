/** Types mirroring the FastAPI response schemas. */

export type FileStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export type MeasurementStatus =
  | "CALCULATED"
  | "NOT_REQUIRED"
  | "UNSUPPORTED"
  | "UNAVAILABLE";

export type MeasurementType = "area" | "length";

export type FileType = "kml" | "shapefile";

export interface UploadResponse {
  id: string;
  filename: string;
  file_type: FileType;
  feature_count: number;
  crs: string | null;
  status: FileStatus;
  error_message?: string | null;
}

export interface FileRecord {
  id: string;
  filename: string;
  file_type: FileType;
  feature_count: number;
  source_crs: string | null;
  status: FileStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface FileListResponse {
  items: FileRecord[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeatureMeasurement {
  feature_index: number;
  geometry_type: string | null;
  properties: Record<string, unknown>;
  measurement_type: MeasurementType | null;
  measurement_value: number | null;
  measurement_unit: string | null;
  measurement_status: MeasurementStatus;
  measurement_reason: string | null;
  projected_crs: string | null;
  geometry: Record<string, unknown> | null;
}

export interface MeasurementListResponse {
  file_id: string;
  filename: string;
  file_type: FileType;
  feature_count: number;
  source_crs: string | null;
  status: FileStatus;
  measurements: FeatureMeasurement[];
}

export interface HealthResponse {
  status: string;
}
