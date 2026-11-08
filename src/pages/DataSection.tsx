import { useEffect, useState } from "react";
import { HistoryStats, api, downloadCsv } from "../lib/api";
import { backupRange, formatDay } from "../lib/format";
import { useLogging } from "../logging";
import { Button, Card, Icon, Sheet, inputClass } from "../ui";

const WORD = "RESET";

/** "Your data": download everything, or permanently clear the meal history. */
export default function DataSection({ onCleared }: { onCleared: () => void }) {
  const { afterReset } = useLogging();
  const [open, setOpen] = useState(false);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState<"" | "backup" | "reset">("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open) return;
    setTyped(""); setErr(""); setStats(null);
    api<HistoryStats>("/api/history/stats").then(setStats).catch((e) => setErr((e as Error).message));
  }, [open]);

  const empty = stats !== null && stats.meals === 0;
  const range = stats && stats.first_date && stats.last_date ? backupRange(stats.first_date, stats.last_date) : null;

  async function backup() {
    if (!range) return;
    setBusy("backup"); setErr("");
    try { await downloadCsv(range.from, range.to); } catch (e) { setErr((e as Error).message); } finally { setBusy(""); }
  }

  async function reset() {
    setBusy("reset"); setErr("");
    try {
      await api("/api/history/reset", { method: "POST", body: JSON.stringify({ confirm: WORD }) });
      setOpen(false);
      await afterReset();
      onCleared();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(""); }
  }

  return (
    <>
      <Card className="space-y-3">
        <h2 className="text-sm font-bold text-ink2">Your data</h2>
        <p className="text-sm text-muted">Clear everything you've logged and start fresh. Your profile and targets stay.</p>
        <Button variant="danger" icon="trash" className="w-full" onClick={() => setOpen(true)}>Reset history…</Button>
      </Card>

      <Sheet open={open} onClose={() => !busy && setOpen(false)} title="Reset your history?">
        {err && <p role="alert" className="mb-3 rounded-xl bg-danger-soft p-3 text-sm font-medium text-danger">{err}</p>}
        {!stats && !err && <p className="animate-pulse text-sm text-muted">Checking your history…</p>}
        {empty && <p className="rounded-xl bg-brand-soft p-3 text-sm font-medium text-brand">You haven't logged anything yet, so there's nothing to reset.</p>}
        {stats && !empty && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-danger-soft p-4 text-sm text-ink">
              <p className="flex items-center gap-2 font-bold text-danger"><Icon name="alert" className="h-5 w-5" />This can't be undone</p>
              <p className="mt-2">
                This permanently deletes <b>{stats.meals} meal{stats.meals === 1 ? "" : "s"}</b> ({stats.items} food item{stats.items === 1 ? "" : "s"})
                {stats.first_date && stats.last_date && <> logged between <b>{formatDay(stats.first_date)}</b> and <b>{formatDay(stats.last_date)}</b></>}.
              </p>
              <p className="mt-2 text-ink2">Kept: your profile, targets and today's AI-log allowance.</p>
            </div>

            <Button variant="secondary" icon="download" className="w-full" loading={busy === "backup"} onClick={backup}>Download a CSV backup first</Button>
            {range?.clamped && <p className="-mt-2 text-xs text-muted">Your history is longer than a year, so the backup covers the most recent 12 months.</p>}

            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-ink2">Type <b className="text-danger">{WORD}</b> to confirm</span>
              <input value={typed} onChange={(e) => setTyped(e.target.value)} className={inputClass} autoCapitalize="characters"
                autoComplete="off" autoCorrect="off" spellCheck={false} aria-label={`Type ${WORD} to confirm`} />
            </label>
            <Button variant="danger" icon="trash" className="w-full" disabled={typed !== WORD} loading={busy === "reset"} onClick={reset}>
              Delete all history
            </Button>
          </div>
        )}
      </Sheet>
    </>
  );
}
