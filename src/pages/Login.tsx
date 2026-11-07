import { FormEvent, useState } from "react";
import { supabase } from "../lib/supabase";

export default function Login() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setState("sending");
    // shouldCreateUser:false => invite-only; unknown emails are rejected by Supabase
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false, emailRedirectTo: window.location.origin },
    });
    if (error) {
      setError(error.message);
      setState("error");
    } else setState("sent");
  }

  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold text-green-700">Calorific</h1>
      <p className="mt-1 text-sm text-gray-600">Invite-only. Sign in with a magic link.</p>
      {state === "sent" ? (
        <p className="mt-6 rounded bg-green-50 p-3 text-green-800">Check your email for the sign-in link.</p>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-3">
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com" className="w-full rounded border p-3" />
          <button disabled={state === "sending"} className="w-full rounded bg-green-600 p-3 font-medium text-white disabled:opacity-60">
            {state === "sending" ? "Sending…" : "Email me a link"}
          </button>
          {state === "error" && <p className="text-sm text-red-600">{error}</p>}
        </form>
      )}
    </main>
  );
}
