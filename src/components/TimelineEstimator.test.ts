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
});
