import { useEffect } from "react";

export default function usePageTitle(title) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} — PrivaLens DataRescue` : "PrivaLens DataRescue";
    return () => {
      document.title = previous;
    };
  }, [title]);
}
