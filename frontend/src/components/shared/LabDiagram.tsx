/**
 * LabDiagram — SVG recreation of the topology diagram from vwanlab.40net.cloud
 *
 * Layout (1100×556 original, scaled proportionally):
 *   Branch (left) → vWAN Hub with 2 FGT NVAs (centre) → Spoke VNet (right)
 *
 * Data sources match the original page:
 *   - NVA names + PIPs  from /api/infra/hubs/{hub}/pips
 *   - Spoke server IPs  from /api/infra/hubs/{hub}/srv
 *   - Branch PIPs/CIDR  from /api/infra/branches/{index}
 *   - Spoke CIDR/peered from /api/infra/spokes/{index}
 */
import { useEffect, useState } from 'react'
import { infraApi } from '@/utils/api'

interface Props {
  envId: string      // zero-padded, e.g. "01"
  hubName: string    // e.g. "hub01"
}

interface DiagramData {
  fgt1Name:       string | null
  fgt1Pip:        string | null
  fgt2Name:       string | null
  fgt2Pip:        string | null
  spokeSrv:       string | null
  spokeCidr:      string | null
  spokePeered:    boolean
  branchFgtPip:   string | null
  branchWinPip:   string | null
  branchCidr:     string | null
  hasNvas:        boolean
}

export default function LabDiagram({ envId, hubName }: Props) {
  const [data, setData] = useState<DiagramData>({
    fgt1Name: null, fgt1Pip: null, fgt2Name: null, fgt2Pip: null,
    spokeSrv: null, spokeCidr: null, spokePeered: false,
    branchFgtPip: null, branchWinPip: null, branchCidr: null,
    hasNvas: false,
  })

  useEffect(() => {
    Promise.allSettled([
      infraApi.pips(hubName),
      infraApi.srv(hubName),
      infraApi.branches(envId),
      infraApi.spokes(envId),
    ]).then(([pipsR, srvR, branchR, spokeR]) => {
      setData(prev => {
        const next = { ...prev }

        if (pipsR.status === 'fulfilled') {
          const pips = pipsR.value.data.pips
          const keys = Object.keys(pips)
          if (keys.length > 0) {
            next.hasNvas   = true
            next.fgt1Name  = keys[0]
            next.fgt1Pip   = pips[keys[0]]
            next.fgt2Name  = keys[1] ?? null
            next.fgt2Pip   = keys[1] ? pips[keys[1]] : null
          }
        }
        if (srvR.status === 'fulfilled') {
          next.spokeSrv = srvR.value.data.private
        }
        if (branchR.status === 'fulfilled') {
          const b = branchR.value.data
          next.branchFgtPip = b.branch_fgt_pip
          next.branchWinPip = b.branch_win_pip
          next.branchCidr   = b.branch_cidr
        }
        if (spokeR.status === 'fulfilled') {
          const s = spokeR.value.data
          next.spokeCidr   = s.spoke_cidr
          next.spokePeered = s.spoke_peered
        }
        return next
      })
    })
  }, [hubName, envId])

  // Scale factor: render at 100% of original 1100×556
  const W = 1100
  const H = 556

  // Colours
  const c = {
    bg:         '#0f1117',
    hubBg:      '#1a1e2a',
    hubBorder:  '#e5281e',
    boxBg:      '#1e2330',
    boxBorder:  '#353a48',
    fgtBg:      '#2a1a18',
    fgtBorder:  '#e5281e',
    branchBg:   '#1a2018',
    branchBorder:'#4a8c3f',
    spokeBg:    '#18202a',
    spokeBorder:'#00d4d4',
    line:       '#444',
    lineActive: '#00d4d4',
    text:       '#e8eaf0',
    textMuted:  '#7c8499',
    textTeal:   '#00d4d4',
    textRed:    '#e5281e',
    textGreen:  '#4ade80',
    internet:   '#252830',
  }

  const mono: React.CSSProperties = { fontFamily: 'JetBrains Mono, monospace' }

  const pending = (v: string | null) => v == null ? '…' : v

  return (
    <div style={{
      width: '100%',
      overflowX: 'auto',
      background: c.bg,
      borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--color-border)',
      padding: '0.5rem',
    }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        style={{ display: 'block', maxWidth: '100%' }}
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* ── Background ── */}
        <rect width={W} height={H} fill={c.bg} />

        {/* ── Internet cloud (centre-top) ── */}
        <ellipse cx={550} cy={60} rx={120} ry={35} fill={c.internet} stroke={c.line} strokeWidth={1.5} />
        <text x={550} y={65} textAnchor="middle" fill={c.textMuted} fontSize={13} fontFamily="sans-serif">Internet / Azure backbone</text>

        {/* ══ BRANCH (left) ══════════════════════════════════════════════ */}
        <rect x={20} y={140} width={230} height={260} rx={8} fill={c.branchBg} stroke={c.branchBorder} strokeWidth={1.5} />
        <text x={135} y={162} textAnchor="middle" fill={c.textGreen} fontSize={12} fontWeight="bold" fontFamily="sans-serif">BRANCH SITE</text>

        {/* Branch CIDR */}
        <rect x={35} y={172} width={200} height={28} rx={4} fill={c.boxBg} stroke={c.boxBorder} strokeWidth={1} />
        <text x={135} y={191} textAnchor="middle" fill={c.textMuted} fontSize={10} fontFamily="sans-serif">Subnet</text>
        <text x={135} y={191} dy={0} textAnchor="middle" fill={c.text} fontSize={11} style={mono}>
          <tspan x={135} dy={14}>{pending(data.branchCidr)}</tspan>
        </text>

        {/* Branch FGT */}
        <rect x={35} y={215} width={200} height={50} rx={4} fill={c.fgtBg} stroke={c.fgtBorder} strokeWidth={1} />
        <text x={135} y={232} textAnchor="middle" fill={c.textRed} fontSize={10} fontWeight="bold" fontFamily="sans-serif">FortiGate</text>
        <text x={135} y={247} textAnchor="middle" fill={c.text} fontSize={10} style={mono}>{pending(data.branchFgtPip)}</text>
        <text x={135} y={259} textAnchor="middle" fill={c.textMuted} fontSize={9} fontFamily="sans-serif">Branch FGT PIP</text>

        {/* Branch Windows */}
        <rect x={35} y={275} width={200} height={50} rx={4} fill={c.boxBg} stroke={c.boxBorder} strokeWidth={1} />
        <text x={135} y={292} textAnchor="middle" fill={c.textMuted} fontSize={10} fontFamily="sans-serif">Windows Desktop</text>
        <text x={135} y={308} textAnchor="middle" fill={c.text} fontSize={10} style={mono}>{pending(data.branchWinPip)}</text>
        <text x={135} y={320} textAnchor="middle" fill={c.textMuted} fontSize={9} fontFamily="sans-serif">RDP PIP</text>

        {/* ── Branch → Internet line ── */}
        <line x1={250} y1={240} x2={430} y2={240} stroke={c.line} strokeWidth={1.5} strokeDasharray="6 3" />
        <line x1={430} y1={95} x2={430} y2={240} stroke={c.line} strokeWidth={1.5} strokeDasharray="6 3" />
        <line x1={430} y1={95} x2={480} y2={95} stroke={c.line} strokeWidth={1.5} />

        {/* ══ vWAN HUB (centre) ════════════════════════════════════════ */}
        <rect x={340} y={110} width={440} height={340} rx={10} fill={c.hubBg} stroke={c.hubBorder} strokeWidth={2} />
        <text x={560} y={135} textAnchor="middle" fill={c.textRed} fontSize={13} fontWeight="bold" fontFamily="sans-serif">vWAN HUB — {hubName}</text>

        {/* Internet line into hub */}
        <line x1={480} y1={95} x2={620} y2={95} stroke={c.line} strokeWidth={1.5} />
        <line x1={620} y1={95} x2={620} y2={110} stroke={c.line} strokeWidth={1.5} />

        {/* FGT NVA 1 */}
        <rect x={360} y={155} width={400} height={60} rx={6} fill={c.fgtBg} stroke={c.fgtBorder} strokeWidth={1.5} />
        <text x={375} y={176} fill={c.textRed} fontSize={10} fontWeight="bold" fontFamily="sans-serif">FortiGate NVA 1</text>
        <text x={375} y={191} fill={c.textMuted} fontSize={9} style={mono}>{data.fgt1Name ?? '—'}</text>
        <text x={375} y={205} fill={c.text} fontSize={10} style={mono}>{pending(data.fgt1Pip)}</text>

        {/* FGT NVA 2 */}
        <rect x={360} y={230} width={400} height={60} rx={6} fill={c.fgtBg} stroke={c.fgtBorder} strokeWidth={1.5} />
        <text x={375} y={251} fill={c.textRed} fontSize={10} fontWeight="bold" fontFamily="sans-serif">FortiGate NVA 2</text>
        <text x={375} y={266} fill={c.textMuted} fontSize={9} style={mono}>{data.fgt2Name ?? '—'}</text>
        <text x={375} y={280} fill={c.text} fontSize={10} style={mono}>{pending(data.fgt2Pip)}</text>

        {/* Azure vWAN router (below NVAs) */}
        <rect x={400} y={310} width={320} height={36} rx={6} fill={c.boxBg} stroke={c.boxBorder} strokeWidth={1} />
        <text x={560} y={333} textAnchor="middle" fill={c.textMuted} fontSize={11} fontFamily="sans-serif">Azure vWAN Virtual Router  ASN 65515</text>

        {/* ── Hub → Internet line (uplink) ── */}
        <line x1={560} y1={110} x2={560} y2={95} stroke={c.line} strokeWidth={1.5} />

        {/* ── Hub → Spoke line ── */}
        <line x1={780} y1={310} x2={860} y2={310} stroke={data.spokePeered ? c.lineActive : c.line} strokeWidth={data.spokePeered ? 2.5 : 1.5} strokeDasharray={data.spokePeered ? undefined : '6 3'} />

        {/* ══ SPOKE VNet (right) ══════════════════════════════════════ */}
        <rect x={860} y={180} width={215} height={260} rx={8} fill={c.spokeBg} stroke={c.spokeBorder} strokeWidth={data.spokePeered ? 2 : 1.5} />
        <text x={967} y={202} textAnchor="middle" fill={c.textTeal} fontSize={12} fontWeight="bold" fontFamily="sans-serif">SPOKE VNet</text>

        {/* Peering badge */}
        <rect x={895} y={210} width={145} height={22} rx={4}
          fill={data.spokePeered ? 'rgba(74,222,128,0.12)' : 'rgba(255,255,255,0.04)'}
          stroke={data.spokePeered ? 'rgba(74,222,128,0.3)' : c.boxBorder}
          strokeWidth={1} />
        <text x={967} y={225} textAnchor="middle" fill={data.spokePeered ? c.textGreen : c.textMuted} fontSize={10} fontFamily="sans-serif">
          {data.spokePeered ? '● Peered' : '○ Not peered'}
        </text>

        {/* Spoke CIDR */}
        <rect x={875} y={242} width={185} height={28} rx={4} fill={c.boxBg} stroke={c.boxBorder} strokeWidth={1} />
        <text x={967} y={258} textAnchor="middle" fill={c.textMuted} fontSize={9} fontFamily="sans-serif">Address space</text>
        <text x={967} y={271} textAnchor="middle" fill={c.text} fontSize={10} style={mono}>{pending(data.spokeCidr)}</text>

        {/* Spoke server */}
        <rect x={875} y={282} width={185} height={50} rx={4} fill={c.boxBg} stroke={c.spokeBorder} strokeWidth={1} />
        <text x={967} y={299} textAnchor="middle" fill={c.textTeal} fontSize={10} fontFamily="sans-serif">Spoke Server (private)</text>
        <text x={967} y={315} textAnchor="middle" fill={c.text} fontSize={11} style={mono}>{pending(data.spokeSrv)}</text>
        <text x={967} y={328} textAnchor="middle" fill={c.textMuted} fontSize={9} fontFamily="sans-serif">private IP</text>

        {/* ── Spoke → Internet line (if peered) ── */}
        {data.spokePeered && (
          <>
            <line x1={967} y1={180} x2={967} y2={95} stroke={c.lineActive} strokeWidth={1.5} />
            <line x1={620} y1={95} x2={967} y2={95} stroke={c.lineActive} strokeWidth={1.5} />
          </>
        )}

        {/* ── Legend ── */}
        <rect x={20} y={430} width={200} height={100} rx={6} fill={c.boxBg} stroke={c.boxBorder} strokeWidth={1} />
        <text x={30} y={448} fill={c.textMuted} fontSize={10} fontFamily="sans-serif">Legend</text>
        <line x1={30} y1={462} x2={60} y2={462} stroke={c.lineActive} strokeWidth={2} />
        <text x={68} y={466} fill={c.text} fontSize={10} fontFamily="sans-serif">Active / peered</text>
        <line x1={30} y1={480} x2={60} y2={480} stroke={c.line} strokeWidth={1.5} strokeDasharray="6 3" />
        <text x={68} y={484} fill={c.text} fontSize={10} fontFamily="sans-serif">Not yet connected</text>
        <rect x={30} y={493} width={12} height={10} rx={2} fill={c.fgtBg} stroke={c.fgtBorder} strokeWidth={1} />
        <text x={48} y={502} fill={c.text} fontSize={10} fontFamily="sans-serif">FortiGate</text>
        <rect x={30} y={508} width={12} height={10} rx={2} fill={c.boxBg} stroke={c.spokeBorder} strokeWidth={1} />
        <text x={48} y={517} fill={c.text} fontSize={10} fontFamily="sans-serif">Spoke / Azure resource</text>
      </svg>
    </div>
  )
}
