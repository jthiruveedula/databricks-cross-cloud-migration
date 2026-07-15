import { visit } from 'unist-util-visit';

// Markdown link syntax (`[text](/path)`) compiles straight to `<a href="/path">` --
// unlike our React components, which route every href through withBase(), plain
// prose links have no equivalent step. On GitHub Pages (served under
// /<repo-name>/, not the domain root) every one of those absolute-root links 404s.
// This rewrites them at build time so content authors can keep writing normal
// root-relative links without knowing about the base path.
export function remarkBasePathLinks(base) {
  const prefix = base.replace(/\/$/, '');
  return (tree) => {
    visit(tree, 'link', (node) => {
      if (typeof node.url === 'string' && node.url.startsWith('/') && !node.url.startsWith('//')) {
        node.url = `${prefix}${node.url}`;
      }
    });
  };
}
