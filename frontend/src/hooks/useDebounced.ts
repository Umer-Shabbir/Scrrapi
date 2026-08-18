// Trailing debounce for search-as-you-type inputs.
//
// The geo pickers query the server on every keystroke, against tables holding
// ~1.1M cities. Without this, typing "birmingham" is ten queries of which nine
// are already stale by the time they land.

import { useEffect, useState } from "react";

export function useDebounced<T>(value: T, delayMs = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
