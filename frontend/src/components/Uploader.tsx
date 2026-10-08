import { useRef, useState, type DragEvent, type ReactNode } from "react";

import { uploadFile } from "../services/api";
import { formatBytes } from "../utils/format";

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".kml", ".zip"];

function validate(file: File): string | null {
  const lower = file.name.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.some((extension) => lower.endsWith(extension))) {
    return "Unsupported file type. Please choose a .kml or .zip (Shapefile) file.";
  }
  if (file.size === 0) {
    return "The selected file is empty.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is ${formatBytes(file.size)} — the upload limit is 20 MB.`;
  }
  return null;
}

export default function Uploader({
  onUploaded,
}: {
  onUploaded: (fileId: string) => void;
}): ReactNode {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function accept(candidate: File | null | undefined): void {
    if (!candidate) {
      return;
    }
    const problem = validate(candidate);
    if (problem) {
      setSelected(null);
      setError(problem);
      return;
    }
    setError(null);
    setSelected(candidate);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setDragging(false);
    accept(event.dataTransfer.files?.[0]);
  }

  async function handleSubmit(): Promise<void> {
    if (!selected || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const record = await uploadFile(selected);
      onUploaded(record.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div className="panel p-6">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 text-center transition ${
          dragging
            ? "border-indigo-400 bg-indigo-500/10"
            : "border-slate-700 bg-slate-950/50 hover:border-slate-500"
        }`}
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="h-8 w-8 text-slate-500"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-.87-8.906 5.25 5.25 0 0 1 10.233-2.33 4.5 4.5 0 0 1 6.077 6.077A4.5 4.5 0 0 1 17.25 19.5H6.75Z"
          />
        </svg>
        <p className="text-sm font-medium text-slate-200">
          Drag &amp; drop a file here, or click to browse
        </p>
        <p className="text-xs text-slate-500">
          Accepted: <span className="text-slate-400">.kml</span> and{" "}
          <span className="text-slate-400">.zip</span> (Shapefile: .shp + .shx + .dbf) · max 20 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".kml,.zip"
          className="hidden"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>

      {selected && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{selected.name}</p>
            <p className="text-xs text-slate-500">{formatBytes(selected.size)}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-ghost"
              disabled={busy}
              onClick={() => {
                setSelected(null);
                setError(null);
              }}
            >
              Clear
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busy}
              onClick={() => void handleSubmit()}
            >
              {busy ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                  Uploading…
                </>
              ) : (
                "Upload & measure"
              )}
            </button>
          </div>
        </div>
      )}

      {busy && (
        <p className="mt-3 text-xs text-slate-400">
          Reading the file, measuring every feature and storing the results…
        </p>
      )}

      {error && (
        <div className="mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
    </div>
  );
}
