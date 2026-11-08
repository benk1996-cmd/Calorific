import { ReactNode, createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AnalyzeResponse, FoodResult, Meal, Profile, Summary, Usage, api } from "./lib/api";
import { todayInTz } from "./lib/format";
import { resizeToJpeg } from "./lib/image";

export const UNDO_SECONDS = 10;
export interface Notice { kind: "error" | "info"; text: string }

interface Ctx {
  profile: Profile;
  day: string;
  summary: Summary | null;
  usage: Usage | null;
  loading: boolean;
  limitReached: boolean;
  analyzing: { label: string; preview: string | null } | null;
  notice: Notice | null;
  clearNotice: () => void;
  result: Meal | null;
  undoLeft: number;
  dismissResult: () => void;
  undo: () => Promise<void>;
  editingId: string | null;
  edit: (id: string | null) => void;
  setSummary: (s: Summary) => void;
  refresh: () => Promise<void>;
  openCamera: () => void;
  openUpload: () => void;
  logText: (text: string) => Promise<void>;
  addFood: (f: FoodResult) => Promise<void>;
}

const LoggingContext = createContext<Ctx | null>(null);
export function useLogging(): Ctx {
  const c = useContext(LoggingContext);
  if (!c) throw new Error("useLogging must be used inside <LoggingProvider>");
  return c;
}

/** Owns today's data and every "log a meal" flow, so any screen (or the Add sheet) can start one. */
export function LoggingProvider({ profile, onLogging, children }: { profile: Profile; onLogging: () => void; children: ReactNode }) {
  const [day, setDay] = useState(() => todayInTz(profile.timezone));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState<Ctx["analyzing"]>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [result, setResult] = useState<Meal | null>(null);
  const [undoLeft, setUndoLeft] = useState(0);
  const [editingId, setEditingId] = useState<string | null>(null);
  const scrollBeforeEdit = useRef(0);
  const camera = useRef<HTMLInputElement>(null);
  const upload = useRef<HTMLInputElement>(null);

  useEffect(() => { setDay(todayInTz(profile.timezone)); }, [profile.timezone]);

  /** Open/close the meal editor, returning to the same scroll position on close. */
  const edit = useCallback((id: string | null) => {
    if (id) scrollBeforeEdit.current = window.scrollY;
    else { const y = scrollBeforeEdit.current; requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, y))); }
    setEditingId(id);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [s, u] = await Promise.all([api<Summary>(`/api/days/${day}/summary`), api<Usage>("/api/usage")]);
      setSummary(s); setUsage(u);
    } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); }
    finally { setLoading(false); }
  }, [day]);
  useEffect(() => { void refresh(); }, [refresh]);

  // Day rollover (midnight in the user's timezone) and refresh when the app regains focus.
  useEffect(() => {
    const check = () => {
      const today = todayInTz(profile.timezone);
      if (today !== day) setDay(today); else if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", check);
    const t = setInterval(() => { const today = todayInTz(profile.timezone); if (today !== day) setDay(today); }, 60_000);
    return () => { document.removeEventListener("visibilitychange", check); clearInterval(t); };
  }, [day, profile.timezone, refresh]);

  useEffect(() => {
    if (undoLeft <= 0) { if (result) setResult(null); return; }
    const t = setTimeout(() => setUndoLeft((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [undoLeft, result]);

  const finish = useCallback((r: AnalyzeResponse) => {
    setUsage(r.usage);
    setSummary(r.summary);
    if (r.not_food || !r.meal) {
      setNotice({ kind: "info", text: "That doesn't look like food. Try another photo, or describe it instead." });
    } else {
      setResult(r.meal); setUndoLeft(UNDO_SECONDS);
    }
  }, []);

  async function run(label: string, preview: string | null, fn: () => Promise<AnalyzeResponse>) {
    setNotice(null); setResult(null); setUndoLeft(0); setAnalyzing({ label, preview });
    onLogging();
    window.scrollTo({ top: 0, behavior: "smooth" }); // keep the ring and progress banner in view
    try { finish(await fn()); }
    catch (e) { setNotice({ kind: "error", text: (e as Error).message }); void refresh(); }
    finally { setAnalyzing(null); if (preview) URL.revokeObjectURL(preview); }
  }

  const onFile = (file?: File) => {
    if (!file) return;
    void run("Analysing your meal…", URL.createObjectURL(file), async () => {
      const fd = new FormData();
      fd.append("image", await resizeToJpeg(file), "meal.jpg");
      return api<AnalyzeResponse>("/api/analyze/photo", { method: "POST", body: fd });
    });
  };

  const ctx: Ctx = {
    profile, day, summary, usage, loading, analyzing, notice, result, undoLeft, editingId, refresh,
    limitReached: usage !== null && usage.remaining <= 0,
    clearNotice: () => setNotice(null),
    dismissResult: () => { setResult(null); setUndoLeft(0); },
    edit,
    setSummary,
    openCamera: () => camera.current?.click(),
    openUpload: () => upload.current?.click(),
    logText: (text) => run("Reading your description…", null, () =>
      api<AnalyzeResponse>("/api/analyze/text", { method: "POST", body: JSON.stringify({ text }) })),
    addFood: async (f) => {
      setNotice(null);
      try {
        const r = await api<{ meal: Meal; summary: Summary }>("/api/meals/manual", { method: "POST", body: JSON.stringify({ food_ref_id: f.id }) });
        setSummary(r.summary); edit(r.meal.id); // open the editor so the portion can be set
      } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); }
    },
    undo: async () => {
      if (!result) return;
      try {
        const r = await api<{ summary: Summary }>(`/api/meals/${result.id}`, { method: "DELETE" });
        setSummary(r.summary); setResult(null); setUndoLeft(0);
        setNotice({ kind: "info", text: "Meal removed." });
      } catch (e) { setNotice({ kind: "error", text: (e as Error).message }); }
    },
  };

  return (
    <LoggingContext.Provider value={ctx}>
      {/* Hidden inputs live here so a tap anywhere can open the camera/gallery within the user gesture. */}
      <input ref={camera} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      <input ref={upload} type="file" accept="image/*" hidden
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      {children}
    </LoggingContext.Provider>
  );
}
