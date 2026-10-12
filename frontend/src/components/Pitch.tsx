import { useRef, type MouseEvent, type ReactNode } from 'react'

// StatsBomb coordinates: 120 x 80, origin top-left, y increasing downward,
// attacking goal at x = 120. The SVG uses the same units, so children can
// place elements at raw data coordinates with no conversion.
export const PITCH_LENGTH = 120
export const PITCH_WIDTH = 80

// full: horizontal, attacking left to right.
// half: attacking half only (every shot in the dataset has x >= 59), turned
//   so the goal is at the top. Screen (X, Y) = (y, 120 - x), which keeps
//   StatsBomb y = 0 on the attacker's left.
const VIEWS = {
  full: { viewBox: '-3 -3 126 86', transform: undefined },
  half: { viewBox: '-3 -3 86 66', transform: 'matrix(0 -1 1 0 0 120)' },
} as const

export type PitchView = keyof typeof VIEWS

interface PitchProps {
  view?: PitchView
  /** Called with pitch coordinates (rounded to 0.1) when the pitch is clicked. */
  onPitchClick?: (x: number, y: number) => void
  children?: ReactNode
  className?: string
  ariaLabel?: string
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export function Pitch({ view = 'half', onPitchClick, children, className = '', ariaLabel }: PitchProps) {
  const pitchRef = useRef<SVGGElement>(null)
  const { viewBox, transform } = VIEWS[view]

  function handleClick(event: MouseEvent<SVGSVGElement>) {
    // The group's CTM includes the view rotation, so its inverse maps the
    // click straight back to StatsBomb coordinates.
    const ctm = pitchRef.current?.getScreenCTM()
    if (!ctm || !onPitchClick) return
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse())
    const minX = view === 'half' ? PITCH_LENGTH / 2 : 0
    const x = Math.round(clamp(point.x, minX, PITCH_LENGTH) * 10) / 10
    const y = Math.round(clamp(point.y, 0, PITCH_WIDTH) * 10) / 10
    onPitchClick(x, y)
  }

  const line = {
    fill: 'none',
    stroke: 'var(--color-pitch-line)',
    strokeWidth: 1.5,
    vectorEffect: 'non-scaling-stroke' as const,
  }

  return (
    <svg
      viewBox={viewBox}
      className={`block w-full select-none ${onPitchClick ? 'cursor-crosshair' : ''} ${className}`}
      onClick={onPitchClick ? handleClick : undefined}
      role="img"
      aria-label={ariaLabel ?? 'Football pitch'}
    >
      <g ref={pitchRef} transform={transform}>
      <rect x={-3} y={-3} width={126} height={86} fill="var(--color-pitch-surround)" />
      <rect x={0} y={0} width={PITCH_LENGTH} height={PITCH_WIDTH} fill="var(--color-pitch)" />

      {/* Outline and halfway line */}
      <rect x={0} y={0} width={PITCH_LENGTH} height={PITCH_WIDTH} {...line} />
      <line x1={60} y1={0} x2={60} y2={80} {...line} />
      <circle cx={60} cy={40} r={10} {...line} />
      <circle cx={60} cy={40} r={0.5} fill="var(--color-pitch-line)" />

      {/* Left end */}
      <rect x={0} y={18} width={18} height={44} {...line} />
      <rect x={0} y={30} width={6} height={20} {...line} />
      <rect x={-2} y={36} width={2} height={8} {...line} />
      <circle cx={12} cy={40} r={0.5} fill="var(--color-pitch-line)" />
      <path d="M 18 32 A 10 10 0 0 1 18 48" {...line} />

      {/* Right (attacking) end: penalty area 102-120 x 18-62, six-yard box, goal y 36-44 */}
      <rect x={102} y={18} width={18} height={44} {...line} />
      <rect x={114} y={30} width={6} height={20} {...line} />
      <rect x={120} y={36} width={2} height={8} {...line} />
      <circle cx={108} cy={40} r={0.5} fill="var(--color-pitch-line)" />
      <path d="M 102 32 A 10 10 0 0 0 102 48" {...line} />

      {children}
      </g>
    </svg>
  )
}
