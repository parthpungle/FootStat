import { useEffect, useState } from 'react'
import { Layout } from './components/Layout'
import { PAGES, type PageId } from './lib/pages'
import { Dashboard } from './pages/Dashboard'
import { Predictor } from './pages/Predictor'
import { ShotMap } from './pages/ShotMap'

function pageFromHash(): PageId {
  const id = window.location.hash.replace(/^#\/?/, '')
  return PAGES.some((p) => p.id === id) ? (id as PageId) : 'dashboard'
}

function App() {
  const [page, setPage] = useState<PageId>(pageFromHash)

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    const label = PAGES.find((p) => p.id === page)?.label
    document.title = `${label} · FootStat`
    window.scrollTo(0, 0)
  }, [page])

  return (
    <Layout current={page}>
      {page === 'dashboard' && <Dashboard />}
      {page === 'shots' && <ShotMap />}
      {page === 'predict' && <Predictor />}
    </Layout>
  )
}

export default App
