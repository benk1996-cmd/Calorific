import { FormEvent, useState } from "react";
import { loginError } from "../lib/errors";
import { supabase } from "../lib/supabase";
import { Button, Icon, inputClass } from "../ui";

export default function Login() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setState("sending");
    // shouldCreateUser:false => invite-only; unknown emails are rejected by Supabase
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(), options: { shouldCreateUser: false, emailRedirectTo: window.location.origin },
    });
    if (error) { setError(loginError(error.message)); setState("error"); } else setState("sent");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-10">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand text-brand-ink shadow-float"><Icon name="leaf" className="h-8 w-8" /></div>
        <h1 className="text-3xl font-extrabold tracking-tight">Calorific</h1>
        <p className="mt-1.5 text-muted">Snap a meal. Know your numbers.</p>
      </div>

      {state === "sent" ? (
        <div className="animate-fade-in rounded-2xl border border-line bg-card p-6 text-center shadow-card" role="status">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-soft text-brand"><Icon name="mail" className="h-6 w-6" /></div>
          <h2 className="text-lg font-bold">Check your inbox</h2>
          <p className="mt-1 text-sm text-ink2">We sent a sign-in link to <b className="break-all">{email.trim()}</b>.</p>
          <p className="mt-3 text-xs text-muted">The link works once and expires in about an hour. Open it on this device. If it doesn't arrive, check spam and wait a few minutes before asking for another.</p>
          <button className="mt-4 min-h-[44px] text-sm font-semibold text-brand" onClick={() => setState("idle")}>Use a different email</button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-line bg-card p-5 shadow-card" noValidate>
          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-ink2">Email</span>
            <input type="email" required autoComplete="email" inputMode="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com" className={inputClass} aria-invalid={state === "error"} />
          </label>
          <Button type="submit" className="w-full" loading={state === "sending"} disabled={!email.includes("@")}>Email me a sign-in link</Button>
          {state === "error" && <p role="alert" className="rounded-xl bg-danger-soft p-3 text-sm font-medium text-danger">{error}</p>}
          <p className="text-center text-xs text-muted">Invite-only. No password needed.</p>
        </form>
      )}
    </main>
  );
}
