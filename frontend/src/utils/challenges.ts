/**
 * Challenge data layer — imports MDX files and index.yaml at build time.
 */

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

// Import index.yaml directly — Vite parses YAML files as JS objects natively
import indexData from '../../../challenges/index.yaml'

// Glob all MDX challenge files
const mdxModules = import.meta.glob(
  '../../../challenges/*/challenge.mdx',
  { eager: true }
) as Record<string, { default: React.ComponentType; frontmatter?: Partial<ChallengeMeta> }>

// ── Build registry ─────────────────────────────────────────────────────────

function buildRegistry(): ChallengeEntry[] {
  const parsed = indexData as { challenges: ChallengeMeta[] }
  const indexById = new Map<string, ChallengeMeta>(
    (parsed?.challenges ?? []).map((c: ChallengeMeta) => [c.id, c])
  )

  const entries: ChallengeEntry[] = []

  for (const [filePath, mod] of Object.entries(mdxModules)) {
    const match = filePath.match(/challenges\/([^/]+)\/challenge\.mdx$/)
    if (!match) continue
    const id = match[1]

    const indexMeta = indexById.get(id) ?? {} as ChallengeMeta
    // MDX frontmatter only has hints/refs — index.yaml is authoritative for
    // visible, scored, points, order. Spread order: index first, mdx second
    // but only pick defined values from mdx frontmatter.
    const fmMeta = mod.frontmatter ?? {}
    const entry: ChallengeEntry = {
      ...indexMeta,
      // Only override with MDX frontmatter values that are explicitly defined
      ...(fmMeta.hints   !== undefined && { hints:   fmMeta.hints }),
      ...(fmMeta.refs    !== undefined && { refs:    fmMeta.refs }),
      ...(fmMeta.title   !== undefined && { title:   fmMeta.title }),
      id,
      Component: mod.default,
    }
    entries.push(entry)
  }

  return entries.sort((a, b) => (a.order ?? 99) - (b.order ?? 99))
}

export const challenges: ChallengeEntry[] = buildRegistry()

export function getChallengeById(id: string): ChallengeEntry | undefined {
  return challenges.find(c => c.id === id)
}
