/**
 * EnvVar — block display of an environment variable value.
 *
 * Usage variants:
 *
 *   Field from environment:
 *     <EnvVar field="branch_fgt_pip" label="Branch FGT IP" />
 *
 *   Static literal string:
 *     <EnvVar value="admin" label="Username" />
 *
 *   Field with prefix/suffix (mixed):
 *     <EnvVar field="fgt_nva1_pip" prefix="https://" label="NVA 1 URL" />
 *     <EnvVar field="env_id" prefix="vwanlab" suffix="@fortinetcloud.onmicrosoft.com" label="Username" />
 *
 *   Clickable link (opens in new tab):
 *     <EnvVar field="url_fmg" label="FortiManager" link />
 *     <EnvVar field="fmg_ip" prefix="https://" label="FortiManager" link />
 *     <EnvVar value="https://portal.azure.com" label="Azure Portal" link />
 *
 *   Secret (hidden by default, reveal button):
 *     <EnvVar field="azure_password" label="Password" secret />
 *
 * EnvVarInline — inline span for use inside prose:
 *   connect to <EnvVarInline field="branch_fgt_pip" />
 *   open <EnvVarInline field="hub_name" prefix="https://" suffix=".example.com" />
 */
import { useState } from 'react'
import { Copy, CheckCheck, Eye, EyeOff, ExternalLink } from 'lucide-react'
import { useEnvData } from '@/hooks/useEnvData'
import type { TeamEnvironment } from '@/utils/api'

interface EnvVarProps {
  field?:   keyof TeamEnvironment   // variable from environment
  value?:   string                  // literal static string (alternative to field)
  prefix?:  string                  // prepended to the resolved value
  suffix?:  string                  // appended to the resolved value
  label?:   string
  secret?:  boolean
  link?:    boolean                 // render value as a clickable link
}

export function EnvVar({ field, value: staticValue, prefix = '', suffix = '', label, secret, link }: EnvVarProps) {
  const env = useEnvData()
  const [copied, setCopied] = useState(false)
  const [revealed, setRevealed] = useState(false)

  // Resolve the core value
  const coreValue = staticValue !== undefined
    ? staticValue
    : field && env ? String(env[field] ?? '') : null

  const pending  = coreValue === null
  const rawValue = pending ? null : `${prefix}${coreValue}${suffix}`

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

  const valueNode = link && rawValue && !secret ? (
    <a
      href={rawValue}
      target="_blank"
      rel="noreferrer"
      style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.875rem',
        color: 'var(--color-teal)',
        flex: 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        textDecoration: 'none',
      }}
    >
      {display}
      <ExternalLink size={11} style={{ flexShrink: 0, opacity: 0.7 }} />
    </a>
  ) : (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: '0.875rem',
      color: pending ? 'var(--color-text-dim)' : 'var(--color-teal)',
      flex: 1,
    }}>
      {pending ? '…' : display}
    </span>
  )

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
      {valueNode}
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

interface EnvVarInlineProps {
  field?:   keyof TeamEnvironment
  value?:   string
  prefix?:  string
  suffix?:  string
}

export function EnvVarInline({ field, value: staticValue, prefix = '', suffix = '' }: EnvVarInlineProps) {
  const env = useEnvData()
  const coreValue = staticValue !== undefined
    ? staticValue
    : field && env ? String(env[field] ?? '') : '…'
  const display = `${prefix}${coreValue}${suffix}`
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
      {display}
    </code>
  )
}
