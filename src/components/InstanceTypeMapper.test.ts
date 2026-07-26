import { describe, it, expect } from 'vitest';
import { findBestMatch } from './InstanceTypeMapper';
import instanceData from '../data/instanceTypes.json';

const data = instanceData as any;

describe('findBestMatch', () => {
  it('maps an AWS general-purpose instance to the closest Azure equivalent by vCPU/memory', () => {
    const source = data.find((d: any) => d.name === 'm5d.2xlarge');
    const match = findBestMatch(source, data, 'azure');
    expect(match).not.toBeNull();
    expect(match!.cloud).toBe('azure');
    expect(match!.tier).toBe(source.tier);
    expect(match!.vCpu).toBe(8);
    expect(match!.memoryGb).toBe(32);
  });

  it('prefers a matching GPU family over a closer vCPU/memory mismatch', () => {
    const source = data.find((d: any) => d.name === 'p4d.24xlarge'); // AWS A100, 96 vCPU
    const match = findBestMatch(source, data, 'gcp');
    expect(match).not.toBeNull();
    expect(match!.gpuType).toBe('A100');
  });

  it('never matches a GPU instance to a non-GPU instance', () => {
    const source = data.find((d: any) => d.name === 'g5.xlarge');
    const match = findBestMatch(source, data, 'azure');
    expect(match).not.toBeNull();
    expect(match!.gpu).not.toBeNull();
  });

  it('returns null when no instance exists in the target cloud for that tier/GPU combination', () => {
    const source = { cloud: 'aws', family: 'x', name: 'fake', vCpu: 4, memoryGb: 16, gpu: null, gpuType: null, databricksSku: 'X', tier: 'Nonexistent', category: 'Standard' };
    expect(findBestMatch(source as any, data, 'azure')).toBeNull();
  });
});
