/**
 * Challenge data layer — imports MDX files and index.yaml at build time.
 *
 * Authority split:
 *   index.yaml  — id, display order, visible, scored, title (override), category
 *   MDX         — title, points, prober, hints, refs (all content fields)
 *
 * Display order follows the index.yaml array order, NOT directory name sort.
 */

// ── Types ──────────────────────────────────────────────────────────────────

export interface ChallengeHint {
  text: string
  cost: number
}

export interface ChallengeRef {
  label: string
  url:   string
}

export interface ChallengeMeta {
  id:       string
  title:    string
  category: string
  points:   number
  scored:   boolean
  prober?:  string
  visible:  boolean
  hints?:   ChallengeHint[]
  refs?:    ChallengeRef[]
}

export interface ChallengeEntry extends ChallengeMeta {
  Component: React.ComponentType
}

// ── Static imports ─────────────────────────────────────────────────────────

import indexData from '../../../challenges/index.yaml'

const mdxModules = import.meta.glob(
  '../../../challenges/*/challenge.mdx',
  { eager: true }
) as Record<string, { default: React.ComponentType; frontmatter?: Partial<ChallengeMeta> }>

// ── Build registry ─────────────────────────────────────────────────────────

function buildRegistry(): ChallengeEntry[] {
  const parsed = indexData as { challenges: Array<Partial<ChallengeMeta> & { id: string }> }
  const indexList = parsed?.challenges ?? []

  // Build a map of MDX modules keyed by slug
  const mdxById = new Map<string, { Component: React.ComponentType; fm: Partial<ChallengeMeta> }>()
  for (const [filePath, mod] of Object.entries(mdxModules)) {
    const match = filePath.match(/challenges\/([^/]+)\/challenge\.mdx$/)
    if (!match) continue
    mdxById.set(match[1], { Component: mod.default, fm: mod.frontmatter ?? {} })
  }

  // Iterate in index.yaml declaration order — this is the display order
  const entries: ChallengeEntry[] = []
  for (const indexEntry of indexList) {
    const { id } = indexEntry
    const mdx = mdxById.get(id)
    if (!mdx) continue  // MDX file missing — skip silently

    const { Component, fm } = mdx

    // MDX frontmatter is authoritative for: title, points, prober, hints, refs
    // index.yaml is authoritative for: id, scored, visible, category
    const entry: ChallengeEntry = {
      id,
      title:    fm.title    ?? indexEntry.title    ?? id,
      category: fm.category ?? indexEntry.category ?? '',
      points:   fm.points   ?? indexEntry.points   ?? 0,
      scored:   indexEntry.scored  ?? false,
      visible:  indexEntry.visible ?? true,
      ...(indexEntry.prober !== undefined && { prober: indexEntry.prober }),
      ...(fm.hints  !== undefined  && { hints:  fm.hints }),
      ...(fm.refs   !== undefined  && { refs:   fm.refs }),
      Component,
    }
    entries.push(entry)
  }

  return entries
}

export const challenges: ChallengeEntry[] = buildRegistry()

export function getChallengeById(id: string): ChallengeEntry | undefined {
  return challenges.find(c => c.id === id)
}
