import { FormEvent, ReactNode, useState } from "react";
import { FoodSearch } from "./components";
import { UNDO_SECONDS, useLogging } from "./logging";
import { needsCheck, roundKcal } from "./lib/format";
import { Button, Icon, IconName, Sheet, inputClass } from "./ui";

export type Tab = "today" | "history" | "profile";

/* ---------- Page header with profile avatar ---------- */
export function PageHeader({ eyebrow, title, name, onProfile }: { eyebrow?: string; title: string; name?: string | null; onProfile: () => void }) {
  return (
    <header className="pt-safe flex items-start justify-between gap-3 px-5 pb-3 pt-5">
      <div className="min-w-0">
        {eyebrow && <p className="text-[13px] font-medium text-muted">{eyebrow}</p>}
        <h1 className="line-clamp-2 text-2xl font-bold leading-tight tracking-tight">{title}</h1>
      </div>
      <button onClick={onProfile} aria-label="Profile and settings"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-soft text-base font-bold text-brand transition active:scale-95">
        {(name?.trim()[0] ?? "").toUpperCase() || <Icon name="user" />}
      </button>
    </header>
  );
}

/* ---------- Bottom navigation with a raised Add button ---------- */
export function BottomNav({ tab, onTab, onAdd }: { tab: Tab; onTab: (t: Tab) => void; onAdd: () => void }) {
  const item = (t: Tab, icon: IconName, label: string) => (
    <button onClick={() => onTab(t)} aria-current={tab === t ? "page" : undefined}
      className={`flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-semibold transition ${tab === t ? "text-brand" : "text-muted hover:text-ink2"}`}>
      <Icon name={icon} className="h-6 w-6" />{label}
    </button>
  );
  return (
    <nav aria-label="Main" className="pb-safe fixed inset-x-0 bottom-0 z-40 border-t border-line/80 bg-card/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-md items-end px-6">
        {item("today", "home", "Today")}
        <div className="flex flex-1 justify-center">
          <button onClick={onAdd} aria-label="Add a meal"
            className="-mt-5 flex h-14 w-14 items-center justify-center rounded-full bg-brand text-brand-ink shadow-float ring-4 ring-bg transition active:scale-95">
            <Icon name="plus" className="h-7 w-7" />
          </button>
        </div>
        {item("history", "chart", "History")}
      </div>
    </nav>
  );
}

/* ---------- Add sheet: the four ways to log ---------- */
function Row({ icon, title, sub, onClick, disabled }: { icon: IconName; title: string; sub: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="flex min-h-[64px] w-full items-center gap-4 rounded-2xl border border-line bg-card p-3 text-left transition enabled:active:bg-line/50 disabled:opacity-45">
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand"><Icon name={icon} className="h-6 w-6" /></span>
      <span className="min-w-0 flex-1"><span className="block font-semibold">{title}</span><span className="block text-sm text-muted">{sub}</span></span>
      <Icon name="chevron" className="h-5 w-5 text-muted" />
    </button>
  );
}

const EXAMPLES = ["1 plate chicken rice, less rice", "kopi-o kosong + 2 slices kaya toast", "2 roti prata + teh tarik"];

export function AddFlow({ sheet, setSheet }: { sheet: null | "add" | "text" | "search"; setSheet: (s: null | "add" | "text" | "search") => void }) {
  const L = useLogging();
  const [text, setText] = useState("");
  const close = () => setSheet(null);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (t.length < 2) return;
    close(); setText(""); void L.logText(t);
  };
  return (
    <>
      <Sheet open={sheet === "add"} onClose={close} title="Add a meal">
        {L.limitReached && (
          <p className="mb-3 rounded-xl bg-warn-soft p-3 text-sm font-medium text-warn" role="status">
            Daily AI limit reached. You can still search and add food manually.
          </p>
        )}
        <div className="space-y-2.5">
          <Row icon="camera" title="Take a photo" sub="Snap it, AI does the rest" disabled={L.limitReached}
            onClick={() => { L.openCamera(); close(); }} />
          <Row icon="image" title="Choose from gallery" sub="Use a photo you already took" disabled={L.limitReached}
            onClick={() => { L.openUpload(); close(); }} />
          <Row icon="pen" title="Describe it" sub="Type what you ate" disabled={L.limitReached} onClick={() => setSheet("text")} />
          <Row icon="search" title="Search foods" sub="No AI needed" onClick={() => setSheet("search")} />
        </div>
        {L.usage && <p className="mt-4 text-center text-xs text-muted">AI logs left today: <b className="text-ink2">{L.usage.remaining}</b> of {L.usage.user_limit}</p>}
      </Sheet>

      <Sheet open={sheet === "text"} onClose={close} title="Describe your meal">
        <form onSubmit={submit} className="space-y-3">
          <textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} rows={3} required
            placeholder="e.g. 1 plate chicken rice, less rice" aria-label="What did you eat?" className={`${inputClass} resize-none py-3`}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e as unknown as FormEvent); }} />
          <div className="flex flex-wrap gap-2" aria-label="Examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" onClick={() => setText(ex)}
                className="rounded-full border border-line bg-bg px-3 py-1.5 text-xs font-medium text-ink2 transition active:bg-line">{ex}</button>
            ))}
          </div>
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Quantities, “less rice”, “no sugar” and drink codes like kopi-o kosong are understood.</span>
            <span className="num shrink-0 pl-2">{text.length}/300</span>
          </div>
          <Button type="submit" className="w-full" icon="sparkle" disabled={text.trim().length < 2}>Log meal</Button>
        </form>
      </Sheet>

      <Sheet open={sheet === "search"} onClose={close} title="Search foods">
        <FoodSearch onPick={(f) => { close(); void L.addFood(f); }} />
      </Sheet>
    </>
  );
}

