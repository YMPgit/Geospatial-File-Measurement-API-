import type { ReactNode } from "react";

interface ToneStyle {
  label: string;
  dot: string;
  chip: string;
}

const TONES: Record<string, ToneStyle> = {
  COMPLETED: {
    label: "Completed",
    dot: "bg-emerald-400",
    chip: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  },
  FAILED: {
    label: "Failed",
    dot: "bg-rose-400",
    chip: "bg-rose-500/10 text-rose-300 ring-rose-500/30",
  },
  PROCESSING: {
    label: "Processing",
    dot: "bg-amber-400",
    chip: "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  },
  CALCULATED: {
    label: "Calculated",
    dot: "bg-emerald-400",
    chip: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
  },
  NOT_REQUIRED: {
    label: "Not required",
    dot: "bg-sky-400",
    chip: "bg-sky-500/10 text-sky-300 ring-sky-500/30",
  },
  UNSUPPORTED: {
    label: "Unsupported",
    dot: "bg-amber-400",
    chip: "bg-amber-500/10 text-amber-300 ring-amber-500/30",
  },
  UNAVAILABLE: {
    label: "Unavailable",
    dot: "bg-slate-400",
    chip: "bg-slate-500/10 text-slate-300 ring-slate-500/30",
  },
};

const FALLBACK: ToneStyle = {
  label: "Unknown",
  dot: "bg-slate-400",
  chip: "bg-slate-500/10 text-slate-300 ring-slate-500/30",
};

export default function StatusBadge({
  status,
  className = "",
}: {
  status: string;
  className?: string;
}): ReactNode {
  const style = TONES[status] ?? FALLBACK;

  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style.chip} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );
}
