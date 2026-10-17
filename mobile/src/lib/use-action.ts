import { useCallback, useState } from 'react';

/** Runs one async action at a time and exposes busy/error state for the UI. */
export function useAction() {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const run = useCallback(async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  }, []);

  return { busy, error, run, clearError: () => setError(null) };
}
