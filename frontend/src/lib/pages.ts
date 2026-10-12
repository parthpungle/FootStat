import { Crosshair, LayoutDashboard, Map } from 'lucide-react'

export type PageId = 'dashboard' | 'shots' | 'predict'

export const PAGES: { id: PageId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'shots', label: 'Shot Map', icon: Map },
  { id: 'predict', label: 'Shot Predictor', icon: Crosshair },
]
