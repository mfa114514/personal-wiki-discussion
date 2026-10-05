import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const release = new URL('./dist/natural-links/', import.meta.url);
await mkdir(release, { recursive: true });
await build({
  entryPoints: ['src/main.ts'],
  bundle: true,
  external: ['obsidian'],
  format: 'cjs',
  target: 'es2022',
  outfile: fileURLToPath(new URL('main.js', release)),
  logLevel: 'info'
});
for (const file of ['manifest.json', 'styles.css']) {
  await copyFile(new URL(file, import.meta.url), new URL(file, release));
}
