// Shared media-query hook -- previously duplicated as a private useIsMobile
// inside AppLayout.tsx; pulled out so every screen doing its own tablet/
// mobile responsive work (SCREENLIST.md cross-cutting #4) shares one
// subscription pattern instead of copy-pasting matchMedia wiring per file.

import { useEffect, useState } from "react";

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);
  return matches;
}
