import { describe, it, expect } from 'vitest';
import { estimateCost, formatCurrency } from './CostCalculator';

const base = {
  clusterCount: 5,
  nodesPerCluster: 3,
  computeHoursPerDay: 8,
  storageTb: 50,
  dataTransferGb: 500,
  gpuWorkload: false,
  workloadType: 'allPurpose' as const,
};

describe('estimateCost', () => {
  it('computes compute, dbu, storage, transfer and total for AWS', () => {
    const r = estimateCost('aws', base);
    expect(r.compute).toBe(1980); // 5*3 * (8*30) * 0.55
    expect(r.dbu).toBe(1980); // 5*3 * (8*30) * 0.55 (allPurpose DBU rate == 0.55)
    expect(r.storage).toBe(1150); // round(50 * 1000 * 0.023) -- TB converted to GB
    expect(r.transfer).toBe(45); // round(500 * 0.09)
    expect(r.total).toBe(r.compute + r.dbu + r.storage + r.transfer);
  });

  it('converts storage TB to GB before applying the per-GB rate', () => {
    const r = estimateCost('aws', { ...base, storageTb: 1 });
    expect(r.storage).toBe(23); // round(1 * 1000 * 0.023), not round(1 * 0.023)
  });

  it('applies the 2.5x GPU multiplier to compute and DBU', () => {
    const r = estimateCost('aws', { ...base, gpuWorkload: true });
    expect(r.compute).toBe(4950); // 1980 * 2.5
    expect(r.dbu).toBe(4950); // 1980 * 2.5
  });

  it('charges less DBU for Jobs Compute than All-Purpose Compute', () => {
    const jobs = estimateCost('aws', { ...base, workloadType: 'jobs' });
    const allPurpose = estimateCost('aws', { ...base, workloadType: 'allPurpose' });
    expect(jobs.dbu).toBeLessThan(allPurpose.dbu);
  });

  it('reflects lower rates for GCP than AWS', () => {
    expect(estimateCost('gcp', base).total).toBeLessThan(estimateCost('aws', base).total);
  });
});

describe('formatCurrency', () => {
  it('formats with a $ and thousands separators', () => {
    expect(formatCurrency(1234567)).toBe('$1,234,567');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0');
  });
});
