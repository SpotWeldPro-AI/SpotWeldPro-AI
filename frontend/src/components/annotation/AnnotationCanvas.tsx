/**
 * VISION-P3E: SVG-based annotation canvas.
 *
 * Tools: bbox (drag to draw), polygon (click to add points, dbl-click closes),
 *        point (single click), pan (space+drag or pan-mode).
 * Zoom: scroll wheel (Ctrl not required).
 * Pan: space+drag, or switch to 'pan' tool.
 * Regions are rendered as SVG overlays on top of the image.
 *
 * Constraints:
 *  - Originals are immutable: canvas does NOT modify or overwrite source images.
 *  - All coordinates are stored in image-pixel space (not canvas space).
 */
import { useRef, useState, useEffect, useCallback } from 'react'

export type RegionType = 'BBOX' | 'POLYGON' | 'POINT' | 'WHOLE_IMAGE'

export interface Region {
  id: string
  type: RegionType
  data: Record<string, unknown>
  defectCode?: string
  color?: string
}

type Tool = 'bbox' | 'polygon' | 'point' | 'pan' | 'select'

interface Props {
  imageSrc: string
  imageWidth: number
  imageHeight: number
  regions: Region[]
  activeTool: Tool
  onRegionAdd?: (r: Region) => void
  onRegionRemove?: (id: string) => void
  readOnly?: boolean
}

const COLORS: Record<string, string> = {
  capak: '#f59e0b',
  deformeli: '#3b82f6',
  kopuk: '#ef4444',
  eksik: '#8b5cf6',
  kucuk_cekirdek: '#06b6d4',
  kacik: '#10b981',
  ust_uste: '#f97316',
  kenar: '#ec4899',
  delik: '#dc2626',
  cift_sac: '#7c3aed',
  cokertme: '#6366f1',
  generic_bad: '#9ca3af',
  expulsion: '#b45309',
  ok: '#22c55e',
  default: '#facc15',
}

function colorFor(code?: string) {
  return (code && COLORS[code]) || COLORS.default
}

function uid() {
  return Math.random().toString(36).slice(2, 10)
}

