// Ранжирование тарифов для гейтинга премиум-блоков.
// Ключи = enum value в БД (SubscriptionPlan): free/personal/investor/expert/landlord/enterprise.
// Публичные имена: personal=Pro, investor=Инвестор, expert=Бюро, landlord=Бюро+.
export const PLAN_RANK: Record<string, number> = {
  free: 0,
  personal: 1, // Pro
  investor: 2, // Инвестор
  expert: 3, // Бюро
  landlord: 4, // Бюро+
  enterprise: 5,
};

export function planRank(plan?: string | null): number {
  return PLAN_RANK[plan ?? "free"] ?? 0;
}

// Пороги для гейтинга блоков лота.
export const RANK_PRO = PLAN_RANK.personal; // 1
export const RANK_INVESTOR = PLAN_RANK.investor; // 2
