/**
 * Challenge data layer.
 *
 * Imports all MDX challenge files at build time using Vite's glob import.
 * Also imports index.yaml for metadata. At runtime this is fully static —
 * no network requests. Hint/solve state comes from the API separately.
 */
import yaml from 'js-yaml'

// ── Types ──────────────────────────────────────────────────────────────────

export interface ChallengeHint {
  text: string
  cost: number
}

export interface ChallengeRef {
  label: string
  url: string
}

/** Metadata from MDX frontmatter (matches index.yaml + per-file hints/refs) */
export interface ChallengeMeta {
  id: string
  title: string
  category: string
  points: number
  scored: boolean
  prober?: string
  order: number
  visible: boolean
  hints?: ChallengeHint[]
  refs?: ChallengeRef[]
}

export interface ChallengeEntry extends ChallengeMeta {
  /** The compiled MDX component, ready to render */
  Component: React.ComponentType
}

// ── Static imports ─────────────────────────────────────────────────────────

// Glob import all MDX files from the challenges directory (outside frontend/src)
// Each module exports default (the component) and frontmatter
const mdxModules = import.meta.glob('/../../challenges/*/challenge.mdx', {
  eager: true,
}) as Record<string, { default: React.ComponentType; frontmatter?: ChallengeMeta }>

// Import index.yaml as raw text then parse
const indexYaml = import.meta.glob('/../../challenges/index.yaml', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

// ── Build the challenge registry ───────────────────────────────────────────

function buildRegistry(): ChallengeEntry[] {
  // Parse index.yaml for order/visibility/scoring metadata
  const indexText = Object.values(indexYaml)[0] ?? ''
  const indexData = yaml.load(indexText) as { challenges: ChallengeMeta[] }
  const indexById = new Map<string, ChallengeMeta>(
    (indexData?.challenges ?? []).map(c => [c.id, c])
  )

  const entries: ChallengeEntry[] = []

  for (const [filePath, mod] of Object.entries(mdxModules)) {
    // Extract id from path: /../../challenges/01-access-azure/challenge.mdx → 01-access-azure
    const match = filePath.match(/challenges\/([^/]+)\/challenge\.mdx$/)
    if (!match) continue
    const id = match[1]

    // Merge: index.yaml base + MDX frontmatter (frontmatter wins for hints/refs)
    const indexMeta = indexById.get(id) ?? {} as ChallengeMeta
    const fmMeta = mod.frontmatter ?? {} as ChallengeMeta

    entries.push({
      ...indexMeta,
      ...fmMeta,
      id,
      Component: mod.default,
    })
  }

  // Sort by order field
  return entries.sort((a, b) => (a.order ?? 99) - (b.order ?? 99))
}

export const challenges: ChallengeEntry[] = buildRegistry()

export function getChallengeById(id: string): ChallengeEntry | undefined {
  return challenges.find(c => c.id === id)
}
