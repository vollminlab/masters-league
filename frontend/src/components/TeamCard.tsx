import { useState } from 'react'
import type { GolferResult, TeamResult } from '../types'
import ScorecardPanel from './ScorecardPanel'

const TOTAL_ROUNDS = 4

// ── Score formatting ──────────────────────────────────────────────────────────

function scoreColor(display: string): string {
  if (display.startsWith('-')) return 'text-green-400'
  if (display.startsWith('+')) return 'text-red-400'
  if (display === 'E') return 'text-white'
  return 'text-gray-500'
}

function roundScoreColor(display: string): string {
  if (display.startsWith('-')) return 'text-green-500'
  if (display.startsWith('+')) return 'text-red-500'
  if (display === 'E') return 'text-gray-300'
  return 'text-gray-600'
}

function rankColor(pos: number | null, dq: boolean): string {
  if (dq) return 'text-gray-700'
  if (pos === 1) return 'text-yellow-400'
  if (pos === 2) return 'text-gray-300'
  if (pos === 3) return 'text-amber-600'
  return 'text-gray-500'
}

// ── Team card ─────────────────────────────────────────────────────────────────

export default function TeamCard({ team, isTied = false }: { team: TeamResult; isTied?: boolean }) {
  const { counting_score_display: scoreDisplay, disqualified, position } = team
  const isLeader = position === 1 && !disqualified
  const [expandedGolfer, setExpandedGolfer] = useState<string | null>(null)

  const posDisplay = disqualified
    ? 'DQ'
    : isTied && position
    ? `T${position}`
    : (position ?? '–')

  function toggleGolfer(name: string) {
    setExpandedGolfer(prev => prev === name ? null : name)
  }

  return (
    <div
      className={`rounded-xl overflow-hidden border transition-all ${
        isLeader
          ? 'border-yellow-500/60 shadow-[0_0_24px_rgba(234,179,8,0.12)]'
          : disqualified
          ? 'border-gray-800/60'
          : 'border-gray-700/80'
      }`}
      style={{ background: '#111827' }}
    >
      {/* ── Card header ── */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{
          background: isLeader ? '#1e2c1a' : disqualified ? '#1a1f2e' : '#1e2538',
        }}
      >
        {/* Rank + name */}
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={`text-2xl font-bold tabular w-10 shrink-0 text-center ${rankColor(position, disqualified)}`}
          >
            {posDisplay}
          </span>

          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h2
                className={`font-bold text-base leading-tight ${
                  disqualified ? 'text-gray-500' : 'text-white'
                }`}
              >
                {team.name}
              </h2>
              {disqualified && (
                <span className="text-xs bg-red-950 text-red-500 border border-red-900 px-1.5 py-0.5 rounded font-semibold">
                  DISQUALIFIED
                </span>
              )}
            </div>
            <p className="text-xs text-gray-600 mt-0.5">
              {team.active_count} active
              {team.cut_count > 0 && (
                <span className="text-red-600 ml-1.5">· {team.cut_count} cut</span>
              )}
            </p>
          </div>
        </div>

        {/* Counting score */}
        <div className="text-right shrink-0 ml-3">
          <div className={`text-3xl font-bold font-mono tabular ${scoreColor(scoreDisplay)}`}>
            {scoreDisplay}
          </div>
          <div className="text-xs text-gray-700 mt-0.5">best 3</div>
        </div>
      </div>

      {/* ── Column headers ── */}
      <div className="px-4 pt-2 pb-1 flex items-center text-xs text-gray-600 uppercase tracking-wider select-none gap-1">
        <div className="w-4 shrink-0" />
        <div className="flex-1 min-w-0">Golfer</div>
        {Array.from({ length: TOTAL_ROUNDS }, (_, i) => (
          <div key={i} className="hidden sm:block w-7 text-right shrink-0">
            R{i + 1}
          </div>
        ))}
        <div className="w-10 text-right shrink-0">Score</div>
        <div className="w-8 text-right shrink-0">Pos</div>
        <div className="w-16 text-right shrink-0">Thru</div>
      </div>

      {/* ── Golfer rows ── */}
      <div className="divide-y divide-gray-800/40 pb-1">
        {team.golfers.map(g => (
          <div key={g.name}>
            <GolferRow
              golfer={g}
              isExpanded={expandedGolfer === g.name}
              onToggle={() => toggleGolfer(g.name)}
            />
            {expandedGolfer === g.name && g.player_id && (
              <ScorecardPanel playerId={g.player_id} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Golfer row ────────────────────────────────────────────────────────────────

function GolferRow({
  golfer,
  isExpanded,
  onToggle,
}: {
  golfer: GolferResult
  isExpanded: boolean
  onToggle: () => void
}) {
  const inactive = golfer.is_cut || golfer.is_withdrawn
  const rounds = golfer.round_scores_display ?? []
  const paddedRounds = [...rounds, ...Array(Math.max(0, TOTAL_ROUNDS - rounds.length)).fill('')]
  const clickable = Boolean(golfer.player_id) && !inactive

  return (
    <div
      onClick={clickable ? onToggle : undefined}
      className={`px-4 py-2 flex items-center text-sm gap-1 transition-opacity ${
        inactive ? 'opacity-35' : ''
      } ${clickable ? 'cursor-pointer hover:bg-white/[0.03]' : ''} ${
        isExpanded ? 'bg-white/[0.04]' : ''
      }`}
    >
      {/* Counting dot / status icon */}
      <div className="w-4 shrink-0 flex items-center justify-center">
        {golfer.is_counting && !inactive && (
          <div
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: '#FFD700' }}
            title="Counting toward team score"
          />
        )}
        {golfer.is_cut && (
          <span className="text-red-700 text-xs leading-none">✗</span>
        )}
        {golfer.is_withdrawn && (
          <span className="text-gray-700 text-xs leading-none">–</span>
        )}
      </div>

      {/* Name */}
      <div
        className={`flex-1 min-w-0 font-medium truncate ${
          inactive
            ? 'text-gray-600 line-through decoration-gray-700'
            : golfer.is_counting
            ? 'text-white'
            : 'text-gray-400'
        }`}
      >
        {golfer.name}
        {clickable && (
          <span className={`ml-1 text-gray-700 text-xs transition-transform inline-block ${isExpanded ? 'rotate-180' : ''}`}>
            ▾
          </span>
        )}
      </div>

      {/* Round scores */}
      {paddedRounds.map((r, i) => (
        <div
          key={i}
          className={`hidden sm:block w-7 text-right font-mono text-xs tabular shrink-0 ${
            r ? roundScoreColor(r) : 'text-gray-800'
          }`}
        >
          {r || '·'}
        </div>
      ))}

      {/* Total score */}
      <div className={`w-10 text-right font-mono font-semibold tabular shrink-0 ${scoreColor(golfer.score_display)}`}>
        {golfer.score_display}
      </div>

      {/* Position */}
      <div className="w-8 text-right text-gray-600 text-xs tabular shrink-0">
        {golfer.position}
      </div>

      {/* Thru */}
      <div
        className={`w-16 text-right text-xs tabular shrink-0 ${
          golfer.thru === 'F' ? 'text-green-700' : 'text-gray-600'
        }`}
      >
        {golfer.thru}
      </div>
    </div>
  )
}
