import { useState, useEffect, useRef, useCallback } from 'react'
import { ModuleReadButton } from '../components/ModuleReadPanel'

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'
type SourceType = 'webcam' | 'rtsp' | 'file'

interface WsMessage {
  type: string
  payload: Record<string, unknown>
}

interface LiveMetrics {
  source_id?: string
  fps_actual: number | null
  fps_nominal: number | null
  frames_total: number
  frames_dropped: number
  last_frame_age_ms: number | null
  queue_depth: number
  worker_state: string
  error_message?: string | null
}

interface MotionEvent {
  event_type: 'MOTION_DETECTED' | 'IDLE' | 'WELD_CYCLE_BOUNDARY'
  timestamp_ms: number
  frame_index: number
  magnitude: number
  threshold: number
  is_above_threshold: boolean
  source_id: string
  note: string
}

interface WeldWindow {
  record_id: string
  source_id: string
  start_timestamp_ms: number
  end_timestamp_ms: number
  duration_ms: number
  frame_count: number
  peak_magnitude: number
  mean_magnitude: number
  state: string
  note: string
}

interface FramePayload {
  source_id: string
  frame_b64: string
  frame_index: number
  timestamp_ms: number
  width: number
  height: number
}

const VITE_API = (import.meta.env.VITE_API_URL as string) || ''

function getWsHost(): string {
  if (VITE_API) {
    try { return new URL(VITE_API).host } catch { /* fall through */ }
  }
  return window.location.host
}

function getAuthToken(): string {
  try {
    return localStorage.getItem('access_token') || ''
  } catch {
    return ''
  }
}

