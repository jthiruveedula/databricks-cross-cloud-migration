import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://jthiruveedula.github.io',
  base: '/databricks-cross-cloud-migration/',
  integrations: [
    tailwind({ applyBaseStyles: false }),
    react(),
    mdx(),
  ],
  markdown: {
    shikiConfig: {
      theme: 'github-dark',
      wrap: true,
    },
  },
  build: {
    format: 'file',
  },
});
