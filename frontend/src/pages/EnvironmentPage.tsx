import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { teamsApi, infraApi, type TeamEnvironment, type SrvOut, type FmgOut, type HubDetailOut } from '@/utils/api'
import LabDiagram from '@/components/shared/LabDiagram'
import { useAuthStore } from '@/store/authStore'
import {
  Server, Network, Key, Cpu, GitBranch,
  Globe, Terminal, Copy, CheckCheck, Clock
} from 'lucide-react'

export default function EnvironmentPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [env, setEnv] = useState<TeamEnvironment | null>(null)
  const [srv, setSrv] = useState<SrvOut | null>(null)
  const [fmg, setFmg] = useState<FmgOut | null>(null)
  const [hub, setHub] = useState<HubDetailOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState<string | null>(null)

  useEffect(() => {
    if (!user?.team_id) { navigate('/team'); return }

    teamsApi.myEnvironment()
      .then(r => {
        const envData = r.data
        setEnv(envData)

        // Hub name = "hub" + env_id, e.g. env_id "01" → "hub01"
        const hubName = `hub${envData.env_id}`

        // Fetch live FMG, spoke server, and hub detail in parallel
        Promise.allSettled([
          infraApi.srv(hubName),
          infraApi.fmg(),
          infraApi.hub(hubName),
        ]).then(([srvResult, fmgResult, hubResult]) => {
          if (srvResult.status === 'fulfilled') setSrv(srvResult.value.data)
          if (fmgResult.status === 'fulfilled') setFmg(fmgResult.value.data)
          if (hubResult.status === 'fulfilled') setHub(hubResult.value.data)
        })
      })
      .catch(() => setError('Failed to load environment data'))
      .finally(() => setLoading(false))
  }, [user, navigate])

  const copy = (text: string | null | undefined, key: string) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
      <span className="spinner" style={{ width: 32, height: 32 }} />
    </div>
  )

  if (error || !env) return (
    <div style={{ maxWidth: 700, margin: '4rem auto', padding: '0 1.5rem' }}>
      <div className="alert alert-error">{error || 'Environment not found'}</div>
    </div>
  )

  // Spoke server: prefer live data from /infra/hubs/.../srv, fall back to env data
  const spokePrivate = srv?.private ?? env.spoke_server_private
  const spokePublic  = srv?.public  ?? env.spoke_server_public

  // FMG: prefer live data from /infra/fmg, fall back to env data
  const fmgSerial = fmg?.serial ?? env.fmg_serial
  const fmgIp     = fmg?.ip     ?? env.fmg_ip

  return (
    <div className="page-enter" style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1.5rem' }}>

      {/* Page header */}
      <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
        <div style={{
          width: 56, height: 56, flexShrink: 0,
          background: 'linear-gradient(135deg, var(--color-teal-dim), var(--color-teal))',
          borderRadius: 'var(--radius-lg)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'var(--shadow-teal)',
        }}>
          <Terminal size={26} color="#0a0c10" />
        </div>
        <div>
          <h2 style={{ marginBottom: '0.2rem' }}>
            My Environment
            <span style={{
              marginLeft: '0.75rem',
              fontFamily: 'var(--font-mono)',
              fontSize: '1.1rem',
              color: 'var(--color-teal)',
              background: 'rgba(0,212,212,0.1)',
              border: '1px solid rgba(0,212,212,0.25)',
              borderRadius: 'var(--radius-sm)',
              padding: '0.1rem 0.5rem',
            }}>
              hub{env.env_id}
            </span>
          </h2>
          <p className="text-muted" style={{ fontSize: '0.9rem' }}>
            Team <strong style={{ color: 'var(--color-text)' }}>{env.team_name}</strong> · Azure lab environment
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))' }}>

        {/* Azure Credentials */}
        <EnvCard icon={<Key size={18} color="var(--color-red)" />} title="Azure Credentials">
          <EnvRow label="Username" value={env.azure_username} onCopy={() => copy(env.azure_username, 'az_user')} copied={copied === 'az_user'} />
          <EnvRow label="Password" value={env.azure_password} secret onCopy={() => copy(env.azure_password, 'az_pass')} copied={copied === 'az_pass'} />
          <EnvRow label="Resource group" value={env.rg_name} onCopy={() => copy(env.rg_name, 'rg')} copied={copied === 'rg'} mono />
          <EnvRow label="Region" value={hub?.location ?? null} mono />
          <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--color-border)' }}>
            <a href="https://portal.azure.com" target="_blank" rel="noreferrer"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--color-teal)' }}>
              <Globe size={13} /> portal.azure.com ↗
            </a>
          </div>
        </EnvCard>

        {/* FortiManager — live data from /api/infra/fmg */}
        <EnvCard icon={<Server size={18} color="var(--color-teal)" />} title="FortiManager (Shared)">
          <EnvRow label="Username" value={`vwanlab${env.env_id}`} onCopy={() => copy(`vwanlab${env.env_id}`, 'fmg_user')} copied={copied === 'fmg_user'} mono />
          <EnvRow label="Serial" value={fmgSerial} mono />
          <EnvRow label="IP / FQDN" value={fmgIp} mono onCopy={() => copy(fmgIp, 'fmg')} copied={copied === 'fmg'} />
          {fmgIp && (
            <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--color-border)' }}>
              <a href={`https://${fmgIp}`} target="_blank" rel="noreferrer"
                style={{ fontSize: '0.85rem', color: 'var(--color-teal)', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Globe size={13} /> Open FortiManager ↗
              </a>
            </div>
          )}
        </EnvCard>

        {/* BGP / ASNs */}
        <EnvCard icon={<Network size={18} color="var(--color-teal)" />} title="BGP ASNs">
          <EnvRow label="FortiGate NVAs" value={String(env.fgt_asn)} onCopy={() => copy(String(env.fgt_asn), 'asn_fgt')} copied={copied === 'asn_fgt'} mono />
          <EnvRow label="Azure vWAN" value={String(env.azure_asn)} onCopy={() => copy(String(env.azure_asn), 'asn_az')} copied={copied === 'asn_az'} mono />
        </EnvCard>

        {/* Networking */}
        <EnvCard icon={<Cpu size={18} color="var(--color-teal)" />} title="Networking">
          <EnvRow label="Overlay network"   value={env.overlay_network}        onCopy={() => copy(env.overlay_network, 'overlay')}   copied={copied === 'overlay'} mono />
          <EnvRow label="SD-WAN healthcheck" value={env.sdwan_healthcheck_range} onCopy={() => copy(env.sdwan_healthcheck_range, 'hc')} copied={copied === 'hc'} mono />
          <EnvRow label="Spoke CIDR"        value={env.spoke_cidr}             onCopy={() => copy(env.spoke_cidr, 'spoke_cidr')}     copied={copied === 'spoke_cidr'} mono />
          <EnvRow label="Branch CIDR"       value={env.branch_cidr}            onCopy={() => copy(env.branch_cidr, 'branch_cidr')}   copied={copied === 'branch_cidr'} mono />
        </EnvCard>

        {/* Hub NVAs */}
        <EnvCard icon={<Server size={18} color="var(--color-red)" />} title="Hub NVAs (FortiGates)">
          <NvaRow name={env.fgt_nva1_name} pip={env.fgt_nva1_pip} onCopy={() => copy(env.fgt_nva1_pip, 'fgt1')} copied={copied === 'fgt1'} />
          <NvaRow name={env.fgt_nva2_name} pip={env.fgt_nva2_pip} onCopy={() => copy(env.fgt_nva2_pip, 'fgt2')} copied={copied === 'fgt2'} />
        </EnvCard>

        {/* FortiFlex */}
        <EnvCard icon={<Key size={18} color="var(--color-teal)" />} title="FortiFlex Tokens (NVA Licenses)">
          <EnvRow label="Token 1" value={env.flex_token1} onCopy={() => copy(env.flex_token1, 'flex1')} copied={copied === 'flex1'} mono />
          <EnvRow label="Token 2" value={env.flex_token2} onCopy={() => copy(env.flex_token2, 'flex2')} copied={copied === 'flex2'} mono />
        </EnvCard>

        {/* Spoke VNet — live data from /infra/hubs/{hub}/srv */}
        <EnvCard icon={<GitBranch size={18} color="var(--color-teal)" />} title="Spoke VNet">
          <EnvRow label="Server (private)" value={spokePrivate} onCopy={() => copy(spokePrivate, 'spoke_priv')} copied={copied === 'spoke_priv'} mono />
          <EnvRow label="Server (public)"  value={spokePublic}  onCopy={() => copy(spokePublic,  'spoke_pub')}  copied={copied === 'spoke_pub'}  mono />
          <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <span className="text-muted">VNet peering:</span>
            <span className={`badge ${env.spoke_peered ? 'badge-green' : 'badge-gray'}`}>
              {env.spoke_peered ? 'Connected' : 'Not peered'}
            </span>
          </div>
        </EnvCard>

        {/* Branch */}
        <EnvCard icon={<GitBranch size={18} color="var(--color-red)" />} title="Branch Site">
          <EnvRow label="FortiGate PIP"    value={env.branch_fgt_pip} onCopy={() => copy(env.branch_fgt_pip, 'br_fgt')} copied={copied === 'br_fgt'} mono />
          <EnvRow label="Windows Desktop"  value={env.branch_win_pip} onCopy={() => copy(env.branch_win_pip, 'br_win')} copied={copied === 'br_win'} mono />
          {env.branch_fgt_pip && (
            <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--color-border)' }}>
              <a href={`https://${env.branch_fgt_pip}`} target="_blank" rel="noreferrer"
                style={{ fontSize: '0.85rem', color: 'var(--color-teal)', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <Server size={13} /> Open Branch FGT ↗
              </a>
            </div>
          )}
        </EnvCard>


      </div>

      {/* Network topology diagram */}
      <div style={{ marginTop: '1.5rem' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '0.75rem' }}>
          Network Topology
        </div>
        <LabDiagram envId={env.env_id} hubName={`hub${env.env_id}`} />
      </div>

      {/* Useful links */}
      <div className="card" style={{ marginTop: '1rem', padding: '1rem 1.25rem' }}>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.8rem', letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '0.75rem' }}>
          References
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
          {[
            { label: 'Azure Portal', href: 'https://portal.azure.com' },
            { label: 'FGT vWAN Deployment Guide', href: 'https://docs.fortinet.com/document/fortigate-public-cloud/7.4.0/azure-vwan-sd-wan-ngfw-deployment-guide/355051/deploying-vwan-on-azure' },
          ].map(l => (
            <a key={l.href} href={l.href} target="_blank" rel="noreferrer"
              style={{ fontSize: '0.85rem', color: 'var(--color-teal)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <Globe size={12} /> {l.label}
            </a>
          ))}
        </div>
      </div>

    </div>
  )
}

// ── Sub-components ──────────────────────────────────────────────────────────

function EnvCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid var(--color-border)' }}>
        {icon}
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.85rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
          {title}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {children}
      </div>
    </div>
  )
}

