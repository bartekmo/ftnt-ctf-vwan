/**
 * NvaCard — renders both hub NVAs as clickable cards, identical to
 * the Hub NVAs frame in EnvironmentPage. Registered in MDXProvider
 * so it can be used in any challenge MDX file with no props:
 *
 *   <NvaCard />
 */
import { Copy, CheckCheck, Clock } from 'lucide-react'
import { useState } from 'react'
import { useEnvData } from '@/hooks/useEnvData'

export function NvaCard() {
  const env = useEnvData()

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', margin: '0.5rem 0' }}>
      <NvaRow
        name={env?.fgt_nva1_name ?? null}
        pip={env?.fgt_nva1_pip ?? null}
        url={env?.url_fgt_nva1 ?? null}
      />
      <NvaRow
        name={env?.fgt_nva2_name ?? null}
        pip={env?.fgt_nva2_pip ?? null}
        url={env?.url_fgt_nva2 ?? null}
      />
    </div>
  )
}

function NvaRow({ name, pip, url }: {
  name: string | null
  pip:  string | null
  url:  string | null
}) {
  const [copied, setCopied] = useState(false)
  const pending = !pip

  const copy = () => {
    if (!pip) return
    navigator.clipboard.writeText(pip)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{
      background: 'var(--color-surface-2)',
      border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius-md)',
      padding: '0.6rem 0.75rem',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem',
    }}>
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-text)', fontWeight: 600 }}>
          {name ?? '…'}
        </div>
        {pending ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
            <Clock size={10} /> pending deployment
          </span>
        ) : (
          <a href={url ?? '#'} target="_blank" rel="noreferrer"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-teal)', marginTop: '0.2rem', display: 'block' }}>
            {pip} ↗
          </a>
        )}
      </div>
      {!pending && (
        <button onClick={copy} style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--color-success)' : 'var(--color-text-dim)', flexShrink: 0 }}>
          {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
        </button>
      )}
    </div>
  )
}
