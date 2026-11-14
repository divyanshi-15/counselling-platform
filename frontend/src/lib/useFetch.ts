import { useEffect, useState } from "react";
import { api } from "./api";

export function useFetch<T>(path: string, params?: Record<string, string | number | undefined>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const key = path + JSON.stringify(params ?? {}) + tick;
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    api<T>(path, { params })
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data, error, loading, reload: () => setTick((t) => t + 1) };
}
