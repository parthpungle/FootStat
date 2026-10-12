import { CircleSlash, Database, Goal, Sigma, Target, Trophy } from 'lucide-react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend as ChartLegend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api/client'
import type { ReactNode } from 'react'
import type { MetricsResponse, OverviewResponse } from '../api/types'
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '../components/ui'
import { useApi, type ApiState } from '../hooks/useApi'
import { formatInt, formatPercent, formatShortDate, formatXg } from '../lib/format'

export function Dashboard() {
  const overview = useApi((signal) => api.overview(signal), 'overview')
  const metrics = useApi((signal) => api.metrics(signal), 'metrics')

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Historical shooting statistics and expected goals from the trained model."
      />
      {overview.loading && !overview.data && <LoadingState label="Loading overview…" />}
      {overview.error && <ErrorState message={overview.error} onRetry={overview.reload} />}
      {overview.data && <DashboardContent data={overview.data} metrics={metrics} />}
    </>
  )
}

function DashboardContent({ data, metrics }: {
  data: OverviewResponse
  metrics: ApiState<MetricsResponse>
}) {
  const conversion = data.total_shots ? data.total_goals / data.total_shots : null

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total shots" value={formatInt(data.total_shots)} icon={<Target className="h-4 w-4" />} />
        <StatCard
          label="Goals scored"
          value={formatInt(data.total_goals)}
          accent="text-goal"
          hint={conversion !== null ? `${formatPercent(conversion)} of shots` : undefined}
          icon={<Goal className="h-4 w-4 text-goal" />}
        />
        <StatCard
          label="Non-goal shots"
          value={formatInt(data.total_non_goals)}
          accent="text-miss"
          icon={<CircleSlash className="h-4 w-4 text-miss" />}
        />
        <StatCard
          label="Total predicted xG"
          value={formatXg(data.total_predicted_xg, 1)}
          accent="text-xg"
          hint={data.total_statsbomb_xg !== null ? `StatsBomb benchmark: ${formatXg(data.total_statsbomb_xg, 1)}` : undefined}
          icon={<Sigma className="h-4 w-4 text-xg" />}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title="Goals vs predicted xG by match date" className="flex flex-col xl:col-span-2">
          <GoalsVsXgChart data={data} />
        </Card>
        <Card title={<span className="inline-flex items-center gap-2"><Trophy className="h-4 w-4 text-goal" /> Top players by xG</span>}>
          <Leaderboard data={data} />
        </Card>
      </div>

      <InfoSection data={data} metrics={metrics} />
    </div>
  )
}

function GoalsVsXgChart({ data }: { data: OverviewResponse }) {
  if (data.by_date.length === 0) {
    return <EmptyState title="No dated match data">Match dates or model predictions are unavailable.</EmptyState>
  }
  const rows = data.by_date.map((d) => ({ ...d, label: formatShortDate(d.match_date) }))

  return (
    <div className="h-72 w-full sm:h-80 xl:h-auto xl:min-h-80 xl:flex-1">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid stroke="var(--color-navy-700)" vertical={false} />
          <XAxis dataKey="label" stroke="var(--color-slate-500)" tick={{ fontSize: 11 }} tickLine={false} interval="preserveStartEnd" minTickGap={12} />
          <YAxis stroke="var(--color-slate-500)" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: 'rgb(148 163 184 / 0.08)' }}
            contentStyle={{ background: 'var(--color-navy-800)', border: '1px solid var(--color-navy-600)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: 'var(--color-slate-200)', marginBottom: 4 }}
            formatter={(value, name) => [name === 'Predicted xG' ? Number(value).toFixed(2) : value, name]}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined
              return row ? `${row.match_date} · ${row.matches} match${row.matches === 1 ? '' : 'es'}, ${row.shots} shots` : ''
            }}
          />
          <ChartLegend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="goals" name="Goals" fill="var(--color-goal)" radius={[3, 3, 0, 0]} maxBarSize={22} />
          <Line dataKey="predicted_xg" name="Predicted xG" stroke="var(--color-xg)" strokeWidth={2} dot={{ r: 2.5 }} type="monotone" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

