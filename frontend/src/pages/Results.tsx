import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import StatusBadge from "../components/StatusBadge";
import { deleteFile, getFile, getMeasurements } from "../services/api";
import type {
  FeatureMeasurement,
  FileRecord,
  MeasurementListResponse,
} from "../types";
import {
  formatDate,
  formatMeasurement,
  formatNumber,
  formatProperty,
} from "../utils/format";

const MAX_ROWS = 500;

interface Summary {
  total: number;
  calculated: number;
  notRequired: number;
  unsupported: number;
  unavailable: number;
  areaTotal: number | null;
  lengthTotal: number | null;
}

function summarize(data: MeasurementListResponse): Summary {
  const summary: Summary = {
    total: data.feature_count,
    calculated: 0,
    notRequired: 0,
    unsupported: 0,
    unavailable: 0,
    areaTotal: null,
    lengthTotal: null,
  };

  let areaSum = 0;
  let areaSeen = false;
  let lengthSum = 0;
  let lengthSeen = false;

  for (const measurement of data.measurements) {
    switch (measurement.measurement_status) {
      case "CALCULATED":
        summary.calculated += 1;
        break;
      case "NOT_REQUIRED":
        summary.notRequired += 1;
        break;
      case "UNSUPPORTED":
        summary.unsupported += 1;
        break;
      case "UNAVAILABLE":
        summary.unavailable += 1;
        break;
    }

    if (measurement.measurement_value !== null) {
      if (measurement.measurement_type === "area") {
        areaSum += measurement.measurement_value;
        areaSeen = true;
      } else if (measurement.measurement_type === "length") {
        lengthSum += measurement.measurement_value;
        lengthSeen = true;
      }
    }
  }

  summary.areaTotal = areaSeen ? areaSum : null;
  summary.lengthTotal = lengthSeen ? lengthSum : null;
  return summary;
}

function SummaryCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}): ReactNode {
  return (
    <div className="panel p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1.5 text-xl font-semibold tabular-nums text-white">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

function PropertyChips({ properties }: { properties: Record<string, unknown> }): ReactNode {
  const entries = Object.entries(properties).filter(
    ([, value]) => value !== null && value !== undefined && value !== "",
  );

  if (entries.length === 0) {
    return <span className="text-slate-600">—</span>;
  }

  return (
    <div className="flex max-w-[18rem] flex-wrap gap-1">
      {entries.slice(0, 4).map(([key, value]) => (
        <span
          key={key}
          title={`${key}: ${formatProperty(value)}`}
          className="inline-flex max-w-full items-center gap-1 rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-300"
        >
          <span className="text-slate-500">{key}</span>
          <span className="truncate text-slate-200">{formatProperty(value)}</span>
        </span>
      ))}
      {entries.length > 4 && (
        <span className="text-xs text-slate-500">+{entries.length - 4} more</span>
      )}
    </div>
  );
}

function MeasurementTable({ rows }: { rows: FeatureMeasurement[] }): ReactNode {
  const visible = rows.slice(0, MAX_ROWS);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-left">
        <thead className="border-b border-slate-800 bg-slate-900/60">
          <tr>
            <th className="table-head">#</th>
            <th className="table-head">Geometry</th>
            <th className="table-head">Properties</th>
            <th className="table-head">Measurement</th>
            <th className="table-head">Status</th>
            <th className="table-head">Measured in</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr
              key={row.feature_index}
              className="border-b border-slate-800/80 transition hover:bg-slate-800/30"
            >
              <td className="table-cell tabular-nums text-slate-500">{row.feature_index + 1}</td>
              <td className="table-cell">
                <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-slate-300">
                  {row.geometry_type ?? "null"}
                </span>
              </td>
              <td className="table-cell">
                <PropertyChips properties={row.properties} />
              </td>
              <td className="table-cell">
                <span className="font-medium tabular-nums text-white">
                  {formatMeasurement(row.measurement_value, row.measurement_unit)}
                </span>
                {row.measurement_type && (
                  <span className="ml-2 text-xs uppercase tracking-wide text-slate-500">
                    {row.measurement_type}
                  </span>
                )}
                {row.measurement_reason && (
                  <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">
                    {row.measurement_reason}
                  </p>
                )}
              </td>
              <td className="table-cell">
                <StatusBadge status={row.measurement_status} />
              </td>
              <td className="table-cell font-mono text-xs text-slate-400">
                {row.projected_crs ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > MAX_ROWS && (
        <p className="border-t border-slate-800 px-4 py-3 text-xs text-slate-500">
          Showing the first {MAX_ROWS} of {rows.length} features.
        </p>
      )}
    </div>
  );
}

export default function ResultsPage(): ReactNode {
  const { fileId } = useParams<{ fileId: string }>();
  const navigate = useNavigate();
  const [file, setFile] = useState<FileRecord | null>(null);
  const [data, setData] = useState<MeasurementListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!fileId) {
      setError("Missing file id.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [record, measurements] = await Promise.all([
        getFile(fileId),
        getMeasurements(fileId),
      ]);
      setFile(record);
      setData(measurements);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this file.");
    } finally {
      setLoading(false);
    }
  }, [fileId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleDelete = useCallback(async () => {
    if (!file) {
      return;
    }
    if (!window.confirm(`Delete "${file.filename}" and all of its measurements?`)) {
      return;
    }
    setDeleting(true);
    try {
      await deleteFile(file.id);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete this file.");
    } finally {
      setDeleting(false);
    }
  }, [file, navigate]);

  const summary = useMemo(() => (data ? summarize(data) : null), [data]);

  if (loading) {
    return (
      <div className="panel flex items-center justify-center gap-3 p-16 text-sm text-slate-400">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-indigo-400" />
        Loading measurements…
      </div>
    );
  }

  if (error || !file || !data || !summary) {
    return (
      <div className="panel mx-auto max-w-lg p-10 text-center">
        <p className="text-lg font-semibold text-rose-300">Could not load the file</p>
        <p className="mt-2 text-sm text-slate-400">{error ?? "Unexpected response."}</p>
        <Link to="/" className="btn-primary mt-6">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const coverage =
    summary.total > 0 ? `${Math.round((summary.calculated / summary.total) * 100)}%` : "—";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/" className="text-xs text-slate-400 hover:text-indigo-300">
            ← Dashboard
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-white break-all">{file.filename}</h1>
            <StatusBadge status={file.status} />
            <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-300 ring-1 ring-inset ring-slate-700">
              {file.file_type === "kml" ? "KML" : "Shapefile"}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-400">
            {formatNumber(summary.total)} feature{summary.total === 1 ? "" : "s"} · source CRS{" "}
            <span className="font-mono text-slate-300">{file.source_crs ?? "unknown"}</span> ·
            uploaded {formatDate(file.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost" onClick={() => void load()}>
            Reload
          </button>
          <button
            type="button"
            onClick={() => void handleDelete()}
            disabled={deleting}
            className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-sm font-medium text-rose-300 transition hover:bg-rose-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      {file.status === "FAILED" && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          <span className="font-semibold">Processing failed.</span>{" "}
          {file.error_message ?? "No further details were recorded."}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryCard label="Features" value={formatNumber(summary.total)} hint="stored per feature" />
        <SummaryCard
          label="Total area"
          value={summary.areaTotal === null ? "—" : `${formatNumber(summary.areaTotal)} m²`}
          hint={summary.areaTotal === null ? "no polygon features" : "sum of measured polygons"}
        />
        <SummaryCard
          label="Total length"
          value={
            summary.lengthTotal === null ? "—" : `${formatNumber(summary.lengthTotal)} m`
          }
          hint={summary.lengthTotal === null ? "no line features" : "sum of measured lines"}
        />
        <SummaryCard
          label="Calculated"
          value={`${formatNumber(summary.calculated)} / ${formatNumber(summary.total)}`}
          hint={`${coverage} of features measured`}
        />
      </div>

      <section className="panel overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Per-feature measurements</h2>
            <p className="text-xs text-slate-500">
              {summary.notRequired} not required · {summary.unsupported} unsupported ·{" "}
              {summary.unavailable} unavailable
            </p>
          </div>
        </div>
        {data.measurements.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-slate-400">
            No measurements were stored for this file.
          </p>
        ) : (
          <MeasurementTable rows={data.measurements} />
        )}
      </section>
    </div>
  );
}
