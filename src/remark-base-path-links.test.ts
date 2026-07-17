import { describe, it, expect } from 'vitest';
import { remarkBasePathLinks } from './remark-base-path-links.mjs';

function apply(base: string, url: string): string {
  const tree = { type: 'root', children: [{ type: 'link', url, children: [] }] };
  remarkBasePathLinks(base)(tree as never);
  return (tree.children[0] as { url: string }).url;
}

describe('remarkBasePathLinks', () => {
  it('prefixes absolute root links with the base', () => {
    expect(apply('/databricks-cross-cloud-migration', '/foo/bar')).toBe(
      '/databricks-cross-cloud-migration/foo/bar',
    );
  });

  it('strips a trailing slash from the base', () => {
    expect(apply('/base/', '/foo')).toBe('/base/foo');
  });

  it('does not rewrite protocol-relative links', () => {
    expect(apply('/base', '//evil.com/x')).toBe('//evil.com/x');
  });

  it('leaves external links untouched', () => {
    expect(apply('/base', 'https://example.com/page')).toBe('https://example.com/page');
  });

  it('leaves relative links untouched', () => {
    expect(apply('/base', 'relative/page')).toBe('relative/page');
  });
});
