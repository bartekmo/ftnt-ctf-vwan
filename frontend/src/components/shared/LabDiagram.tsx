/**
 * LabDiagram — faithful recreation of the vwanlab.40net.cloud diagram.
 * Uses the original PNG backgrounds with absolutely positioned text overlays,
 * matching the exact positions from the original CSS.
 *
 * Original container: 1100×556px, light grey background (#f0f0f0).
 * Text overlay positions preserved verbatim from the original stylesheet.
 */
import { useEffect, useState } from 'react'
import { infraApi } from '@/utils/api'

interface Props {
  envId: string    // zero-padded, e.g. "01"
  hubName: string  // e.g. "hub01"
}

interface DiagramData {
  fgt1Name:     string | null
  fgt1Pip:      string | null
  fgt2Name:     string | null
  fgt2Pip:      string | null
  spokeSrv:     string | null
  spokeCidr:    string | null
  spokePeered:  boolean
  branchFgtPip: string | null
  branchWinPip: string | null
  branchCidr:   string | null
  hasNvas:      boolean
}

const EMPTY: DiagramData = {
  fgt1Name: null, fgt1Pip: null, fgt2Name: null, fgt2Pip: null,
  spokeSrv: null, spokeCidr: null, spokePeered: false,
  branchFgtPip: null, branchWinPip: null, branchCidr: null,
  hasNvas: false,
}

export default function LabDiagram({ envId, hubName }: Props) {
  const [data, setData] = useState<DiagramData>(EMPTY)

  useEffect(() => {
    setData(EMPTY)
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
          if (pips.length > 0) {
            next.hasNvas  = true
            next.fgt1Name = pips[0].nva_name
            next.fgt1Pip  = pips[0].pip
            next.fgt2Name = pips[1]?.nva_name ?? null
            next.fgt2Pip  = pips[1]?.pip ?? null
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
          next.spokeCidr   = spokeR.value.data.spoke_cidr
          next.spokePeered = spokeR.value.data.spoke_peered
        }
        return next
      })
    })
  }, [hubName, envId])

  // Overlay text style — matches original #diag div rules
  const ov: React.CSSProperties = {
    position: 'absolute',
    width: 80,
    fontSize: '0.7em',
    textAlign: 'center',
    fontFamily: 'monospace',
    lineHeight: 1.3,
    color: '#101010',
  }

  return (
    <div style={{ background: '#f0f0f0', borderRadius: 'var(--radius-lg)', padding: '1rem', overflowX: 'auto' }}>
      {/* Matches original: width:1100px, height:556px, position:relative */}
      <div style={{
        backgroundImage: `url(/${data.hasNvas ? 'diagram2' : 'diagram0'}.png)`,
        backgroundRepeat: 'no-repeat',
        backgroundSize: '1100px 556px',
        width: 1100,
        height: 556,
        position: 'relative',
      }}>
        {/* Positions taken verbatim from original CSS */}

        {/* diag_branch: left:80, top:210 */}
        <div style={{ ...ov, left: 80, top: 210 }}>
          {data.branchCidr && `[${data.branchCidr}]`}
        </div>

        {/* diag_branchfgtpip: left:240, top:330 */}
        <div style={{ ...ov, left: 240, top: 330 }}>
          {data.branchFgtPip}
        </div>

        {/* diag_branchwin: left:33, top:360 */}
        <div style={{ ...ov, left: 33, top: 360 }}>
          {data.branchWinPip}
        </div>

        {/* diag_fgt1pip: left:440, top:275 */}
        <div style={{ ...ov, left: 440, top: 275 }}>
          {data.fgt1Pip}
        </div>

        {/* diag_fgt2pip: left:440, top:360 */}
        <div style={{ ...ov, left: 440, top: 360 }}>
          {data.fgt2Pip}
        </div>

        {/* diag_fgt1: left:542, top:275, width:200 */}
        <div style={{ ...ov, left: 542, top: 275, width: 200 }}>
          {data.fgt1Name}
        </div>

        {/* diag_fgt2: left:542, top:360, width:200 */}
        <div style={{ ...ov, left: 542, top: 360, width: 200 }}>
          {data.fgt2Name}
        </div>

        {/* diag_spokesrv: left:929, top:320 */}
        <div style={{ ...ov, left: 929, top: 320 }}>
          {data.spokeSrv}
        </div>

        {/* diag_spoke: left:929, top:227 */}
        <div style={{ ...ov, left: 929, top: 227 }}>
          {data.spokeCidr && `[${data.spokeCidr}]`}
        </div>

        {/* vnet_connect canvas: left:755, top:210, 130×150
            Draws a horizontal line at y=75 when spoke is peered */}
        <canvas
          ref={el => {
            if (!el) return
            const ctx = el.getContext('2d')!
            ctx.clearRect(0, 0, el.width, el.height)
            if (data.spokePeered) {
              ctx.strokeStyle = '#101010'
              ctx.lineWidth = 2
              ctx.beginPath()
              ctx.moveTo(0, 75)
              ctx.lineTo(130, 75)
              ctx.stroke()
            }
          }}
          style={{ position: 'absolute', left: 755, top: 210 }}
          width={130}
          height={150}
        />
      </div>
    </div>
  )
}
