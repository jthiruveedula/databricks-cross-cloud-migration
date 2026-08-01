import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';
import { remarkBasePathLinks } from './src/remark-base-path-links.mjs';

const base = '/databricks-cross-cloud-migration/';

export default defineConfig({
  site: 'https://jthiruveedula.github.io',
  base,
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [react(), mdx()],
  markdown: {
    remarkPlugins: [[remarkBasePathLinks, base]],
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
  build: {
    format: 'file',
  },
});
