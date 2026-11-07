import { useEffect, useState } from "react";

export default function App() {
  const [status, setStatus] = useState("checking…");
  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus("unreachable"));
  }, []);
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold text-green-700">Calorific</h1>
      <p className="mt-2 text-sm text-gray-600">API: {status}</p>
    </main>
  );
}
