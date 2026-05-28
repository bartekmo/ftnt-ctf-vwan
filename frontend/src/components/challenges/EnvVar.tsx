/**
 * EnvVar — block display of an environment variable value.
 * Used in MDX challenge files as: <EnvVar field="branch_fgt_pip" label="Branch FGT IP" />
 *
 * EnvVarInline — inline span for use inside prose.
 * Used as: connect to <EnvVarInline field="branch_fgt_pip" />
 */
import { useState } from 'react'
import { Copy, CheckCheck, Eye, EyeOff } from 'lucide-react'
import { useEnvData } from '@/hooks/useEnvData'
import type { TeamEnvironment } from '@/utils/api'

interface EnvVarProps {
  field: keyof TeamEnvironment
  label?: string
  secret?: boolean
}

export function EnvVar({ field, label, secret }: EnvVarProps) {
  const env = useEnvData()
  const [copied, setCopied] = useState(false)
  const [revealed, setRevealed] = useState(false)

  const rawValue = env ? String(env[field] ?? '') : null
  const pending = !rawValue

  const copy = () => {
    if (!rawValue) return
    navigator.clipboard.writeText(rawValue)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const display = pending
    ? undefined
    : secret && !revealed
      ? '••••••••'
      : rawValue

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem',
      padding: '0.5rem 0.75rem',
      background: 'var(--color-surface-2)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-md)',
      margin: '0.35rem 0',
      minHeight: 36,
    }}>
      {label && (
        <span style={{
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)',
          fontFamily: 'var(--font-display)',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          flexShrink: 0,
          minWidth: 130,
        }}>
          {label}
        </span>
      )}
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.875rem',
        color: pending ? 'var(--color-text-dim)' : 'var(--color-teal)',
        flex: 1,
      }}>
        {pending ? '…' : display}
      </span>
      {secret && !pending && (
        <button
          onClick={() => setRevealed(v => !v)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', padding: 2 }}
        >
          {revealed ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
      )}
      {!pending && (
        <button
          onClick={copy}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--color-success)' : 'var(--color-text-dim)', padding: 2, flexShrink: 0 }}
        >
          {copied ? <CheckCheck size={13} /> : <Copy size={13} />}
        </button>
      )}
    </div>
  )
}

export function EnvVarInline({ field }: { field: keyof TeamEnvironment }) {
  const env = useEnvData()
  const value = env ? String(env[field] ?? '') : '…'
  return (
    <code style={{
      fontFamily: 'var(--font-mono)',
      fontSize: '0.875em',
      color: 'var(--color-teal)',
      background: 'rgba(0,212,212,0.08)',
      border: '1px solid rgba(0,212,212,0.15)',
      borderRadius: '3px',
      padding: '0.1em 0.4em',
    }}>
      {value}
    </code>
  )
}
