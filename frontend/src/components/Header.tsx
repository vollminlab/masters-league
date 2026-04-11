interface HeaderProps {
  lastRefresh: Date | null
  isRefreshing: boolean
  playerCount: number | null
  onRefresh: () => void
}

export default function Header({ lastRefresh, isRefreshing, playerCount, onRefresh }: HeaderProps) {
  const timeStr = lastRefresh?.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <header style={{ background: '#006747' }} className="border-b border-yellow-600/20 shadow-xl">
      <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">

        {/* Left: title */}
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#FFD700' }}>
            ⛳ Masters League 2026
          </h1>
          <p className="text-green-200/70 text-xs mt-0.5">
            Fantasy Golf · Best 3 of 5 Score
            {playerCount !== null && (
              <span className="ml-2 text-green-300/50">· {playerCount} players tracked</span>
            )}
          </p>
        </div>

        {/* Right: live indicator + refresh */}
        <div className="flex items-center gap-4">
          <div className="text-right hidden sm:block">
            {lastRefresh ? (
              <p className="text-green-200/70 text-xs">Updated {timeStr}</p>
            ) : (
              <p className="text-green-200/40 text-xs">Connecting…</p>
            )}
            <p className="text-green-300/30 text-xs">Auto-refresh every 30s</p>
          </div>

          <div className="flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                isRefreshing
                  ? 'bg-yellow-400 animate-ping'
                  : 'bg-green-400 animate-pulse'
              }`}
            />
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="text-xs font-medium text-yellow-400 hover:text-yellow-200 disabled:opacity-40 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>

      </div>
    </header>
  )
}
