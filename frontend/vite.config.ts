import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import mdx from '@mdx-js/rollup'
import yaml from '@rollup/plugin-yaml'
import remarkGfm from 'remark-gfm'
import remarkFrontmatter from 'remark-frontmatter'
import remarkChallengeImages from './remarkChallengeImages.mjs'
import remarkMdxFrontmatter from 'remark-mdx-frontmatter'
import rehypeHighlight from 'rehype-highlight'
import path from 'path'

export default defineConfig({
  plugins: [
    yaml(),
    mdx({
      remarkPlugins: [
        remarkGfm,
        remarkFrontmatter,           // parses --- YAML block
        remarkChallengeImages,       // rewrites ./img/foo.png → /challenges/{slug}/img/foo.png
        remarkMdxFrontmatter,        // exports it as `frontmatter` named export
      ],
      rehypePlugins: [rehypeHighlight],
      providerImportSource: path.resolve(__dirname, './node_modules/@mdx-js/react'),
    }),
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      'react': path.resolve(__dirname, './node_modules/react'),
      'react/jsx-runtime': path.resolve(__dirname, './node_modules/react/jsx-runtime'),
      '@mdx-js/react': path.resolve(__dirname, './node_modules/@mdx-js/react'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
    },
    fs: { allow: ['..'] },
  },
})
