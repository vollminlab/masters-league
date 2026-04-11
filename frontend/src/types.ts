export interface GolferResult {
  name: string
  score: number | null
  score_display: string   // "-12", "E", "+3", "CUT", "WD", "-"
  position: string        // "T1", "2nd", "CUT", "-"
  thru: string            // "F", "9", "-", "1:30 PM"
  is_cut: boolean
  is_withdrawn: boolean
  is_counting: boolean    // one of the best 3 active players
  round_scores_display: string[]  // ["−5", "−7", "+1"] per completed round
}

export interface TeamResult {
  name: string
  golfers: GolferResult[]
  counting_score: number | null
  counting_score_display: string  // "-17", "E", "+7", "DQ"
  cut_count: number
  active_count: number
  disqualified: boolean
  position: number | null
}

export interface LeaderboardData {
  teams: TeamResult[]
  last_updated: string   // ISO timestamp
  cache_ttl: number
  player_count: number
}
