import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { Profile, api } from "./lib/api";
import { LoggingProvider, useLogging } from "./logging";
import EditMeal from "./pages/EditMeal";
import History from "./pages/History";
import Login from "./pages/Login";
import ProfileForm from "./pages/ProfileForm";
import Today from "./pages/Today";
import { AddFlow, AnalyzingBanner, BottomNav, Page, PageHeader, ResultToast, Tab } from "./shell";
import { supabase } from "./lib/supabase";
import { Button, Skeleton } from "./ui";

function Shell({ profile, onSaved, tab, setTab }: { profile: Profile; onSaved: (p: Profile) => void; tab: Tab; setTab: (t: Tab) => void }) {
  const L = useLogging();
  const [sheet, setSheet] = useState<null | "add" | "text" | "search">(null);

  if (L.editingId) return <EditMeal />;
  const signOut = () => void supabase.auth.signOut();

  return (
    <>
      <Page>
        {tab === "today" && <Today onProfile={() => setTab("profile")} onAdd={() => setSheet("add")} onEdit={L.edit} />}
        {tab === "history" && <History profile={profile} onProfile={() => setTab("profile")} />}
        {tab === "profile" && (
          <>
            <PageHeader title="Settings" eyebrow={profile.display_name ?? undefined} name={profile.display_name} onProfile={() => setTab("today")} />
            <ProfileForm initial={profile} onSaved={(p) => { onSaved(p); setTab("today"); }} onSignOut={signOut} />
          </>
        )}
      </Page>
      <AnalyzingBanner />
      <ResultToast onEdit={L.edit} />
      <BottomNav tab={tab} onTab={setTab} onAdd={() => setSheet("add")} />
      <AddFlow sheet={sheet} setSheet={setSheet} />
    </>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [tab, setTab] = useState<Tab>("today");
  const [error, setError] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  const load = useCallback(async () => {
    setError("");
    try { setProfile((await api<{ profile: Profile | null }>("/api/profile")).profile); }
    catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { if (session) void load(); else { setProfile(undefined); setTab("today"); } }, [session, load]);

  if (session === undefined) return <div className="mx-auto max-w-md space-y-4 p-6"><Skeleton className="h-10 w-40" /><Skeleton className="h-48" /></div>;
  if (!session) return <Login />;
  if (error) return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-3 p-6 text-center">
      <p role="alert" className="rounded-2xl bg-danger-soft p-4 font-medium text-danger">{error}</p>
      <Button onClick={() => void load()}>Try again</Button>
      <Button variant="ghost" onClick={() => void supabase.auth.signOut()}>Sign out</Button>
    </main>
  );
  if (profile === undefined) return <div className="mx-auto max-w-md space-y-4 p-6"><Skeleton className="h-10 w-40" /><Skeleton className="h-48" /><Skeleton className="h-32" /></div>;
  if (profile === null) return <ProfileForm initial={null} onboarding onSaved={setProfile} />;

  return (
    <LoggingProvider profile={profile} onLogging={() => setTab("today")}>
      <Shell profile={profile} onSaved={setProfile} tab={tab} setTab={setTab} />
    </LoggingProvider>
  );
}
