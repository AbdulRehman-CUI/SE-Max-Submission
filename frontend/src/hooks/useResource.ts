import { useCallback, useEffect, useState } from "react";
import { message } from "../lib/format";
export function useResource<T>(load: () => Promise<T>) {
  const [state, setState] = useState<{
    data?: T;
    error?: string;
    loading: boolean;
  }>({ loading: true });
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setState({ loading: true });
    load().then(
      (data) => {
        if (active) setState({ data, loading: false });
      },
      (error) => {
        if (active) setState({ error: message(error), loading: false });
      },
    );
    return () => {
      active = false;
    };
  }, [load, version]);
  return {
    ...state,
    reload: useCallback(() => setVersion((value) => value + 1), []),
  };
}
