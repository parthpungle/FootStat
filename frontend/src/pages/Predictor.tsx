import { Crosshair, Loader2, MousePointerClick, Sparkles } from 'lucide-react'
import { useRef, useState } from 'react'
import { api } from '../api/client'
import { BODY_PARTS, type BodyPart, type PredictResponse } from '../api/types'
import { Pitch } from '../components/Pitch'
import { Card, EmptyState, ErrorState, PageHeader } from '../components/ui'
import { formatPercent } from '../lib/format'

interface Point {
  x: number
  y: number
}

export function Predictor() {
  const [point, setPoint] = useState<Point | null>(null)
  const [bodyPart, setBodyPart] = useState<BodyPart>('Right Foot')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const requestRef = useRef<AbortController | null>(null)

  // Any input change makes the previous result stale.
  function resetResult() {
    requestRef.current?.abort()
    setLoading(false)
    setResult(null)
    setError(null)
  }

  function selectPoint(x: number, y: number) {
    setPoint({ x, y })
    resetResult()
  }

  async function predict() {
    if (!point) return
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await api.predict({ x: point.x, y: point.y, body_part: bodyPart }, controller.signal)
      setResult(response)
    } catch (err) {
      if (controller.signal.aborted) return
      setError(err instanceof Error ? err.message : 'Prediction failed')
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Shot Predictor"
        description="Pick a shooting position and body part. The trained model on the backend returns the probability of a goal."
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title="Shot location"
          action={
            <span className="text-xs text-slate-400 tabular-nums">
              {point ? `x ${point.x.toFixed(1)}, y ${point.y.toFixed(1)}` : 'Click the pitch'}
            </span>
          }
        >
          <Pitch view="half" onPitchClick={selectPoint} ariaLabel="Attacking half. Click to choose a shot location." className="rounded-lg">
            {point && (
              <g pointerEvents="none">
                {/* Lines to each post show the shooting angle the model uses. */}
                <line x1={point.x} y1={point.y} x2={120} y2={36} stroke="var(--color-xg)" strokeDasharray="4 3" strokeWidth={1.25} vectorEffect="non-scaling-stroke" />
                <line x1={point.x} y1={point.y} x2={120} y2={44} stroke="var(--color-xg)" strokeDasharray="4 3" strokeWidth={1.25} vectorEffect="non-scaling-stroke" />
                <circle cx={point.x} cy={point.y} r={1.6} fill="var(--color-xg)" stroke="#fff" strokeWidth={2} vectorEffect="non-scaling-stroke" />
              </g>
            )}
          </Pitch>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
            <MousePointerClick className="h-3.5 w-3.5" /> Attacking towards the goal at the top. Coordinates use the StatsBomb 120 × 80 pitch.
          </p>
        </Card>

        <div className="flex flex-col gap-6">
          <Card title="Shot settings">
            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-1 text-xs text-slate-400">
                Body part
                <select
                  value={bodyPart}
                  onChange={(e) => {
                    setBodyPart(e.target.value as BodyPart)
                    resetResult()
                  }}
                  className="rounded-lg border border-navy-600 bg-navy-850 px-3 py-2 text-sm text-slate-100"
                >
                  {BODY_PARTS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </label>
              <button
                type="button"
                onClick={predict}
                disabled={!point || loading}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-goal px-4 py-2.5 text-sm font-semibold text-navy-950 hover:bg-green-400 disabled:cursor-not-allowed disabled:bg-navy-700 disabled:text-slate-500"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                {loading ? 'Predicting…' : 'Predict'}
              </button>
              {!point && <p className="text-xs text-slate-500">Select a location on the pitch first.</p>}
            </div>
          </Card>

          <Card title="Prediction">
            {error && <ErrorState message={error} onRetry={predict} />}
            {loading && <p className="flex items-center gap-2 py-6 text-sm text-slate-400" role="status"><Loader2 className="h-4 w-4 animate-spin" /> Asking the model…</p>}
            {!loading && !error && !result && (
              <EmptyState title="No prediction yet">
                <span className="inline-flex items-center gap-1"><Crosshair className="h-4 w-4" /> Choose a spot and press Predict.</span>
              </EmptyState>
            )}
            {result && point && <PredictionResult result={result} point={point} bodyPart={bodyPart} />}
          </Card>
        </div>
      </div>
    </>
  )
}

function PredictionResult({ result, point, bodyPart }: { result: PredictResponse; point: Point; bodyPart: BodyPart }) {
  const pct = Math.min(100, Math.max(0, result.predicted_xg * 100))
  return (
    <div aria-live="polite">
      <p className="text-xs tracking-wide text-slate-400 uppercase">Goal probability</p>
      <p className="mt-1 text-5xl font-semibold text-goal tabular-nums">{formatPercent(result.predicted_xg)}</p>
      <p className="mt-1 text-sm text-slate-300">
        xG <span className="font-semibold tabular-nums text-xg">{result.predicted_xg.toFixed(3)}</span>
      </p>
      <div className="mt-4 h-2 rounded-full bg-navy-700" aria-hidden>
        <div className="h-full rounded-full bg-goal" style={{ width: `${pct}%` }} />
      </div>
      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-navy-850 p-3">
          <dt className="text-xs text-slate-500">Distance to goal</dt>
          <dd className="mt-0.5 text-slate-100 tabular-nums">{result.distance.toFixed(1)}</dd>
        </div>
        <div className="rounded-lg bg-navy-850 p-3">
          <dt className="text-xs text-slate-500">Shooting angle</dt>
          <dd className="mt-0.5 text-slate-100 tabular-nums">{result.angle_degrees.toFixed(1)}°</dd>
        </div>
      </dl>
      <p className="mt-4 text-xs text-slate-500">
        {bodyPart} shot from ({point.x.toFixed(1)}, {point.y.toFixed(1)}) · model <code>{result.model_version}</code>.
        Shot type is not a model input, so penalties are under-estimated.
      </p>
    </div>
  )
}
