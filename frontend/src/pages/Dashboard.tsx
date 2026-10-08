import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import RecentFilesTable from "../components/RecentFilesTable";
import Uploader from "../components/Uploader";
import { deleteFile, getHealth, listFiles } from "../services/api";
import type { FileRecord } from "../types";

type HealthState = "checking" | "online" | "offline";

function HealthChip({ state }: { state: HealthState }): ReactNode {
  const styles: Record<HealthState, { dot: string; label: string; chip: string }> = {
    checking: {
      dot: "bg-slate-400",
      label: "Checking API…",
      chip: "text-slate-400 ring-slate-600",
    },
    online: {
      dot: "bg-emerald-400",
      label: "API online",
      chip: "text-emerald-300 ring-emerald-500/40",
    },
    offline: {
      dot: "bg-rose-400",
      label: "API offline",
      chip: "text-rose-300 ring-rose-500/40",
    },
  };
  const style = styles[state];

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1 text-xs font-medium ring-1 ring-inset ${style.chip}`}
    >
      <span className={`h-2 w-2 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}

function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load recent files.";
}

export default function DashboardPage(): ReactNode {
  const navigate = useNavigate();
  const [health, setHealth] = useState<HealthState>("checking");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [filesError, setFilesError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    setFilesLoading(true);
    setFilesError(null);
    try {
      const response = await listFiles(10);
      setFiles(response.items);
    } catch (error) {
      setFilesError(toMessage(error));
    } finally {
      setFilesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFiles();
    getHealth()
      .then(() => setHealth("online"))
      .catch(() => setHealth("offline"));
  }, [loadFiles]);

  const handleDelete = useCallback(async (file: FileRecord) => {
    if (!window.confirm(`Delete "${file.filename}" and all of its measurements?`)) {
      return;
    }
    setDeletingId(file.id);
    setFilesError(null);
    try {
      await deleteFile(file.id);
      setFiles((previous) => previous.filter((item) => item.id !== file.id));
    } catch (error) {
      setFilesError(toMessage(error));
    } finally {
      setDeletingId(null);
    }
  }, []);

  return (
    <div className="space-y-8">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Upload a geospatial file</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Every feature is read with GDAL and its area or length is measured in a metric
            projection. Results are stored per feature and shown on the results page.
          </p>
        </div>
        <HealthChip state={health} />
      </section>

      <Uploader onUploaded={(fileId) => navigate(`/files/${fileId}`)} />

      <section className="panel overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-white">Recent uploads</h2>
            <p className="text-xs text-slate-500">Newest first — click a row to inspect it.</p>
          </div>
          <button type="button" className="btn-ghost" onClick={() => void loadFiles()}>
            Refresh
          </button>
        </div>
        <RecentFilesTable
          files={files}
          loading={filesLoading}
          error={filesError}
          onRetry={() => void loadFiles()}
          onDelete={deletingId ? undefined : (file) => void handleDelete(file)}
        />
      </section>
    </div>
  );
}
