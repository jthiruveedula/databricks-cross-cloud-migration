import { describe, it, expect } from 'vitest';
import { computeMigrationWaves, blastRadius } from './DependencyGraph';

// edges: {source, target} means "source depends on target" (target migrates first)
const nodes = [
  { id: 'a', type: 't', label: 'A', group: 'g' },
  { id: 'b', type: 't', label: 'B', group: 'g' },
  { id: 'c', type: 't', label: 'C', group: 'g' },
  { id: 'd', type: 't', label: 'D', group: 'g' },
];

describe('computeMigrationWaves', () => {
  it('assigns wave 0 to nodes with no dependencies', () => {
    const { waves } = computeMigrationWaves(nodes, []);
    expect(waves.a).toBe(0);
    expect(waves.d).toBe(0);
  });

  it('assigns each node a wave one past its deepest dependency', () => {
    const edges = [
      { source: 'b', target: 'a' }, // b depends on a
      { source: 'c', target: 'b' }, // c depends on b
    ];
    const { waves } = computeMigrationWaves(nodes, edges);
    expect(waves.a).toBe(0);
    expect(waves.b).toBe(1);
    expect(waves.c).toBe(2);
    expect(waves.d).toBe(0);
  });

  it('takes the deepest branch when a node has multiple dependencies', () => {
    const edges = [
      { source: 'c', target: 'a' }, // wave 0 dep
      { source: 'b', target: 'a' },
      { source: 'c', target: 'b' }, // b is wave 1, so c must be wave 2
    ];
    const { waves } = computeMigrationWaves(nodes, edges);
    expect(waves.c).toBe(2);
  });

  it('detects a cycle and excludes cyclic nodes from ordering', () => {
    const edges = [
      { source: 'a', target: 'b' },
      { source: 'b', target: 'a' },
    ];
    const { cycles } = computeMigrationWaves(nodes, edges);
    expect(cycles.length).toBeGreaterThan(0);
  });
});

describe('blastRadius', () => {
  it('counts transitive dependents of a node', () => {
    const edges = [
      { source: 'b', target: 'a' },
      { source: 'c', target: 'b' },
      { source: 'd', target: 'b' },
    ];
    // a <- b <- c, a <- b <- d: disrupting a affects b, c, d
    expect(blastRadius('a', edges)).toBe(3);
    expect(blastRadius('b', edges)).toBe(2);
    expect(blastRadius('d', edges)).toBe(0);
  });

  it('returns 0 for a node nothing depends on', () => {
    expect(blastRadius('a', [])).toBe(0);
  });
});
