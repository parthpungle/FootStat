import { Filter, MousePointerClick, X } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { MatchXg, OutcomeFilter, ShotRecord, ShotsQuery } from '../api/types'
import { Pitch } from '../components/Pitch'
import { Card, EmptyState, ErrorState, Legend, LoadingState, PageHeader } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { formatXg } from '../lib/format'

// The API caps a page at 2000; the World Cup dataset has fewer shots than that.
const SHOT_LIMIT = 2000
const MIN_RADIUS = 0.55 // pitch units, keeps low-xG shots visible and clickable
const RADIUS_SCALE = 2.2
const MIN_HIT_RADIUS = 1.1 // clickable area, larger than the smallest visible marker

const markerRadius = (xg: number) => Math.max(MIN_RADIUS, Math.sqrt(xg) * RADIUS_SCALE)

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

export function ShotMap() {
  const [team, setTeam] = useState('')
  const [playerInput, setPlayerInput] = useState('')
  const [outcome, setOutcome] = useState<OutcomeFilter | ''>('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const player = useDebounced(playerInput.trim(), 300)

  // Unfiltered shots supply the filter options; overview supplies match labels.
  const allShots = useApi((signal) => api.shots({ limit: SHOT_LIMIT }, signal), 'all-shots')
  const overview = useApi((signal) => api.overview(signal), 'overview')
  const query: ShotsQuery = { team: team || undefined, player: player || undefined, outcome: outcome || undefined, limit: SHOT_LIMIT }
  const shots = useApi((signal) => api.shots(query, signal), JSON.stringify(query))

  const teams = useMemo(
    () => [...new Set((allShots.data?.items ?? []).map((s) => s.team_name).filter((t): t is string => !!t))].sort(),
    [allShots.data],
  )
  const players = useMemo(
    () => [...new Set((allShots.data?.items ?? [])
      .filter((s) => !team || s.team_name === team)
      .map((s) => s.player_name)
      .filter((p): p is string => !!p))].sort(),
    [allShots.data, team],
  )
  const matches = useMemo(
    () => new Map((overview.data?.by_match ?? []).map((m) => [m.match_id, m])),
    [overview.data],
  )

  const items = useMemo(() => shots.data?.items ?? [], [shots.data])
  const selected = items.find((s) => s.event_id === selectedId) ?? null
  // Draw big markers first so small ones stay clickable; goals on top of misses.
  const ordered = useMemo(
    () => [...items].sort((a, b) => Number(a.goal) - Number(b.goal) || b.predicted_xg - a.predicted_xg),
    [items],
  )
  const goals = items.filter((s) => s.goal).length
  const xgSum = items.reduce((sum, s) => sum + s.predicted_xg, 0)
  const filtersActive = Boolean(team || playerInput || outcome)

  function clearFilters() {
    setTeam('')
    setPlayerInput('')
    setOutcome('')
  }

  return (
    <>
      <PageHeader title="Shot Map" description="Every historical shot at its recorded location. Click a marker for details." />

      <Card className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <Filter className="hidden h-4 w-4 text-slate-500 md:mb-2.5 md:block" />
          <label className="flex flex-1 flex-col gap-1 text-xs text-slate-400">
            Team
            <select
              value={team}
              onChange={(e) => setTeam(e.target.value)}
              className="rounded-lg border border-navy-600 bg-navy-850 px-3 py-2 text-sm text-slate-100"
            >
              <option value="">All teams</option>
              {teams.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-slate-400">
            Player
            <input
              type="search"
              value={playerInput}
              onChange={(e) => setPlayerInput(e.target.value)}
              placeholder="Search player name…"
              list="player-options"
              className="rounded-lg border border-navy-600 bg-navy-850 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
            />
            <datalist id="player-options">
              {players.map((p) => <option key={p} value={p} />)}
            </datalist>
          </label>
          <div className="flex flex-col gap-1 text-xs text-slate-400">
            Outcome
            <div className="flex rounded-lg border border-navy-600 bg-navy-850 p-0.5" role="group" aria-label="Outcome filter">
              {([['', 'All'], ['goal', 'Goals'], ['no_goal', 'No goal']] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setOutcome(value)}
                  aria-pressed={outcome === value}
                  className={`flex-1 rounded-md px-3 py-1.5 text-sm whitespace-nowrap ${
                    outcome === value
                      ? value === 'goal' ? 'bg-goal/20 text-goal' : value === 'no_goal' ? 'bg-miss/20 text-red-300' : 'bg-navy-600 text-slate-100'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {filtersActive && (
            <button type="button" onClick={clearFilters} className="inline-flex items-center gap-1 self-start rounded-md px-2 py-2 text-sm text-slate-400 hover:text-slate-100 md:self-end">
              <X className="h-4 w-4" /> Clear
            </button>
          )}
        </div>
      </Card>

      {shots.error && <div className="mb-6"><ErrorState message={shots.error} onRetry={shots.reload} /></div>}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card
          className="xl:col-span-2"
          title={shots.data ? `${items.length} shots · ${goals} goals · ${xgSum.toFixed(1)} xG` : 'Shots'}
          action={<Legend />}
        >
          {shots.loading && !shots.data && <LoadingState label="Loading shots…" />}
          {shots.data && (
            <div className="relative">
              <Pitch view="half" ariaLabel="Shot map of the attacking half" className={`rounded-lg ${shots.loading ? 'opacity-60' : ''}`}>
                {ordered.map((s) => (
                  <ShotMarker key={s.event_id} shot={s} selected={s.event_id === selectedId} onSelect={setSelectedId} />
                ))}
              </Pitch>
              {items.length === 0 && !shots.loading && (
                <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-navy-950/70">
                  <EmptyState title="No shots match these filters">
                    Try a different team, player or outcome.{' '}
                    <button type="button" onClick={clearFilters} className="text-goal underline-offset-2 hover:underline">Clear filters</button>
                  </EmptyState>
                </div>
              )}
            </div>
          )}
          {shots.data && shots.data.total > items.length && (
            <p className="mt-3 text-xs text-slate-500">Showing the first {items.length} of {shots.data.total} matching shots.</p>
          )}
        </Card>

        <Card title="Shot details">
          {selected ? (
            <ShotDetails shot={selected} match={matches.get(selected.match_id)} onClose={() => setSelectedId(null)} />
          ) : (
            <EmptyState title="No shot selected">
              <span className="inline-flex items-center gap-1"><MousePointerClick className="h-4 w-4" /> Click a marker on the pitch to see its details.</span>
            </EmptyState>
          )}
        </Card>
      </div>
    </>
  )
}

function ShotMarker({ shot, selected, onSelect }: { shot: ShotRecord; selected: boolean; onSelect: (id: string) => void }) {
  const color = shot.goal ? 'var(--color-goal)' : 'var(--color-miss)'
  const radius = markerRadius(shot.predicted_xg)
  return (
    <g
      className="cursor-pointer focus:outline-none"
      role="button"
      tabIndex={0}
      aria-label={`${shot.player_name ?? 'Unknown player'}, ${shot.shot_outcome}, xG ${shot.predicted_xg.toFixed(2)}`}
      onClick={(e) => {
        e.stopPropagation()
        onSelect(shot.event_id)
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(shot.event_id)
        }
      }}
    >
      <title>{`${shot.player_name ?? 'Unknown'} · ${shot.shot_outcome} · xG ${shot.predicted_xg.toFixed(2)}`}</title>
      {/* Invisible, slightly larger hit area so small low-xG markers are easy to click. */}
      <circle cx={shot.x} cy={shot.y} r={Math.max(radius, MIN_HIT_RADIUS)} fill="transparent" />
      <circle
        cx={shot.x}
        cy={shot.y}
        r={radius}
        fill={color}
        fillOpacity={selected ? 0.95 : 0.55}
        stroke={selected ? '#fff' : color}
        strokeWidth={selected ? 2 : 1}
        vectorEffect="non-scaling-stroke"
        data-shot-marker
        data-goal={shot.goal}
      />
    </g>
  )
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-navy-700/60 py-2 text-sm last:border-0">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-100">{children}</dd>
    </div>
  )
}

function ShotDetails({ shot, match, onClose }: { shot: ShotRecord; match?: MatchXg; onClose: () => void }) {
  const matchLabel = match?.home_team && match?.away_team
    ? `${match.home_team} vs ${match.away_team}`
    : `Match ${shot.match_id}`

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-lg font-semibold text-slate-50">{shot.player_name ?? 'Unknown player'}</p>
          <p className="text-sm text-slate-400">{shot.team_name ?? 'Unknown team'}</p>
        </div>
        <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-500 hover:bg-navy-800 hover:text-slate-200" aria-label="Close details">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className={`mb-4 flex items-center justify-between rounded-lg border p-3 ${shot.goal ? 'border-goal/40 bg-goal/10' : 'border-miss/40 bg-miss/10'}`}>
        <span className={`font-semibold ${shot.goal ? 'text-goal' : 'text-red-300'}`}>{shot.goal ? 'Goal' : 'No goal'}</span>
        {!shot.goal && <span className="text-sm text-slate-300">{shot.shot_outcome}</span>}
      </div>

      <dl>
        <DetailRow label="Match">
          {matchLabel}
          {match?.match_date && <span className="block text-xs text-slate-500">{match.match_date}</span>}
        </DetailRow>
        <DetailRow label="Predicted xG"><span className="font-semibold text-xg tabular-nums">{formatXg(shot.predicted_xg, 3)}</span></DetailRow>
        {shot.statsbomb_xg !== null && (
          <DetailRow label="StatsBomb xG (benchmark)"><span className="tabular-nums">{formatXg(shot.statsbomb_xg, 3)}</span></DetailRow>
        )}
        {shot.body_part && <DetailRow label="Body part">{shot.body_part}</DetailRow>}
        {shot.shot_type && <DetailRow label="Shot type">{shot.shot_type}</DetailRow>}
        <DetailRow label="Location (x, y)"><span className="tabular-nums">{shot.x.toFixed(1)}, {shot.y.toFixed(1)}</span></DetailRow>
      </dl>
    </div>
  )
}
