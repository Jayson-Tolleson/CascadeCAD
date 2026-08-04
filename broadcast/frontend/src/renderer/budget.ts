export type BudgetTier = 'global' | 'regional' | 'local';

export interface RenderBudget { tier: BudgetTier; clouds: number; rain: number; ocean: number; bait: number; boats: number; lightning: number; inlandWater: number; reports: number; }

export function budgetForTier(tier: BudgetTier): RenderBudget {
  if (tier === 'local') return { tier, clouds: 56, rain: 72, ocean: 64, bait: 40, boats: 24, lightning: 50, inlandWater: 120, reports: 40 };
  if (tier === 'regional') return { tier, clouds: 32, rain: 40, ocean: 36, bait: 24, boats: 12, lightning: 24, inlandWater: 60, reports: 24 };
  return { tier, clouds: 16, rain: 20, ocean: 18, bait: 12, boats: 6, lightning: 12, inlandWater: 20, reports: 12 };
}
