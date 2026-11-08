import { ButtonHTMLAttributes, ReactNode, useEffect, useId, useRef } from "react";

/* ---------- Icons (24px grid, 1.75 stroke, currentColor) ---------- */
const PATHS = {
  home: "M3 11.5 12 4l9 7.5M5.5 10v9.5h13V10",
  chart: "M5 20V11M12 20V5M19 20v-7",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20a7.5 7.5 0 0 1 15 0",
  camera: "M4 8.5A1.5 1.5 0 0 1 5.5 7H8l1.2-2h5.6L16 7h2.5A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9ZM12 16.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z",
  image: "M4 5h16v14H4zM4 16l4.5-4.5 3.5 3.5 2.5-2.5L20 17M9 9.5h.01",
  pen: "M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14ZM20 20l-4-4",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  x: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5 10 17.5 19 7.5",
  alert: "M12 4 3 19.5h18L12 4ZM12 10v4.5M12 17.2h.01",
  trash: "M5 7h14M9 7V5h6v2M7 7l.8 12h8.4L17 7M10 11v5M14 11v5",
  back: "M15 5l-7 7 7 7",
  chevron: "M9 5l7 7-7 7",
  download: "M12 4v11M7.5 11 12 15.5 16.5 11M5 20h14",
  swap: "M7 7h11l-3-3M17 17H6l3 3",
  logout: "M10 5H5v14h5M15 8l4 4-4 4M19 12H9",
  sunrise: "M4 17h16M7 17a5 5 0 0 1 10 0M12 5v3M5.5 9.5l1.8 1.8M18.5 9.5l-1.8 1.8",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4",
  cup: "M5 9h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5V9ZM16 10h1.5a2.5 2.5 0 0 1 0 5H16M8 4v2M12 4v2",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z",
  leaf: "M5 19c0-8 5-14 15-14 0 10-6 15-14 15M5 19c3-5 6-8 10-10",
  mail: "M4 6.5h16v11H4zM4.5 7l7.5 6 7.5-6",
  sparkle: "M12 4l1.8 4.7L18.5 10.5l-4.7 1.8L12 17l-1.8-4.7L5.5 10.5l4.7-1.8L12 4Z",
} as const;
export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"
      className={`shrink-0 ${className}`} aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

/* ---------- Buttons ---------- */
type Variant = "primary" | "secondary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-brand-ink shadow-sm hover:brightness-110 active:brightness-95",
  secondary: "border border-line bg-card text-ink hover:bg-bg active:bg-line/60",
  ghost: "text-ink2 hover:bg-line/50 active:bg-line",
  danger: "border border-danger/30 bg-danger-soft text-danger hover:brightness-95",
};

export function Button({ variant = "primary", icon, loading, className = "", children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; icon?: IconName; loading?: boolean }) {
  return (
    <button {...rest} disabled={disabled || loading}
      className={`inline-flex min-h-[48px] items-center justify-center gap-2 rounded-xl px-5 text-[15px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}>
      {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden /> : icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

export function IconButton({ label, icon, className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: IconName }) {
  return (
    <button {...rest} aria-label={label} title={label}
      className={`inline-flex h-11 w-11 items-center justify-center rounded-full text-ink2 transition hover:bg-line/60 active:bg-line ${className}`}>
      <Icon name={icon} />
    </button>
  );
}

/* ---------- Surfaces ---------- */
export function Card({ className = "", padded = true, children }: { className?: string; padded?: boolean; children: ReactNode }) {
  return <section className={`rounded-2xl border border-line/70 bg-card shadow-card ${padded ? "p-4" : ""} ${className}`}>{children}</section>;
}

export function Chip({ tone = "neutral", children }: { tone?: "neutral" | "brand" | "warn" | "danger"; children: ReactNode }) {
  const tones = {
    neutral: "bg-line/70 text-ink2", brand: "bg-brand-soft text-brand", warn: "bg-warn-soft text-warn", danger: "bg-danger-soft text-danger",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/* ---------- Segmented control ---------- */
export function Segmented<T extends string | number>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; label: string; options: { value: T; label: string; icon?: IconName }[];
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-xl bg-line/60 p-1">
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button key={String(o.value)} type="button" role="radio" aria-checked={on} onClick={() => onChange(o.value)}
            className={`flex min-h-[40px] flex-1 items-center justify-center gap-1.5 rounded-lg px-2 text-sm font-semibold transition ${on ? "bg-card text-ink shadow-sm" : "text-ink2 hover:text-ink"}`}>
            {o.icon && <Icon name={o.icon} className="h-4 w-4" />}{o.label}
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Bottom sheet ---------- */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const first = ref.current?.querySelector<HTMLElement>("textarea, input, button:not([data-sheet-close])");
    (first ?? ref.current)?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      prev?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <div className="absolute inset-0 animate-fade-in bg-black/40" onClick={onClose} aria-hidden />
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        className="pb-safe relative max-h-[88vh] w-full max-w-md animate-sheet-up overflow-y-auto rounded-t-3xl bg-card p-5 shadow-float outline-none sm:rounded-3xl">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-line sm:hidden" aria-hidden />
        <div className="mb-3 flex items-center justify-between">
          <h2 id={titleId} className="text-lg font-bold">{title}</h2>
          <IconButton data-sheet-close label="Close" icon="x" onClick={onClose} className="-mr-2" />
        </div>
        {children}
      </div>
    </div>
  );
}

/* ---------- Form field ---------- */
export const inputClass =
  "w-full min-h-[48px] rounded-xl border border-line bg-card px-3.5 text-base text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";

export function Field({ label, hint, error, suffix, children }: {
  label: string; hint?: string; error?: string; suffix?: string; children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold text-ink2">{label}</span>
      <span className="relative block">
        {children}
        {suffix && <span className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-sm text-muted">{suffix}</span>}
      </span>
      {error ? <span className="mt-1 block text-xs font-medium text-danger" role="alert">{error}</span>
        : hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}
