import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { Profile, api } from "./lib/api";
import { supabase } from "./lib/supabase";
import Login from "./pages/Login";
import ProfileForm from "./pages/ProfileForm";

export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => data.subscription.unsubscribe();
  }, []);

  const load = useCallback(async () => {
    try {
      setProfile((await api<{ profile: Profile | null }>("/api/profile")).profile);
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { if (session) load(); else setProfile(undefined); }, [session, load]);

  if (session === undefined) return <p className="p-6">Loading…</p>;
  if (!session) return <Login />;
  if (error) return (
    <main className="p-6"><p className="text-red-600">{error}</p>
      <button className="mt-3 underline" onClick={() => supabase.auth.signOut()}>Sign out</button></main>
  );
  if (profile === undefined) return <p className="p-6">Loading…</p>;
  if (profile === null) return <ProfileForm initial={null} onboarding onSaved={setProfile} />;
  if (editing) return <ProfileForm initial={profile} onSaved={(p) => { setProfile(p); setEditing(false); }} />;

  // Placeholder home until M4 (Today dashboard)
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold text-green-700">Calorific</h1>
      <p className="mt-4">Daily target: <b>{profile.target_kcal} kcal</b></p>
      <p className="text-sm text-gray-600">
        P {profile.target_protein_g}g · C {profile.target_carbs_g}g · F {profile.target_fat_g}g
      </p>
      <div className="mt-6 space-x-4 text-sm">
        <button className="underline" onClick={() => setEditing(true)}>Edit profile</button>
        <button className="underline" onClick={() => supabase.auth.signOut()}>Sign out</button>
      </div>
    </main>
  );
}
