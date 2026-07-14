// GitHub Pages serves this project under /<repo-name>/, not the domain root, so every
// internal link must be prefixed with Astro's configured `base` (see astro.config.mjs).
// BASE_URL only ends in "/" if the config value itself does -- normalize here so a config
// edit can never silently reintroduce a missing-slash 404.
const base = import.meta.env.BASE_URL.replace(/\/?$/, '/');

/** Prefix an app-root-relative path (with or without a leading slash) with the configured base. */
export function withBase(path: string): string {
  return `${base}${path.replace(/^\//, '')}`;
}
