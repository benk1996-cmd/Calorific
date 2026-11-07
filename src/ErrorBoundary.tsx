import { Component, ReactNode } from "react";

/** Last-resort screen so a rendering bug never leaves a blank page. */
export default class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error) { console.error("UI error:", error.message); }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="mx-auto max-w-md p-6">
        <p className="font-semibold">Something went wrong.</p>
        <p className="mt-1 text-sm text-gray-600">Your logged meals are safe. Reload to continue.</p>
        <button className="mt-3 rounded bg-green-600 px-4 py-2 text-white" onClick={() => window.location.reload()}>Reload</button>
      </main>
    );
  }
}
