import { describe, it, expect } from 'vitest';
import { estimateCost, formatCurrency } from './CostCalculator';

const base = {
  clusterCount: 5,
  nodesPerCluster: 3,
  computeHoursPerDay: 8,
  storageTb: 50,
  dataTransferGb: 500,
  gpuWorkload: false,
};

describe('estimateCost', () => {
  it('computes compute, storage, transfer and total for AWS', () => {
    const r = estimateCost('aws', base);
    expect(r.compute).toBe(1980); // 5*3 * (8*30) * 0.55
    expect(r.storage).toBe(1); // round(50 * 0.023)
    expect(r.transfer).toBe(45); // round(500 * 0.09)
    expect(r.total).toBe(r.compute + r.storage + r.transfer);
  });

  it('applies the 2.5x GPU multiplier to compute', () => {
    const r = estimateCost('aws', { ...base, gpuWorkload: true });
    expect(r.compute).toBe(4950); // 1980 * 2.5
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
