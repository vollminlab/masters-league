import { useState, useEffect } from 'react'
import type { ScorecardData, HoleData } from '../types'

const HOLES_FRONT = [1, 2, 3, 4, 5, 6, 7, 8, 9]
const HOLES_BACK = [10, 11, 12, 13, 14, 15, 16, 17, 18]

// ── Symbol styles ─────────────────────────────────────────────────────────────

type SymbolStyle = { ring: string; text: string }

const SCORE_STYLES: Record<string, SymbolStyle> = {
  ALBATROSS: {
    ring: 'border-2 border-yellow-300 rounded-full shadow-[0_0_0_2px_#111827,0_0_0_4px_#fde047,0_0_0_6px_#111827,0_0_0_8px_#fde047]',
    text: 'text-yellow-200',
  },
  EAGLE: {
    ring: 'border-2 border-yellow-400 rounded-full shadow-[0_0_0_2px_#111827,0_0_0_4px_#fbbf24]',
    text: 'text-yellow-300',
  },
  BIRDIE: {
    ring: 'border-2 border-red-500 rounded-full',
    text: 'text-red-400',
  },
  PAR: {
    ring: '',
    text: 'text-gray-400',
  },
  BOGEY: {
    ring: 'border-2 border-blue-500',
    text: 'text-blue-400',
  },
  DOUBLE_BOGEY: {
    ring: 'border-2 border-blue-700 shadow-[0_0_0_2px_#111827,0_0_0_4px_#1d4ed8]',
    text: 'text-blue-300',
  },
  TRIPLE_BOGEY: {
    ring: 'bg-red-900',
    text: 'text-white',
  },
  WORSE: {
    ring: 'bg-red-950',
    text: 'text-white',
  },
}

function getStyle(scoreType: string | null): SymbolStyle {
  if (!scoreType) return SCORE_STYLES.PAR
  return SCORE_STYLES[scoreType] ?? SCORE_STYLES.WORSE
}

// ── Individual hole cell ──────────────────────────────────────────────────────

function HoleCell({ hole }: { hole: HoleData | null }) {
  const baseCell = 'w-7 h-7 flex items-center justify-center text-xs font-mono tabular shrink-0'

  if (!hole || hole.strokes === null) {
    return (
      <div className={`${baseCell} text-gray-700`}>–</div>
    )
  }

  const style = getStyle(hole.score_type)
  return (
    <div className={`${baseCell} ${style.ring} ${style.text}`}>
      {hole.strokes}
    </div>
  )
}

// ── Scorecard grid ────────────────────────────────────────────────────────────