/* ---------- Progress banner while the AI works (always in view, unlike an inline card) ---------- */
export function AnalyzingBanner() {
  const { analyzing } = useLogging();
  if (!analyzing) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-[76px] z-40 px-4">
      <div role="status" aria-live="polite"
        className="pointer-events-auto relative mx-auto flex max-w-md animate-toast-in items-center gap-3 overflow-hidden rounded-2xl border border-line bg-card p-3.5 shadow-float">
        {analyzing.preview
          ? <img src={analyzing.preview} alt="Your meal" className="h-12 w-12 shrink-0 rounded-xl object-cover" />
          : <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand"><Icon name="sparkle" className="h-6 w-6" /></span>}
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{analyzing.label}</p>
          <p className="text-xs text-muted">Usually just a few seconds.</p>
        </div>
        <div className="skeleton absolute inset-x-0 bottom-0 h-1 rounded-none bg-brand/30" aria-hidden />
      </div>
    </div>
  );
}

/* ---------- Undo toast shown after a meal is logged ---------- */
export function ResultToast({ onEdit }: { onEdit: (id: string) => void }) {
  const { result, undoLeft, undo, dismissResult } = useLogging();
  if (!result) return null;
  const total = result.items.reduce((s, i) => s + i.kcal, 0);
  const names = result.items.map((i) => i.name);
  const check = result.items.filter(needsCheck).length;
  return (
    <div className="pb-safe pointer-events-none fixed inset-x-0 bottom-[76px] z-40 px-4">
      <div role="status" className="pointer-events-auto relative mx-auto max-w-md animate-toast-in overflow-hidden rounded-2xl bg-ink p-4 text-bg shadow-float">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand text-brand-ink"><Icon name="check" className="h-5 w-5" /></span>
          <div className="min-w-0 flex-1">
            <p className="font-bold">Logged <span className="num">{roundKcal(total)}</span> kcal</p>
            <p className="truncate text-sm opacity-80">{names.slice(0, 2).join(", ")}{names.length > 2 ? ` +${names.length - 2} more` : ""}</p>
            {check > 0 && <p className="mt-1 text-xs font-medium text-warn-soft">⚠ {check === 1 ? "1 item is an estimate" : `${check} items are estimates`}. Tap Edit to check.</p>}
          </div>
          <button onClick={dismissResult} aria-label="Dismiss" className="-mr-1 -mt-1 flex h-9 w-9 items-center justify-center rounded-full opacity-70"><Icon name="x" className="h-4 w-4" /></button>
        </div>
        <div className="mt-3 flex gap-2">
          <button onClick={() => onEdit(result.id)} className="min-h-[40px] flex-1 rounded-lg bg-bg/15 text-sm font-semibold">Edit</button>
          <button onClick={() => void undo()} className="min-h-[40px] flex-1 rounded-lg bg-bg/15 text-sm font-semibold">Undo <span className="num opacity-70">({undoLeft}s)</span></button>
        </div>
        <div key={result.id} className="absolute inset-x-0 bottom-0 h-1 origin-left animate-shrink bg-brand" style={{ animationDuration: `${UNDO_SECONDS}s` }} aria-hidden />
      </div>
    </div>
  );
}

export function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto min-h-screen max-w-md pb-40">{children}</div>;
}
