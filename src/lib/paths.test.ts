import { describe, it, expect } from 'vitest';
import { withBase } from './paths';

describe('withBase', () => {
  it('prefixes a root-relative path without a leading slash', () => {
    expect(withBase('overview/x')).toBe('/overview/x');
  });

  it('collapses a duplicate leading slash', () => {
    expect(withBase('/overview/x')).toBe('/overview/x');
  });

  it('handles an empty path', () => {
    expect(withBase('')).toBe('/');
  });
});
