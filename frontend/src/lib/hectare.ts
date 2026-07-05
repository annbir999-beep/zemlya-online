// Регионы федеральных программ «бесплатного гектара».
// Источник: backend/services/regional_programs.py (ФЗ-119, ФЗ-247).
// 14 (Якутия) и 87 (Чукотка) участвуют в обеих программах.

export const DV_HECTARE_REGIONS = new Set([
  "03", "14", "25", "27", "28", "41", "49", "65", "75", "79", "87",
]);

export const ARCTIC_HECTARE_REGIONS = new Set([
  "10", "11", "14", "24", "29", "51", "83", "86", "87", "89",
]);

export type HectareProgram = "dv" | "arctic" | "both";

export function hectareProgram(regionCode?: string | null): HectareProgram | null {
  if (!regionCode) return null;
  const dv = DV_HECTARE_REGIONS.has(regionCode);
  const ar = ARCTIC_HECTARE_REGIONS.has(regionCode);
  if (dv && ar) return "both";
  if (dv) return "dv";
  if (ar) return "arctic";
  return null;
}

export const HECTARE_LABEL: Record<HectareProgram, string> = {
  dv: "ДВ-гектар",
  arctic: "Аркт. гектар",
  both: "ДВ + Аркт. гектар",
};

export const HECTARE_TITLE: Record<HectareProgram, string> = {
  dv: "Регион программы «Дальневосточный гектар» (ФЗ-119): до 1 га бесплатно каждому гражданину РФ",
  arctic: "Регион программы «Арктический гектар» (ФЗ-247): до 1 га бесплатно каждому гражданину РФ",
  both: "Регион программ «Дальневосточный гектар» (ФЗ-119) и «Арктический гектар» (ФЗ-247)",
};