function Leaderboard({ data }: { data: OverviewResponse }) {
  if (data.top_players.length === 0) {
    return <EmptyState title="No player rankings">Predicted xG is unavailable.</EmptyState>
  }
  const max = Math.max(...data.top_players.map((p) => p.predicted_xg), 0.0001)

  return (
    <ol className="flex flex-col gap-3">
      {data.top_players.map((p, i) => (
        <li key={p.player_id} className="rounded-lg border border-navy-700 bg-navy-850 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-start gap-3">
              <span className="mt-0.5 w-4 text-sm font-semibold text-slate-500 tabular-nums">{i + 1}</span>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-slate-100" title={p.player_name}>{p.player_name}</p>
                <p className="text-xs text-slate-500">{p.team_name} · {p.shots} shots · <span className="text-goal">{p.goals} goals</span></p>
              </div>
            </div>
            <span className="text-sm font-semibold text-xg tabular-nums">{formatXg(p.predicted_xg)}</span>
          </div>
          <div className="mt-2 ml-7 h-1.5 rounded-full bg-navy-700">
            <div className="h-full rounded-full bg-xg" style={{ width: `${(p.predicted_xg / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ol>
  )
}

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-navy-700/60 py-2 text-sm last:border-0">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-200 tabular-nums">{value}</dd>
    </div>
  )
}

function InfoSection({ data, metrics }: { data: OverviewResponse; metrics: ApiState<MetricsResponse> }) {
  const dates = data.by_match.map((m) => m.match_date).filter((d): d is string => !!d).sort()
  const m = metrics.data

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card title={<span className="inline-flex items-center gap-2"><Database className="h-4 w-4" /> Dataset</span>}>
        <dl>
          <InfoRow label="Source" value="StatsBomb Open Data" />
          <InfoRow label="Matches" value={formatInt(data.by_match.length)} />
          {dates.length > 0 && <InfoRow label="Date range" value={`${dates[0]} → ${dates[dates.length - 1]}`} />}
          <InfoRow label="Shots" value={formatInt(data.total_shots)} />
          <InfoRow label="Goal rate" value={data.total_shots ? formatPercent(data.total_goals / data.total_shots) : '—'} />
        </dl>
        <p className="mt-3 text-xs text-slate-500">
          Predicted xG totals include matches the model was trained on. See held-out metrics for an honest evaluation.
        </p>
      </Card>

      <Card title="Model">
        {metrics.loading && !m && <LoadingState label="Loading metrics…" />}
        {metrics.error && <ErrorState message={metrics.error} onRetry={metrics.reload} />}
        {m && (
          <>
            <dl>
              <InfoRow label="Type" value={m.model} />
              <InfoRow label="Version" value={<code className="text-xs">{m.model_version ?? '—'}</code>} />
              <InfoRow label="Trained" value={new Date(m.trained_at).toLocaleString()} />
              <InfoRow label="Train / test split" value={`${m.train.matches} / ${m.test.matches} matches`} />
              <InfoRow label="Test shots" value={`${formatInt(m.test_examples)} (${m.test.goals} goals)`} />
            </dl>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 uppercase">
                    <th className="pb-2 font-medium">Held-out metric</th>
                    <th className="pb-2 text-right font-medium">Model</th>
                    <th className="pb-2 text-right font-medium">Base rate</th>
                    <th className="pb-2 text-right font-medium">StatsBomb</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  <MetricRow label="Log loss ↓" values={[m.test_metrics.log_loss, m.baseline_training_goal_rate.log_loss, m.statsbomb_xg_benchmark.log_loss]} />
                  <MetricRow label="Brier score ↓" values={[m.test_metrics.brier_score, m.baseline_training_goal_rate.brier_score, m.statsbomb_xg_benchmark.brier_score]} />
                  <MetricRow label="ROC-AUC ↑" values={[m.test_metrics.roc_auc, m.baseline_training_goal_rate.roc_auc, m.statsbomb_xg_benchmark.roc_auc]} />
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}

function MetricRow({ label, values }: { label: string; values: (number | null)[] }) {
  return (
    <tr className="border-t border-navy-700/60">
      <td className="py-2 text-slate-400">{label}</td>
      {values.map((v, i) => (
        <td key={i} className={`py-2 text-right ${i === 0 ? 'font-semibold text-slate-100' : 'text-slate-400'}`}>
          {v === null ? '—' : v.toFixed(4)}
        </td>
      ))}
    </tr>
  )
}
