import { Goal, Menu, PanelLeftClose, PanelLeftOpen, X } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { PAGES, type PageId } from '../lib/pages'

function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-goal/15 text-goal">
        <Goal className="h-5 w-5" />
      </span>
      {!compact && (
        <span className="text-lg font-semibold tracking-tight text-slate-50">
          Foot<span className="text-goal">Stat</span>
        </span>
      )}
    </div>
  )
}

function NavLinks({ current, compact, onNavigate }: { current: PageId; compact: boolean; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {PAGES.map(({ id, label, icon: Icon }) => {
        const active = id === current
        return (
          <a
            key={id}
            href={`#/${id}`}
            onClick={onNavigate}
            title={compact ? label : undefined}
            aria-current={active ? 'page' : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              active ? 'bg-goal/10 text-goal' : 'text-slate-400 hover:bg-navy-800 hover:text-slate-100'
            } ${compact ? 'justify-center' : ''}`}
          >
            <Icon className="h-[18px] w-[18px] shrink-0" />
            {!compact && label}
          </a>
        )
      })}
    </nav>
  )
}

export function Layout({ current, children }: { current: PageId; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-navy-700 bg-navy-900 p-3 lg:flex ${
          collapsed ? 'w-[68px]' : 'w-60'
        }`}
      >
        <div className={`mb-6 flex items-center px-1.5 pt-2 ${collapsed ? 'justify-center' : 'justify-between'}`}>
          <Logo compact={collapsed} />
        </div>
        <NavLinks current={current} compact={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="mt-auto flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs text-slate-500 hover:bg-navy-800 hover:text-slate-300"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" /> Collapse</>}
        </button>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-navy-700 bg-navy-900/95 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="rounded-md p-2 text-slate-300 hover:bg-navy-800"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-navy-700 bg-navy-900 p-3">
            <div className="mb-6 flex items-center justify-between px-1.5 pt-2">
              <Logo />
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="rounded-md p-1.5 text-slate-400 hover:bg-navy-800"
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <NavLinks current={current} compact={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <main className={`px-4 py-6 sm:px-6 lg:py-8 ${collapsed ? 'lg:pl-[100px]' : 'lg:pl-[272px]'} lg:pr-8`}>
        <div className="mx-auto max-w-7xl">{children}</div>
      </main>
    </div>
  )
}
