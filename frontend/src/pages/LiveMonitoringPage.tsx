import { useState, useEffect, useRef } from 'react'

type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'
type SourceType = 'webcam' | 'rtsp' | 'file'

interface WsMessage {
  type: string
  payload: Record<string, unknown>
}

export function LiveMonitoringPage() {
  const [sourceType, setSourceType] = useState<SourceType>('webcam')
  const [rtspUrl, setRtspUrl] = useState('')
  const [connState, setConnState] = useState<ConnectionState>('disconnected')
  const [messages, setMessages] = useState<WsMessage[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    return () => {
      wsRef.current?.close()
    }
  }, [])

  function connect() {
    if (wsRef.current) wsRef.current.close()
    setMessages([])
    setConnState('connecting')

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host
    const ws = new WebSocket(`${proto}//${host}/api/v1/vision/live/ws`)
    wsRef.current = ws

    ws.onopen = () => {
      setConnState('connected')
      ws.send(JSON.stringify({ action: 'subscribe', source_id: sourceType }))
    }
    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data)
        setMessages((prev) => [msg, ...prev].slice(0, 50))
      } catch { /* ignore malformed */ }
    }
    ws.onerror = () => setConnState('error')
    ws.onclose = () => {
      if (connState !== 'error') setConnState('disconnected')
    }
  }

  function disconnect() {
    wsRef.current?.close()
    setConnState('disconnected')
  }

  const card: React.CSSProperties = {
    background: 'var(--card-bg, #f9fafb)',
    border: '1px solid var(--border, #e5e7eb)',
    borderRadius: 8,
    padding: '16px 20px',
    marginBottom: 16,
  }
  const label: React.CSSProperties = {
    display: 'block',
    fontSize: 12,
    fontWeight: 600,
    color: 'var(--muted, #6b7280)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: 4,
  }
  const input: React.CSSProperties = {
    width: '100%',
    padding: '7px 10px',
    border: '1px solid var(--border, #d1d5db)',
    borderRadius: 6,
    fontSize: 14,
    boxSizing: 'border-box',
  }

  const stateColor: Record<ConnectionState, string> = {
    disconnected: '#6b7280',
    connecting:   '#d97706',
    connected:    '#16a34a',
    error:        '#dc2626',
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '0 4px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Live Monitoring</h2>

      {/* Framework disclaimer — must be visible */}
      <div style={{
        ...card,
        background: '#fffbeb',
        border: '1px solid #fcd34d',
        marginBottom: 20,
      }}>
        <div style={{ fontWeight: 700, marginBottom: 6, color: '#92400e' }}>
          ⚠ Framework Only — Not Production-Ready
        </div>
        <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: 13, color: '#78350f', lineHeight: 1.6 }}>
          <li>No trained weld-cycle segmentation model is loaded.</li>
          <li>No validated capture adapter is registered.</li>
          <li>Standard 30-FPS cameras cannot capture high-speed expulsion events.</li>
          <li>End-to-end latency and sustained FPS have not been characterised.</li>
          <li>Hardware and software validation is required before production use.</li>
          <li>No automatic PLC actuation is performed by this interface.</li>
        </ul>
      </div>

      {/* Source selector */}
      <div style={{ ...card }}>
        <div style={{ fontWeight: 700, marginBottom: 12 }}>Capture Source</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
          <div>
            <label style={label}>Source Type</label>
            <select
              style={input}
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value as SourceType)}
            >
              <option value="webcam">USB Webcam</option>
              <option value="rtsp">RTSP Stream</option>
              <option value="file">Video File</option>
            </select>
          </div>
          {sourceType === 'rtsp' && (
            <div>
              <label style={label}>RTSP URL</label>
              <input
                style={input}
                type="text"
                placeholder="rtsp://user:pass@192.168.1.100:554/stream"
                value={rtspUrl}
                onChange={(e) => setRtspUrl(e.target.value)}
              />
            </div>
          )}
          {sourceType === 'file' && (
            <div>
              <label style={label}>Video File</label>
              <input style={input} type="file" accept="video/*" disabled />
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
                File upload for video not yet implemented in this release.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Connection control */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20 }}>
        <button
          onClick={connect}
          disabled={connState === 'connecting' || connState === 'connected'}
          style={{
            padding: '9px 20px',
            background: connState === 'connected' ? '#9ca3af' : '#3b82f6',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 14,
            cursor: connState === 'connecting' || connState === 'connected' ? 'not-allowed' : 'pointer',
          }}
        >
          {connState === 'connecting' ? 'Connecting…' : 'Connect'}
        </button>
        <button
          onClick={disconnect}
          disabled={connState === 'disconnected'}
          style={{
            padding: '9px 20px',
            background: connState !== 'disconnected' ? '#dc2626' : '#9ca3af',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            fontSize: 14,
            cursor: connState !== 'disconnected' ? 'pointer' : 'not-allowed',
          }}
        >
          Disconnect
        </button>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 14,
          color: stateColor[connState],
          fontWeight: 600,
        }}>
          <span style={{
            display: 'inline-block',
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: stateColor[connState],
          }} />
          {connState.toUpperCase()}
        </div>
      </div>

      {/* Stream preview placeholder */}
      <div style={{
        ...card,
        background: '#111827',
        minHeight: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 16,
      }}>
        {connState === 'connected' ? (
          <div style={{ color: '#6b7280', textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
            <div style={{ fontSize: 13 }}>
              Stream preview requires a validated capture adapter. Framework connected.
            </div>
          </div>
        ) : (
          <div style={{ color: '#6b7280', textAlign: 'center' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
            <div style={{ fontSize: 13 }}>Stream preview — connect to begin</div>
          </div>
        )}
      </div>

      {/* Live metrics row (all N/A until adapter is wired) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'FPS Actual', value: '—' },
          { label: 'FPS Target', value: '—' },
          { label: 'Frames Dropped', value: '—' },
          { label: 'Inference Latency', value: '—' },
          { label: 'Active Welds', value: '—' },
          { label: 'Alerts', value: '—' },
        ].map(({ label: lbl, value }) => (
          <div key={lbl} style={{ ...card, padding: '12px 16px', textAlign: 'center' }}>
            <div style={{ fontSize: 11, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>{lbl}</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
          </div>
        ))}
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
                  color: m.type === 'alert' ? '#dc2626' : m.type === 'error' ? '#b45309' : '#374151',
                  fontWeight: m.type === 'alert' ? 700 : 400,
                }}>
                  [{m.type.toUpperCase()}]{' '}
                </span>
                {JSON.stringify(m.payload)}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Per-weld traceability placeholder */}
      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>Per-Weld Traceability</div>
        <div style={{ fontSize: 13, color: '#6b7280' }}>
          Weld records will appear here once a validated capture adapter and
          weld-cycle segmentation model are connected.
        </div>
      </div>
    </div>
  )
}
