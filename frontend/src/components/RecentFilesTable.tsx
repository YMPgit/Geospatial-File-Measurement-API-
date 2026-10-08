import { type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import StatusBadge from "./StatusBadge";
import type { FileRecord } from "../types";
import { formatDate } from "../utils/format";

function TypeChip({ file_type }: { file_type: string }): ReactNode {
  const label = file_type === "kml" ? "KML" : "Shapefile";
  const classes =
    file_type === "kml"
      ? "bg-sky-500/10 text-sky-300 ring-sky-500/30"
      : "bg-violet-500/10 text-violet-300 ring-violet-500/30";
  return (
    <span
      className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}
    >
      {label}
    </span>
  );
}

function SkeletonRows(): ReactNode {
  return (
    <>
      {[0, 1, 2].map((row) => (
        <tr key={row} className="animate-pulse border-b border-slate-800/80">
          <td className="table-cell">
            <div className="h-4 w-48 rounded bg-slate-800" />
          </td>
          <td className="table-cell">
            <div className="h-4 w-20 rounded bg-slate-800" />
          </td>
          <td className="table-cell">
            <div className="h-4 w-12 rounded bg-slate-800" />
          </td>
          <td className="table-cell">
            <div className="h-4 w-24 rounded bg-slate-800" />
          </td>
          <td className="table-cell">
            <div className="h-4 w-24 rounded bg-slate-800" />
          </td>
          <td className="table-cell">
            <div className="h-4 w-28 rounded bg-slate-800" />
          </td>
        </tr>
      ))}
    </>
  );
}

export default function RecentFilesTable({
  files,
  loading,
  error,
  onRetry,
  onDelete,
}: {
  files: FileRecord[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onDelete?: (file: FileRecord) => void;
}): ReactNode {
  const navigate = useNavigate();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-left">
        <thead className="border-b border-slate-800 bg-slate-900/60">
          <tr>
            <th className="table-head">File</th>
            <th className="table-head">Type</th>
            <th className="table-head">Features</th>
            <th className="table-head">Source CRS</th>
            <th className="table-head">Status</th>
            <th className="table-head">Uploaded</th>
            <th className="table-head text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading && <SkeletonRows />}

          {!loading && files.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-10 text-center text-sm text-slate-400">
                {error ??
                  "No files uploaded yet — drop a KML or Shapefile ZIP above to get started."}
              </td>
            </tr>
          )}

          {!loading &&
            files.map((file) => (
              <tr
                key={file.id}
                onClick={() => navigate(`/files/${file.id}`)}
                className="cursor-pointer border-b border-slate-800/80 transition hover:bg-slate-800/40"
              >
                <td className="table-cell">
                  <Link
                    to={`/files/${file.id}`}
                    className="font-medium text-white hover:text-indigo-300"
                    onClick={(event) => event.stopPropagation()}
                  >
                    {file.filename}
                  </Link>
                </td>
                <td className="table-cell">
                  <TypeChip file_type={file.file_type} />
                </td>
                <td className="table-cell tabular-nums">{file.feature_count}</td>
                <td className="table-cell font-mono text-xs text-slate-400">
                  {file.source_crs ?? "—"}
                </td>
                <td className="table-cell">
                  <StatusBadge status={file.status} />
                </td>
                <td className="table-cell whitespace-nowrap text-slate-400">
                  {formatDate(file.created_at)}
                </td>
                <td className="table-cell text-right">
                  {onDelete && (
                    <button
                      type="button"
                      aria-label={`Delete ${file.filename}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(file);
                      }}
                      className="rounded px-2 py-1 text-xs font-medium text-rose-400 transition hover:bg-rose-500/10 hover:text-rose-300"
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
        </tbody>
      </table>

      {error && !loading && files.length > 0 && (
        <div className="flex items-center justify-between gap-3 border-t border-slate-800 px-4 py-3 text-sm text-rose-300">
          <span>{error}</span>
          <button type="button" className="btn-ghost" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