function ScorecardGrid({ round }: { round: import('../types').RoundData }) {
  const holeMap = new Map(round.holes.map(h => [h.hole, h]))

  const frontPlayed = HOLES_FRONT.map(n => holeMap.get(n)).filter(Boolean) as HoleData[]
  const backPlayed = HOLES_BACK.map(n => holeMap.get(n)).filter(Boolean) as HoleData[]

  const outStrokes = frontPlayed.reduce((s, h) => s + (h.strokes ?? 0), 0)
  const inStrokes = backPlayed.reduce((s, h) => s + (h.strokes ?? 0), 0)
  const totalStrokes = outStrokes + inStrokes

  const outPar = frontPlayed.reduce((s, h) => s + h.par, 0)
  const inPar = backPlayed.reduce((s, h) => s + h.par, 0)

  const showOut = frontPlayed.length > 0
  const showIn = backPlayed.length > 0

  const cellBase = 'w-7 shrink-0 text-center text-xs tabular'
  const totalCell = 'w-9 shrink-0 text-center text-xs tabular font-semibold'

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max px-4 py-2 space-y-1">

        {/* HOLE row */}
        <div className="flex items-center gap-1 text-gray-600 text-xs uppercase">
          <div className="w-10 shrink-0 text-gray-700 font-semibold">HOLE</div>
          {HOLES_FRONT.map(n => (
            <div key={n} className={cellBase}>{n}</div>
          ))}
          <div className={`${totalCell} text-gray-600`}>OUT</div>
          {HOLES_BACK.map(n => (
            <div key={n} className={cellBase}>{n}</div>
          ))}
          <div className={`${totalCell} text-gray-600`}>IN</div>
          <div className={`${totalCell} text-gray-500`}>TOT</div>
        </div>

        {/* PAR row */}
        <div className="flex items-center gap-1 text-gray-600 text-xs">
          <div className="w-10 shrink-0 text-gray-700 font-semibold text-xs">PAR</div>
          {HOLES_FRONT.map(n => {
            const h = holeMap.get(n)
            return (
              <div key={n} className={cellBase}>{h ? h.par : '·'}</div>
            )
          })}
          <div className={`${totalCell} text-gray-600`}>{showOut ? outPar : '–'}</div>
          {HOLES_BACK.map(n => {
            const h = holeMap.get(n)
            return (
              <div key={n} className={cellBase}>{h ? h.par : '·'}</div>
            )
          })}
          <div className={`${totalCell} text-gray-600`}>{showIn ? inPar : '–'}</div>
          <div className={`${totalCell} text-gray-500`}>{showOut && showIn ? outPar + inPar : '–'}</div>
        </div>

        {/* SCORE row */}
        <div className="flex items-center gap-1">
          <div className="w-10 shrink-0 text-gray-700 font-semibold text-xs">SCORE</div>
          {HOLES_FRONT.map(n => (
            <HoleCell key={n} hole={holeMap.get(n) ?? null} />
          ))}
          <div className={`${totalCell} ${showOut ? 'text-white' : 'text-gray-700'}`}>
            {showOut ? outStrokes : '–'}
          </div>
          {HOLES_BACK.map(n => (
            <HoleCell key={n} hole={holeMap.get(n) ?? null} />
          ))}
          <div className={`${totalCell} ${showIn ? 'text-white' : 'text-gray-700'}`}>
            {showIn ? inStrokes : '–'}
          </div>
          <div className={`${totalCell} ${(showOut || showIn) ? 'text-white font-bold' : 'text-gray-700'}`}>
            {(showOut || showIn) ? totalStrokes : '–'}
          </div>
        </div>

      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function ScorecardPanel({ playerId }: { playerId: string }) {
  const [data, setData] = useState<ScorecardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeRound, setActiveRound] = useState<number>(1)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setData(null)
    fetch(`/api/scorecard/${playerId}`, { signal: controller.signal })
      .then(r => r.ok ? r.json() : Promise.reject(`Error ${r.status}`))
      .then((d: ScorecardData) => {
        setData(d)
        setActiveRound(d.current_round)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if ((e as DOMException)?.name === 'AbortError') return
        setError(typeof e === 'string' ? e : 'Scorecard unavailable')
        setLoading(false)
      })
    return () => controller.abort()
  }, [playerId])

  const currentRound = data?.rounds.find(r => r.round === activeRound)

  return (
    <div className="border-t border-gray-800/60" style={{ background: '#0d1520' }}>

      {/* Round tabs */}
      <div className="flex gap-1 px-4 pt-3 pb-1">
        {[1, 2, 3, 4].map(n => {
          const round = data?.rounds.find(r => r.round === n)
          const started = round?.started ?? false
          const isActive = n === activeRound

          return (
            <button
              key={n}
              onClick={() => started && setActiveRound(n)}
              className={`
                px-3 py-1 rounded text-xs font-semibold transition-colors
                ${isActive
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40'
                  : started
                  ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50 border border-transparent'
                  : 'text-gray-700 border border-transparent cursor-default'
                }
              `}
              disabled={!started}
            >
              R{n}
              {started && round?.to_par_display && (
                <span className={`ml-1 ${
                  round.to_par_display.startsWith('-') ? 'text-green-500' :
                  round.to_par_display.startsWith('+') ? 'text-red-500' : 'text-gray-500'
                }`}>
                  {round.to_par_display}
                </span>
              )}
            </button>
          )
        })}

        {/* Running to-par for active round */}
        {data && currentRound?.to_par_display && (
          <div className={`ml-auto text-sm font-bold font-mono tabular self-center ${
            currentRound.to_par_display.startsWith('-') ? 'text-green-400' :
            currentRound.to_par_display.startsWith('+') ? 'text-red-400' : 'text-white'
          }`}>
            {currentRound.to_par_display}
          </div>
        )}
      </div>

      {/* Content */}
      {loading && (
        <div className="px-4 py-4 text-gray-600 text-xs animate-pulse">Loading scorecard…</div>
      )}

      {error && (
        <div className="px-4 py-3 text-red-600 text-xs">{error}</div>
      )}

      {!loading && !error && currentRound && (
        currentRound.started
          ? <ScorecardGrid round={currentRound} />
          : <div className="px-4 py-4 text-gray-700 text-xs">Round not yet started</div>
      )}

      <div className="h-2" />
    </div>
  )
}
