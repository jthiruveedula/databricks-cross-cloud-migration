import { describe, it, expect } from 'vitest';
import {
  computeTimeline,
  effectiveWorkers,
  transferHours,
  WORKER_SATURATION_CEILING,
  TRANSFER_OVERHEAD_FACTOR,
} from './TimelineEstimator';

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

// ---------------------------------------------------------------------------
// Scale model. Everything above exercises the pre-scale call signature and must
// keep passing unchanged -- omitting the scale argument disables the physical
// model and falls back to the original volume heuristic.
// ---------------------------------------------------------------------------

const LARGE = {
  tableCount: 50000,
  catalogCount: 25,
  parallelWorkers: 16,
  throughputGbps: 10,
  tablesPerWave: 2500,
} as const;

const large = (over: Partial<typeof LARGE> = {}, accelerated = true) =>
  computeTimeline(12, 1200, 6000, 4000, 12, 'azure-aws', accelerated, 900, { ...LARGE, ...over });

describe('scale model', () => {
  it('is inert unless a table count is supplied', () => {
    const withoutScale = computeTimeline(3, 50, 100, 30, 4, 'azure-aws', true, 25);
    const withZero = computeTimeline(3, 50, 100, 30, 4, 'azure-aws', true, 25, { tableCount: 0 });
    expect(withoutScale.scale).toBeNull();
    expect(withZero.scale).toBeNull();
    expect(withZero.totalWeeks).toBe(withoutScale.totalWeeks);
  });

  it('reports a breakdown once a table count is supplied', () => {
    const s = large().scale!;
    expect(s).not.toBeNull();
    expect(s.waves).toBe(20); // 50,000 / 2,500
    expect(s.tablesPerHour).toBeGreaterThan(0);
  });

  it('50k tables takes materially longer than 5k, all else equal', () => {
    expect(large({ tableCount: 50000 }).totalWeeks).toBeGreaterThan(
      large({ tableCount: 5000 }).totalWeeks,
    );
  });

  it('worker concurrency saturates instead of scaling linearly', () => {
    // Below the ceiling, extra workers are nearly linear.
    expect(effectiveWorkers(4)).toBeGreaterThan(3.5);
    // Far above it, they are not: 128 requested buys under 32 effective.
    expect(effectiveWorkers(128)).toBeLessThan(WORKER_SATURATION_CEILING);
    expect(effectiveWorkers(128)).toBeGreaterThan(effectiveWorkers(64));
    // Doubling well past the ceiling buys less than 20% more throughput.
    expect(effectiveWorkers(256) / effectiveWorkers(128)).toBeLessThan(1.2);
  });

  it('more workers shorten an object-bound migration, with diminishing returns', () => {
    const few = large({ parallelWorkers: 2 });
    const some = large({ parallelWorkers: 16 });
    const many = large({ parallelWorkers: 128 });
    expect(some.scale!.objectBoundWeeks).toBeLessThan(few.scale!.objectBoundWeeks);
    expect(many.scale!.objectBoundWeeks).toBeLessThan(some.scale!.objectBoundWeeks);
    const firstGain = few.scale!.objectBoundWeeks - some.scale!.objectBoundWeeks;
    const secondGain = some.scale!.objectBoundWeeks - many.scale!.objectBoundWeeks;
    expect(firstGain).toBeGreaterThan(secondGain);
  });

  it('team size does not shorten the object-bound term -- only the code-bound one', () => {
    const small = large();
    const big = computeTimeline(12, 1200, 6000, 4000, 40, 'azure-aws', true, 900, LARGE);
    expect(big.scale!.objectBoundWeeks).toBe(small.scale!.objectBoundWeeks);
    expect(big.scale!.codeBoundWeeks).toBeLessThan(small.scale!.codeBoundWeeks);
  });

  it('matches the transfer formula published in the runbook', () => {
    // (TB * 8 * 1024 * overhead) / (Gbps * 3600) -- large-scale-data-transfer.mdx
    const expected = (480 * 8 * 1024 * TRANSFER_OVERHEAD_FACTOR) / (8 * 3600);
    expect(transferHours(480, 8)).toBeCloseTo(expected, 6);
    expect(Math.round(transferHours(480, 8))).toBe(184);
  });

  it('narrow waves cost calendar time even when the data is identical', () => {
    const wide = large({ tablesPerWave: 10000 });
    const narrow = large({ tablesPerWave: 1000 });
    expect(narrow.scale!.waves).toBeGreaterThan(wide.scale!.waves);
    expect(narrow.scale!.waveOverheadWeeks).toBeGreaterThan(wide.scale!.waveOverheadWeeks);
    expect(narrow.totalWeeks).toBeGreaterThan(wide.totalWeeks);
  });

  it('names bandwidth as the constraint when the pipe is the slow part', () => {
    expect(large({ throughputGbps: 1, tableCount: 2000 }).scale!.bottleneck).toBe('bytes');
  });

  it('4000 jobs do not cost 4000 units of work -- only the non-mechanical ones do', () => {
    const s = large().scale!;
    expect(s.manualJobs).toBeLessThan(4000 * 0.2);
    // ...and an unaccelerated run leaves materially more of them to hand-map.
    expect(large({}, false).scale!.manualJobs).toBeGreaterThan(s.manualJobs);
  });

  it('accelerators still beat a hand-rolled run at 50k tables', () => {
    expect(large().totalWeeks).toBeLessThan(large({ parallelWorkers: 4 }, false).totalWeeks);
  });

  it('more catalogs extend foundation, which headcount does not compress', () => {
    const few = large({ catalogCount: 3 });
    const many = large({ catalogCount: 60 });
    expect(many.phases[1].weeks).toBeGreaterThan(few.phases[1].weeks);
  });
});
