/**
 * remarkChallengeImages.mjs
 *
 * Remark plugin that rewrites relative image paths in challenge MDX files
 * so they resolve correctly when served as static assets.
 *
 * Given a file at:
 *   challenges/00-access-azure/challenge.mdx
 *
 * It rewrites:
 *   ![](student-rg.png)          → <img src="/challenges/00-access-azure/img/student-rg.png">
 *   ![](./student-rg.png)        → same
 *   ![](./img/student-rg.png)    → same (img/ prefix deduplicated)
 *   ![](img/student-rg.png)      → same
 *
 * Absolute paths and external URLs are left untouched.
 */

import path from 'path'
import { visit } from 'unist-util-visit'

export default function remarkChallengeImages() {
  return (tree, file) => {
    // file.path is the absolute path to the .mdx file
    // e.g. /repo/challenges/00-access-azure/challenge.mdx
    const filePath = file.history?.[0] || file.path || ''
    if (!filePath) return

    // Extract the challenge slug from the directory name
    // challenges/00-access-azure/challenge.mdx → 00-access-azure
    const match = filePath.match(/challenges[\\/]([^\\/]+)[\\/]challenge\.mdx$/)
    if (!match) return

    const slug = match[1]
    const base = `/challenges/${slug}/img/`

    visit(tree, 'image', (node) => {
      const url = node.url || ''

      // Leave absolute paths and external URLs untouched
      if (url.startsWith('/') || url.startsWith('http://') || url.startsWith('https://')) {
        return
      }

      // Strip leading ./ and any img/ prefix, then prepend the full base path
      const filename = path.basename(url)
      node.url = base + filename
    })
  }
}
