import { useState, useEffect, useCallback, useRef } from 'react'
import type { LeaderboardData } from './types'
import Header from './components/Header'
import TeamCard from './components/TeamCard'

export default function App() {
  const [data, setData] = useState<LeaderboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const initialLoad = useRef(true)

  const fetchData = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true)
    try {
      const resp = await fetch('/api/leaderboard')
      if (!resp.ok) throw new Error(`Server error ${resp.status}`)
      const json: LeaderboardData = await resp.json()
      setData(json)
      setLastRefresh(new Date())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection error')
    } finally {
      if (initialLoad.current) {
        setLoading(false)
        initialLoad.current = false
      }
      setIsRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const id = setInterval(() => fetchData(), 30_000)
    return () => clearInterval(id)
  }, [fetchData])

  const activeTeams = data?.teams.filter(t => !t.disqualified) ?? []
  const dqTeams = data?.teams.filter(t => t.disqualified) ?? []

  const tiedPositions = new Set(
    activeTeams
      .map(t => t.position)
      .filter((pos, _i, arr) => pos !== null && arr.filter(p => p === pos).length > 1)
  )

  return (
    <div className="min-h-screen" style={{ background: '#0a1628' }}>
      <Header
        lastRefresh={lastRefresh}
        isRefreshing={isRefreshing}
        playerCount={data?.player_count ?? null}
        onRefresh={() => fetchData(true)}
      />

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="text-yellow-400 text-xl animate-pulse">Loading leaderboard…</div>
          </div>
        )}

        {error && (
          <div className="bg-red-950/40 border border-red-700/60 rounded-lg px-4 py-3 text-red-300 text-sm">
            ⚠ {error} — {data ? 'showing last known data' : 'no data available'}
          </div>
        )}

        {!loading && data && (
          <>
            {/* Active teams grid */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              {activeTeams.map(team => (
                <TeamCard key={team.name} team={team} isTied={tiedPositions.has(team.position)} />
              ))}
            </div>

            {/* Disqualified teams */}
            {dqTeams.length > 0 && (
              <section>
                <h2 className="text-gray-600 text-xs uppercase tracking-widest font-semibold mb-3 px-1">
                  Disqualified — fewer than 3 players made the cut
                </h2>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  {dqTeams.map(team => (
                    <TeamCard key={team.name} team={team} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
