import { describe, it, expect } from 'vitest';
import { computeTimeline } from './TimelineEstimator';

describe('computeTimeline', () => {
  const cross = computeTimeline(3, 50, 100, 30, 4, 'azure-aws');

  it('returns the seven migration phases', () => {
    expect(cross.phases.length).toBe(7);
  });

  it('totalWeeks equals the sum of phase weeks', () => {
    expect(cross.totalWeeks).toBe(cross.phases.reduce((s, p) => s + p.weeks, 0));
  });

  it('cross-cloud foundation is longer than same-cloud foundation', () => {
    const same = computeTimeline(3, 50, 100, 30, 4, 'same-cloud');
    expect(same.phases[1].weeks).toBeLessThan(cross.phases[1].weeks);
  });

  it('hypercare is fixed at two weeks', () => {
    expect(cross.phases[6].weeks).toBe(2);
  });

  it('AI-accelerated totals less than traditional for the same inputs', () => {
    const traditional = computeTimeline(5, 100, 400, 60, 6, 'azure-aws', false, 50);
    const accelerated = computeTimeline(5, 100, 400, 60, 6, 'azure-aws', true, 50);
    expect(accelerated.totalWeeks).toBeLessThan(traditional.totalWeeks);
  });

  it('a bigger team compresses the total, with diminishing returns', () => {
    const small = computeTimeline(5, 100, 400, 60, 2, 'azure-aws', true, 50);
    const mid = computeTimeline(5, 100, 400, 60, 6, 'azure-aws', true, 50);
    const big = computeTimeline(5, 100, 400, 60, 15, 'azure-aws', true, 50);
    expect(mid.totalWeeks).toBeLessThan(small.totalWeeks);
    expect(big.totalWeeks).toBeLessThan(mid.totalWeeks);
    // Diminishing returns: the 2->6 jump saves more than the 6->15 jump per person added.
    const firstJumpSavings = (small.totalWeeks - mid.totalWeeks) / 4;
    const secondJumpSavings = (mid.totalWeeks - big.totalWeeks) / 9;
    expect(firstJumpSavings).toBeGreaterThan(secondJumpSavings);
  });

  it('more data volume extends the migration phase', () => {
    const lean = computeTimeline(5, 100, 400, 60, 6, 'azure-aws', true, 1);
    const heavy = computeTimeline(5, 100, 400, 60, 6, 'azure-aws', true, 800);
    expect(heavy.phases[2].weeks).toBeGreaterThan(lean.phases[2].weeks);
  });
});