export function AnnotationCanvas({
  imageSrc,
  imageWidth,
  imageHeight,
  regions,
  activeTool,
  onRegionAdd,
  onRegionRemove,
  readOnly = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [spaceDown, setSpaceDown] = useState(false)
  const [panStart, setPanStart] = useState<{ x: number; y: number; ox: number; oy: number } | null>(null)

  // bbox draw state
  const [bboxStart, setBboxStart] = useState<{ x: number; y: number } | null>(null)
  const [bboxCurrent, setBboxCurrent] = useState<{ x: number; y: number } | null>(null)

  // polygon draw state
  const [polyPoints, setPolyPoints] = useState<[number, number][]>([])
  const [polyMouse, setPolyMouse] = useState<[number, number] | null>(null)

  // fit image on mount / resize
  useEffect(() => {
    function fit() {
      if (!containerRef.current) return
      const { width, height } = containerRef.current.getBoundingClientRect()
      const s = Math.min(width / imageWidth, height / imageHeight, 1)
      setScale(s)
      setOffset({ x: (width - imageWidth * s) / 2, y: (height - imageHeight * s) / 2 })
    }
    fit()
    const ro = new ResizeObserver(fit)
    if (containerRef.current) ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [imageWidth, imageHeight])

  // keyboard: space = temp pan
  useEffect(() => {
    function onDown(e: KeyboardEvent) { if (e.code === 'Space') { e.preventDefault(); setSpaceDown(true) } }
    function onUp(e: KeyboardEvent) { if (e.code === 'Space') setSpaceDown(false) }
    window.addEventListener('keydown', onDown)
    window.addEventListener('keyup', onUp)
    return () => { window.removeEventListener('keydown', onDown); window.removeEventListener('keyup', onUp) }
  }, [])

  function toImg(clientX: number, clientY: number): [number, number] {
    const rect = containerRef.current!.getBoundingClientRect()
    const cx = clientX - rect.left
    const cy = clientY - rect.top
    const ix = Math.round((cx - offset.x) / scale)
    const iy = Math.round((cy - offset.y) / scale)
    return [
      Math.max(0, Math.min(imageWidth, ix)),
      Math.max(0, Math.min(imageHeight, iy)),
    ]
  }

  function handleWheel(e: React.WheelEvent) {
    e.preventDefault()
    const factor = e.deltaY < 0 ? 1.1 : 0.9
    const rect = containerRef.current!.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    setScale((s) => {
      const ns = Math.max(0.1, Math.min(10, s * factor))
      setOffset((o) => ({
        x: mx - (mx - o.x) * (ns / s),
        y: my - (my - o.y) * (ns / s),
      }))
      return ns
    })
  }

  function handleMouseDown(e: React.MouseEvent) {
    if (readOnly) return
    const isPan = activeTool === 'pan' || spaceDown
    if (isPan) {
      setPanStart({ x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y })
      return
    }
    const [ix, iy] = toImg(e.clientX, e.clientY)

    if (activeTool === 'bbox') {
      setBboxStart({ x: ix, y: iy })
      setBboxCurrent({ x: ix, y: iy })
      return
    }
    if (activeTool === 'point') {
      onRegionAdd?.({
        id: uid(), type: 'POINT', data: { x: ix, y: iy },
      })
      return
    }
    if (activeTool === 'polygon') {
      if (e.detail === 2 && polyPoints.length >= 3) {
        // close polygon on double-click
        onRegionAdd?.({
          id: uid(), type: 'POLYGON', data: { points: polyPoints },
        })
        setPolyPoints([])
        setPolyMouse(null)
        return
      }
      setPolyPoints((pts) => [...pts, [ix, iy]])
    }
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (panStart) {
      setOffset({
        x: panStart.ox + e.clientX - panStart.x,
        y: panStart.oy + e.clientY - panStart.y,
      })
      return
    }
    if (!readOnly && bboxStart) {
      const [ix, iy] = toImg(e.clientX, e.clientY)
      setBboxCurrent({ x: ix, y: iy })
    }
    if (!readOnly && activeTool === 'polygon') {
      const [ix, iy] = toImg(e.clientX, e.clientY)
      setPolyMouse([ix, iy])
    }
  }

  function handleMouseUp(e: React.MouseEvent) {
    if (panStart) { setPanStart(null); return }
    if (!readOnly && bboxStart && bboxCurrent) {
      const x = Math.min(bboxStart.x, bboxCurrent.x)
      const y = Math.min(bboxStart.y, bboxCurrent.y)
      const w = Math.abs(bboxCurrent.x - bboxStart.x)
      const h = Math.abs(bboxCurrent.y - bboxStart.y)
      if (w > 2 && h > 2) {
        onRegionAdd?.({ id: uid(), type: 'BBOX', data: { x, y, w, h } })
      }
      setBboxStart(null)
      setBboxCurrent(null)
    }
  }

  function renderRegion(r: Region) {
    const color = colorFor(r.defectCode)
    const alpha = '99'
    if (r.type === 'BBOX') {
      const { x, y, w, h } = r.data as { x: number; y: number; w: number; h: number }
      return (
        <g key={r.id}>
          <rect x={x} y={y} width={w} height={h}
            fill={color + '22'} stroke={color} strokeWidth={1.5 / scale} />
          {!readOnly && (
            <text x={x + 2} y={y - 2} fill={color} fontSize={11 / scale}>
              {r.defectCode || '?'}
            </text>
          )}
        </g>
      )
    }
    if (r.type === 'POLYGON') {
      const pts = (r.data as { points: [number, number][] }).points
      const pStr = pts.map(([px, py]) => `${px},${py}`).join(' ')
      return (
        <g key={r.id}>
          <polygon points={pStr} fill={color + '22'} stroke={color} strokeWidth={1.5 / scale} />
        </g>
      )
    }
    if (r.type === 'POINT') {
      const { x, y } = r.data as { x: number; y: number }
      return (
        <g key={r.id}>
          <circle cx={x} cy={y} r={5 / scale} fill={color + alpha} stroke={color} strokeWidth={1 / scale} />
        </g>
      )
    }
    if (r.type === 'WHOLE_IMAGE') {
      return (
        <rect key={r.id} x={0} y={0} width={imageWidth} height={imageHeight}
          fill="none" stroke={color} strokeWidth={2 / scale} strokeDasharray={`${8 / scale},${4 / scale}`} />
      )
    }
    return null
  }

  // in-progress bbox ghost
  function renderBboxGhost() {
    if (!bboxStart || !bboxCurrent) return null
    const x = Math.min(bboxStart.x, bboxCurrent.x)
    const y = Math.min(bboxStart.y, bboxCurrent.y)
    const w = Math.abs(bboxCurrent.x - bboxStart.x)
    const h = Math.abs(bboxCurrent.y - bboxStart.y)
    return <rect x={x} y={y} width={w} height={h}
      fill="rgba(250,204,21,0.1)" stroke="#facc15" strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale},${3 / scale}`} />
  }

  // in-progress polygon ghost
  function renderPolyGhost() {
    if (polyPoints.length === 0) return null
    const pts = polyMouse ? [...polyPoints, polyMouse] : polyPoints
    const pStr = pts.map(([px, py]) => `${px},${py}`).join(' ')
    return (
      <>
        <polyline points={pStr} fill="none" stroke="#facc15"
          strokeWidth={1.5 / scale} strokeDasharray={`${5 / scale},${3 / scale}`} />
        {polyPoints.map(([px, py], i) => (
          <circle key={i} cx={px} cy={py} r={4 / scale} fill="#facc15" />
        ))}
      </>
    )
  }

  const isPanCursor = activeTool === 'pan' || spaceDown
  const cursorMap: Record<Tool, string> = {
    bbox: 'crosshair', polygon: 'crosshair', point: 'crosshair', pan: 'grab', select: 'default',
  }
  const cursor = panStart ? 'grabbing' : isPanCursor ? 'grab' : cursorMap[activeTool] || 'default'

  return (
    <div
      ref={containerRef}
      style={{ position: 'relative', overflow: 'hidden', width: '100%', height: '100%',
               background: '#111', cursor, userSelect: 'none' }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => { setPanStart(null); setBboxStart(null); setBboxCurrent(null) }}
    >
      <div style={{
        position: 'absolute',
        left: offset.x, top: offset.y,
        width: imageWidth * scale, height: imageHeight * scale,
        transformOrigin: '0 0',
      }}>
        <img
          src={imageSrc}
          alt="Weld annotation"
          style={{ display: 'block', width: imageWidth * scale, height: imageHeight * scale,
                   imageRendering: scale > 2 ? 'pixelated' : 'auto', pointerEvents: 'none' }}
          draggable={false}
        />
        <svg
          style={{ position: 'absolute', top: 0, left: 0, width: imageWidth * scale,
                   height: imageHeight * scale, pointerEvents: 'none', overflow: 'visible' }}
          viewBox={`0 0 ${imageWidth} ${imageHeight}`}
          preserveAspectRatio="none"
        >
          {regions.map(renderRegion)}
          {renderBboxGhost()}
          {renderPolyGhost()}
        </svg>
      </div>
    </div>
  )
}
