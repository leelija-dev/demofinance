import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: 'static',
  base: '/static/',
  publicDir: 'public',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'static/agent/js/index.js'),
        tailwind: resolve(__dirname, 'static/agent/css/tailwind.css'),
      },
      output: {
        entryFileNames: 'js/[name].js',
        chunkFileNames: 'js/[name].[hash].js',
        assetFileNames: (assetInfo) => {
          const ext = assetInfo.name.split('.').pop().toLowerCase();
          if (ext === 'css') {
            return 'css/[name][extname]';
          }
          if (['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'eot', 'ttf', 'woff', 'woff2'].includes(ext)) {
            return 'assets/[name]-[hash][extname]';
          }
          return '[name]-[hash][extname]';
        },
      },
    },
  },
  css: {
    postcss: './postcss.config.cjs',
  },
  server: {
    host: 'localhost',
    port: 3000,
  },
  optimizeDeps: {
    include: ['alpinejs', 'apexcharts', 'flatpickr'],
  },
});
