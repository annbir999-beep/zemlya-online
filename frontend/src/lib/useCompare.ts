"use client";
import { useEffect, useState } from "react";
import { compare } from "./compare";

export function useCompareIds(): number[] {
  const [ids, setIds] = useState<number[]>([]);

  useEffect(() => {
    setIds(compare.get());
    const refresh = () => setIds(compare.get());
    const unsub = compare.subscribe(refresh);
    window.addEventListener("storage", refresh);
    window.addEventListener("compare-changed", refresh);
    return () => {
      unsub();
      window.removeEventListener("storage", refresh);
      window.removeEventListener("compare-changed", refresh);
    };
  }, []);

  return ids;
}