export function LiveMonitoringPage() {
  const [sourceType, setSourceType] = useState<SourceType>('webcam')
  const [rtspUrl, setRtspUrl] = useState('')
  const [filePath, setFilePath] = useState('clip.mp4')
  const [sourceId, setSourceId] = useState('webcam://device/0')
  const [connState, setConnState] = useState<ConnectionState>('disconnected')
  const [messages, setMessages] = useState<WsMessage[]>([])
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null)
  const [lastFrame, setLastFrame] = useState<FramePayload | null>(null)
  const [motionEvents, setMotionEvents] = useState<MotionEvent[]>([])
  const [weldWindows, setWeldWindows] = useState<WeldWindow[]>([])
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => () => { wsRef.current?.close() }, [])

  const addLog = useCallback((msg: WsMessage) => {
    setMessages(prev => [msg, ...prev].slice(0, 50))
  }, [])

  function connect() {
    if (wsRef.current) wsRef.current.close()
    setMessages([])
    setMetrics(null)
    setLastFrame(null)
    setMotionEvents([])
    setWeldWindows([])
    setErrorMsg(null)
    setConnState('connecting')

    const token = getAuthToken()
    if (!token) {
      setErrorMsg('No auth token found in localStorage. Log in first.')
      setConnState('error')
      return
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${getWsHost()}/api/v1/vision/live/ws`)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ action: 'auth', token }))
    }

    ws.onmessage = (e) => {
      let msg: WsMessage
      try { msg = JSON.parse(e.data) } catch { return }
      addLog(msg)

      switch (msg.type) {
        case 'auth_ok':
          setConnState('connected')
          ws.send(JSON.stringify({ action: 'subscribe', source_id: sourceId }))
          break
        case 'metrics':
          setMetrics(msg.payload as unknown as LiveMetrics)
          break
        case 'frame':
          setLastFrame(msg.payload as unknown as FramePayload)
          break
        case 'event': {
          const ev = msg.payload as unknown as MotionEvent
          setMotionEvents(prev => [ev, ...prev].slice(0, 30))
          break
        }
        case 'weld_window': {
          const ww = msg.payload as unknown as WeldWindow
          setWeldWindows(prev => [ww, ...prev].slice(0, 20))
          break
        }
        case 'error':
          setErrorMsg(String((msg.payload as Record<string, unknown>).message ?? 'Unknown error'))
          break
      }
    }

    ws.onerror = () => {
      setConnState('error')
      setErrorMsg('WebSocket connection error.')
    }
    ws.onclose = (ev) => {
      if (ev.code === 4001) setErrorMsg(`Authentication failed (${ev.reason || 'Invalid token'})`)
      else if (ev.code === 4029) setErrorMsg('Server at session limit — try again shortly.')
      setConnState('disconnected')
    }
  }

  function disconnect() {
    wsRef.current?.close()
    setConnState('disconnected')
  }

  // ── Styles ────────────────────────────────────────────────────────────────

  const card: React.CSSProperties = {
    background: 'var(--card-bg, #f9fafb)',
    border: '1px solid var(--border, #e5e7eb)',
    borderRadius: 8,
    padding: '16px 20px',
    marginBottom: 16,
  }
  const lbl: React.CSSProperties = {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: 'var(--muted, #6b7280)', textTransform: 'uppercase',
    letterSpacing: '0.05em', marginBottom: 4,
  }
  const inp: React.CSSProperties = {
    width: '100%', padding: '7px 10px',
    border: '1px solid var(--border, #d1d5db)', borderRadius: 6,
    fontSize: 14, boxSizing: 'border-box',
  }

  const stateColor: Record<ConnectionState, string> = {
    disconnected: '#6b7280', connecting: '#d97706',
    connected: '#16a34a', error: '#dc2626',
  }

  function fmt(v: number | null | undefined, unit: string = ''): string {
    if (v == null) return '—'
    return `${v}${unit}`
  }

  const metricTiles = [
    { label: 'FPS Actual',   value: fmt(metrics?.fps_actual, '') },
    { label: 'FPS Nominal',  value: fmt(metrics?.fps_nominal, '') },
    { label: 'Frames Total', value: fmt(metrics?.frames_total) },
    { label: 'Dropped',      value: fmt(metrics?.frames_dropped) },
    { label: 'Frame Age',    value: fmt(metrics?.last_frame_age_ms, ' ms') },
    { label: 'Queue',        value: fmt(metrics?.queue_depth) },
  ]

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '0 4px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Live Monitoring</h2>
        <ModuleReadButton moduleId="live" />
      </div>

      {/* Framework disclaimer */}
      <div style={{ ...card, background: '#fffbeb', border: '1px solid #fcd34d', marginBottom: 20 }}>
        <div style={{ fontWeight: 700, marginBottom: 6, color: '#92400e' }}>
          ⚠ Phase 2 — Frame acquisition active, AI inference not loaded
        </div>
        <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#78350f', lineHeight: 1.6 }}>
          <li>Motion events are pixel-level frame differences only — not weld quality assessments.</li>
          <li>No weld-cycle segmentation model is loaded; weld windows are heuristic only.</li>
          <li>Standard 30-FPS cameras cannot capture high-speed expulsion events.</li>
          <li>End-to-end latency and sustained FPS have not been hardware-validated.</li>
          <li>No automatic PLC actuation is performed by this interface.</li>
        </ul>
      </div>

      {/* File Replay banner — shown when file source is selected */}
      {sourceType === 'file' && (
        <div style={{ ...card, background: '#eff6ff', border: '1px solid #93c5fd', marginBottom: 16 }}>
          <div style={{ fontWeight: 700, marginBottom: 6, color: '#1d4ed8' }}>
            FILE REPLAY MODE
          </div>
          <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#1e40af', lineHeight: 1.6 }}>
            <li>Source will be treated as a local video file on the backend host, not a live camera.</li>
            <li>Replay FPS reflects file decode speed — not industrial real-time performance.</li>
            <li>Analysis status: <strong>NOT_EVALUATED</strong> — no trained inference model is loaded.</li>
            <li>Motion events are pixel-level frame differences only; weld windows are heuristic only.</li>
            <li>Provide the absolute path accessible from the backend process, or a relative path from its working directory.</li>
          </ul>
        </div>
      )}

      {/* Error banner */}
      {errorMsg && (
        <div style={{ ...card, background: '#fef2f2', border: '1px solid #fca5a5', marginBottom: 16 }}>
          <span style={{ color: '#dc2626', fontWeight: 600 }}>⚠ {errorMsg}</span>
        </div>
      )}

      {/* Source config */}
      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 12 }}>Capture Source</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
          <div>
            <label style={lbl}>Source Type</label>
            <select style={inp} value={sourceType}
              onChange={(e) => {
                const t = e.target.value as SourceType
                setSourceType(t)
                if (t === 'webcam') setSourceId('webcam://device/0')
                else if (t === 'file') setSourceId(`file://${filePath}`)
              }}>
              <option value="webcam">USB Webcam</option>
              <option value="rtsp">RTSP Stream</option>
              <option value="file">Video File (Replay)</option>
            </select>
          </div>
          {sourceType === 'rtsp' && (
            <div>
              <label style={lbl}>RTSP URL</label>
              <input style={inp} type="text"
                placeholder="rtsp://user:pass@192.168.1.100:554/stream"
                value={rtspUrl}
                onChange={(e) => { setRtspUrl(e.target.value); setSourceId(e.target.value) }}
              />
            </div>
          )}
          {sourceType === 'file' && (
            <div>
              <label style={lbl}>Video file path</label>
              <input style={inp} type="text"
                placeholder="clip.mp4 or /absolute/path/to/video.mp4"
                value={filePath}
                onChange={(e) => {
                  setFilePath(e.target.value)
                  setSourceId(`file://${e.target.value}`)
                }}
              />
            </div>
          )}
          <div>
            <label style={lbl}>Source ID (sent to server)</label>
            <input style={{ ...inp, color: '#6b7280' }} type="text" value={sourceId}
              onChange={e => setSourceId(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Connection control */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20 }}>
        <button onClick={connect}
          disabled={connState === 'connecting' || connState === 'connected'}
          style={{
            padding: '9px 20px',
            background: connState === 'connected' ? '#9ca3af' : '#3b82f6',
            color: '#fff', border: 'none', borderRadius: 6,
            fontWeight: 600, fontSize: 14,
            cursor: connState === 'connecting' || connState === 'connected' ? 'not-allowed' : 'pointer',
          }}>
          {connState === 'connecting' ? 'Connecting…' : 'Connect'}
        </button>
        <button onClick={disconnect} disabled={connState === 'disconnected'}
          style={{
            padding: '9px 20px',
            background: connState !== 'disconnected' ? '#dc2626' : '#9ca3af',
            color: '#fff', border: 'none', borderRadius: 6,
            fontWeight: 600, fontSize: 14,
            cursor: connState !== 'disconnected' ? 'pointer' : 'not-allowed',
          }}>
          Disconnect
        </button>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 14, color: stateColor[connState], fontWeight: 600,
        }}>
          <span style={{
            display: 'inline-block', width: 8, height: 8,
            borderRadius: '50%', background: stateColor[connState],
          }} />
          {connState.toUpperCase()}
          {metrics?.worker_state && connState === 'connected' && (
            <span style={{ color: '#6b7280', fontWeight: 400, fontSize: 12 }}>
              · worker: {metrics.worker_state}
            </span>
          )}
        </div>
      </div>

      {/* Stream preview */}
      <div style={{
        ...card, background: '#111827', minHeight: 200,
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16,
      }}>
        {lastFrame ? (
          <div style={{ width: '100%', textAlign: 'center' }}>
            <img
              ref={imgRef}
              src={`data:image/jpeg;base64,${lastFrame.frame_b64}`}
              alt="Live frame"
              style={{ maxWidth: '100%', maxHeight: 360, borderRadius: 4 }}
            />
            <div style={{ color: '#6b7280', fontSize: 11, marginTop: 6 }}>
              Frame #{lastFrame.frame_index} · {lastFrame.width}×{lastFrame.height}
              · age: {fmt(metrics?.last_frame_age_ms, ' ms')}
            </div>
          </div>
        ) : (
          <div style={{ color: '#6b7280', textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
            <div style={{ fontSize: 13 }}>
              {connState === 'connected'
                ? 'Waiting for frames from source…'
                : 'Connect to begin.'}
            </div>
          </div>
        )}
      </div>

      {/* Live metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 12, marginBottom: 20 }}>
        {metricTiles.map(({ label, value }) => (
          <div key={label} style={{ ...card, padding: '12px 16px', textAlign: 'center', marginBottom: 0 }}>
            <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
              {label}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* Motion events */}
      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>
          Motion Events ({motionEvents.length})
          <span style={{ fontWeight: 400, fontSize: 11, color: '#6b7280', marginLeft: 8 }}>
            Pixel-level frame differences — not weld quality
          </span>
        </div>
        {motionEvents.length === 0 ? (
          <div style={{ fontSize: 13, color: '#6b7280' }}>
            {connState === 'connected' ? 'Waiting for events…' : 'Connect and subscribe to see events.'}
          </div>
        ) : (
          <div style={{ maxHeight: 180, overflowY: 'auto', fontSize: 12, fontFamily: 'monospace' }}>
            {motionEvents.map((ev, i) => (
              <div key={i} style={{
                padding: '3px 0', borderBottom: '1px solid #f3f4f6',
                color: ev.event_type === 'MOTION_DETECTED' ? '#d97706' : '#6b7280',
              }}>
                [{ev.event_type}] frame={ev.frame_index} mag={ev.magnitude.toFixed(2)} thr={ev.threshold}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Weld windows */}
      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>
          Motion Windows ({weldWindows.length})
          <span style={{ fontWeight: 400, fontSize: 11, color: '#6b7280', marginLeft: 8 }}>
            Heuristic — NOT a quality result
          </span>
        </div>
        {weldWindows.length === 0 ? (
          <div style={{ fontSize: 13, color: '#6b7280' }}>
            No motion windows detected yet.
          </div>
        ) : (
          <div style={{ maxHeight: 200, overflowY: 'auto' }}>
            {weldWindows.map((w) => (
              <div key={w.record_id} style={{
                ...card, marginBottom: 8, padding: '10px 14px',
                background: 'var(--card-bg2, #f1f5f9)',
              }}>
                <div style={{ fontSize: 12, fontFamily: 'monospace', color: '#374151' }}>
                  Frames: {w.frame_count} · Duration: {w.duration_ms.toFixed(0)} ms ·
                  Peak: {w.peak_magnitude.toFixed(2)} · Mean: {w.mean_magnitude.toFixed(2)}
                </div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>{w.note}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Event log */}
      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 10 }}>
          WebSocket Event Log ({messages.length})
        </div>
        {messages.length === 0 ? (
          <div style={{ fontSize: 13, color: '#6b7280' }}>
            {connState === 'connected' ? 'Waiting for messages…' : 'Connect to see events.'}
          </div>
        ) : (
          <div style={{ maxHeight: 300, overflowY: 'auto', fontSize: 12, fontFamily: 'monospace' }}>
            {messages.map((m, i) => (
              <div key={i} style={{ padding: '3px 0', borderBottom: '1px solid #f3f4f6' }}>
                <span style={{
                  color: m.type === 'error' ? '#dc2626' : m.type === 'weld_window' ? '#7c3aed' : '#374151',
                  fontWeight: m.type === 'error' ? 700 : 400,
                }}>
                  [{m.type.toUpperCase()}]{' '}
                </span>
                {m.type === 'frame' ? '(frame data omitted)' : JSON.stringify(m.payload).slice(0, 120)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