function EnvRow({ label, value, secret, mono, onCopy, copied }: {
  label: string
  value: string | null | undefined
  secret?: boolean
  mono?: boolean
  onCopy?: () => void
  copied?: boolean
}) {
  const [revealed, setRevealed] = useState(false)
  const pending = value == null || value === ''
  const display = pending ? undefined : (secret && !revealed ? '••••••••' : value)

  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', minHeight: 28 }}>
      <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', flexShrink: 0, minWidth: 140 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 }}>
        {pending ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.78rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
            <Clock size={11} /> pending
          </span>
        ) : (
          <span style={{ fontFamily: mono || secret ? 'var(--font-mono)' : 'var(--font-body)', fontSize: '0.85rem', color: 'var(--color-text)', wordBreak: 'break-all' }}>
            {display}
          </span>
        )}
        {secret && !pending && (
          <button onClick={() => setRevealed(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-dim)', padding: '0 2px', flexShrink: 0, fontSize: '0.75rem' }}>
            {revealed ? 'hide' : 'show'}
          </button>
        )}
        {onCopy && !pending && (
          <button onClick={onCopy} style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--color-success)' : 'var(--color-text-dim)', flexShrink: 0, padding: '0 2px' }}>
            {copied ? <CheckCheck size={13} /> : <Copy size={13} />}
          </button>
        )}
      </div>
    </div>
  )
}

function NvaRow({ name, pip, onCopy, copied }: {
  name: string; pip: string | null | undefined; onCopy: () => void; copied: boolean
}) {
  const pending = pip == null || pip === ''
  return (
    <div style={{ background: 'var(--color-surface-2)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)', padding: '0.6rem 0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--color-text)', fontWeight: 600 }}>{name}</div>
        {pending ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
            <Clock size={10} /> pending deployment
          </span>
        ) : (
          <a href={`https://${pip}`} target="_blank" rel="noreferrer"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--color-teal)', marginTop: '0.2rem', display: 'block' }}>
            {pip} ↗
          </a>
        )}
      </div>
      {!pending && (
        <button onClick={onCopy} style={{ background: 'none', border: 'none', cursor: 'pointer', color: copied ? 'var(--color-success)' : 'var(--color-text-dim)', flexShrink: 0 }}>
          {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
        </button>
      )}
    </div>
  )
}
