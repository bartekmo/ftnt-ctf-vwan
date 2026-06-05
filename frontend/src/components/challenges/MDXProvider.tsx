/**
 * MDXProvider — wraps MDX challenge content with:
 * - Custom component mappings (h1–h3, p, code, table, blockquote)
 * - EnvVar / EnvVarInline available globally in all MDX files
 * - Consistent dark-theme prose styling
 */
import { MDXProvider as BaseMDXProvider } from '@mdx-js/react'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { EnvVar, EnvVarInline } from './EnvVar'
import { NvaCard } from './NvaCard'

// ── Prose component overrides ──────────────────────────────────────────────

const H2 = ({ children }: { children?: ReactNode }) => (
  <h2 style={{
    fontFamily: 'var(--font-display)', fontWeight: 700,
    fontSize: '1.3rem', color: 'var(--color-text)',
    margin: '1.75rem 0 0.6rem',
    paddingBottom: '0.4rem',
    borderBottom: '1px solid var(--color-border)',
  }}>{children}</h2>
)

const H3 = ({ children }: { children?: ReactNode }) => (
  <h3 style={{
    fontFamily: 'var(--font-display)', fontWeight: 700,
    fontSize: '1.05rem', color: 'var(--color-text)',
    margin: '1.25rem 0 0.4rem',
    textTransform: 'uppercase', letterSpacing: '0.04em',
  }}>{children}</h3>
)

const P = ({ children }: { children?: ReactNode }) => (
  <p style={{ margin: '0.6rem 0', lineHeight: 1.75, color: 'var(--color-text)' }}>{children}</p>
)

const UL = ({ children }: { children?: ReactNode }) => (
  <ul style={{ margin: '0.6rem 0 0.6rem 1.25rem', lineHeight: 1.75, color: 'var(--color-text)' }}>{children}</ul>
)

const OL = ({ children }: { children?: ReactNode }) => (
  <ol style={{ margin: '0.6rem 0 0.6rem 1.25rem', lineHeight: 1.75, color: 'var(--color-text)' }}>{children}</ol>
)

const LI = ({ children }: { children?: ReactNode }) => (
  <li style={{ marginBottom: '0.25rem' }}>{children}</li>
)

const Code = ({ children, className }: { children: ReactNode; className?: string }) => {
  // Block code (has language class from rehype-highlight)
  if (className) {
    return (
      <code className={className} style={{
        fontFamily: 'var(--font-mono)', fontSize: '0.875rem',
      }}>{children}</code>
    )
  }
  // Inline code
  return (
    <code style={{
      fontFamily: 'var(--font-mono)', fontSize: '0.875em',
      color: 'var(--color-teal)',
      background: 'rgba(0,212,212,0.08)',
      border: '1px solid rgba(0,212,212,0.15)',
      borderRadius: '3px', padding: '0.1em 0.4em',
    }}>{children}</code>
  )
}

const Pre = ({ children }: { children?: ReactNode }) => (
  <pre style={{
    background: 'var(--color-surface-2)',
    border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius-md)',
    padding: '1rem 1.25rem',
    overflowX: 'auto',
    fontFamily: 'var(--font-mono)',
    fontSize: '0.875rem',
    lineHeight: 1.6,
    margin: '0.75rem 0',
    color: 'var(--color-text)',
  }}>{children}</pre>
)

const Blockquote = ({ children }: { children?: ReactNode }) => (
  <blockquote style={{
    borderLeft: '3px solid var(--color-teal-dim)',
    background: 'rgba(0,212,212,0.05)',
    borderRadius: '0 var(--radius-md) var(--radius-md) 0',
    padding: '0.6rem 1rem',
    margin: '0.75rem 0',
    color: 'var(--color-text-muted)',
  }}>{children}</blockquote>
)

const Table = ({ children }: { children?: ReactNode }) => (
  <div style={{ overflowX: 'auto', margin: '0.75rem 0' }}>
    <table style={{
      width: '100%', borderCollapse: 'collapse',
      fontSize: '0.9rem', color: 'var(--color-text)',
    }}>{children}</table>
  </div>
)

const TH = ({ children }: { children?: ReactNode }) => (
  <th style={{
    padding: '0.5rem 0.75rem', textAlign: 'left',
    fontFamily: 'var(--font-display)', fontWeight: 700,
    fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em',
    color: 'var(--color-text-muted)',
    borderBottom: '2px solid var(--color-border)',
  }}>{children}</th>
)

const TD = ({ children }: { children?: ReactNode }) => (
  <td style={{
    padding: '0.5rem 0.75rem',
    borderBottom: '1px solid var(--color-border)',
  }}>{children}</td>
)

const Img = ({ src, alt }: { src?: string; alt?: string }) => {
  const [open, setOpen] = useState(false)
  return (
    <>
      <img
        src={src} alt={alt}
        onClick={() => setOpen(true)}
        style={{
          maxWidth: '100%', height: 'auto', display: 'block',
          margin: '0.75rem 0', borderRadius: 'var(--radius-md)',
          cursor: 'zoom-in', border: '1px solid var(--color-border)',
        }}
      />
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.85)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'zoom-out',
          }}
        >
          <img
            src={src} alt={alt}
            style={{ maxWidth: '90vw', maxHeight: '90vh', objectFit: 'contain' }}
          />
        </div>
      )}
    </>
  )
}

const A = ({ href, children }: { href?: string; children: ReactNode }) => (
  <a href={href} target="_blank" rel="noreferrer" style={{ color: 'var(--color-teal)' }}>
    {children}
  </a>
)

const HR = () => <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', margin: '1.5rem 0' }} />

// ── Component map — also includes EnvVar/EnvVarInline for MDX usage ────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const components: any = {
  h2: H2, h3: H3, p: P,
  ul: UL, ol: OL, li: LI,
  code: Code, pre: Pre,
  blockquote: Blockquote,
  table: Table, th: TH, td: TD,
  a: A, hr: HR, img: Img,
  // Available as JSX components inside any .mdx file
  EnvVar,
  EnvVarInline,
  NvaCard,
}

export function ChallengesMDXProvider({ children }: { children?: ReactNode }) {
  return (
    <BaseMDXProvider components={components}>
      {children}
    </BaseMDXProvider>
  )
}
