/**
 * Challenge data layer.
 *
 * Imports all MDX challenge files at build time using Vite's glob import.
 * The @challenges alias resolves to ../../challenges (the repo-level directory).
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
  Component: React.ComponentType
}

// ── Static imports ─────────────────────────────────────────────────────────

// Glob relative to this file: ../../../challenges/*/challenge.mdx
// Using the alias is more reliable across environments
const mdxModules = import.meta.glob(
  '../../../challenges/*/challenge.mdx',
  { eager: true }
) as Record<string, { default: React.ComponentType; frontmatter?: Partial<ChallengeMeta> }>

const indexRaw = import.meta.glob(
  '../../../challenges/index.yaml',
  { eager: true, query: '?raw', import: 'default' }
) as Record<string, string>

// ── Build registry ─────────────────────────────────────────────────────────

function buildRegistry(): ChallengeEntry[] {
  // Parse index.yaml
  const indexText = Object.values(indexRaw)[0] ?? ''
  const indexData = yaml.load(indexText) as { challenges: ChallengeMeta[] } | null
  const indexById = new Map<string, ChallengeMeta>(
    (indexData?.challenges ?? []).map(c => [c.id, c])
  )

  const entries: ChallengeEntry[] = []

  for (const [filePath, mod] of Object.entries(mdxModules)) {
    const match = filePath.match(/challenges\/([^/]+)\/challenge\.mdx$/)
    if (!match) continue
    const id = match[1]

    const indexMeta = indexById.get(id) ?? {} as ChallengeMeta
    const fmMeta = (mod.frontmatter ?? {}) as Partial<ChallengeMeta>

    entries.push({
      ...indexMeta,
      ...fmMeta,
      id,
      Component: mod.default,
    })
  }

  return entries.sort((a, b) => (a.order ?? 99) - (b.order ?? 99))
}

export const challenges: ChallengeEntry[] = buildRegistry()

export function getChallengeById(id: string): ChallengeEntry | undefined {
  return challenges.find(c => c.id === id)
}
