import { AlertTriangle, Inbox, Loader2, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'

export function Card({ title, action, children, className = '' }: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-xl border border-navy-700 bg-navy-900 p-4 sm:p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold tracking-wide text-slate-300 uppercase">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function StatCard({ label, value, hint, icon, accent = 'text-slate-100' }: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon: ReactNode
  accent?: string
}) {
  return (
    <section className="rounded-xl border border-navy-700 bg-navy-900 p-4 sm:p-5">
      <div className="flex items-center justify-between text-slate-400">
        <span className="text-xs font-medium tracking-wide uppercase">{label}</span>
        {icon}
      </div>
      <p className={`mt-3 text-3xl font-semibold tabular-nums ${accent}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </section>
  )
}

export function PageHeader({ title, description }: { title: string; description: ReactNode }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold text-slate-50">{title}</h1>
      <p className="mt-1 text-sm text-slate-400">{description}</p>
    </header>
  )
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-400" role="status">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-miss/40 bg-miss/10 p-4 text-sm text-red-200 sm:flex-row sm:items-center">
      <AlertTriangle className="h-5 w-5 shrink-0 text-miss" />
      <p className="flex-1">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-md border border-red-300/30 px-3 py-1.5 text-red-100 hover:bg-red-400/10"
        >
          <RotateCw className="h-3.5 w-3.5" /> Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <Inbox className="h-8 w-8 text-slate-600" />
      <p className="font-medium text-slate-300">{title}</p>
      {children && <p className="max-w-sm text-sm text-slate-500">{children}</p>}
    </div>
  )
}

export function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-full bg-goal" /> Goal
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-full bg-miss" /> No goal
      </span>
      <span>Marker size = predicted xG</span>
    </div>
  )
}
