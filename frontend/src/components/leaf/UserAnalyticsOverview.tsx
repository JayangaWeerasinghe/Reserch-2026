import { useEffect, useMemo, useState } from 'react'
import { getCases, getUserHistory } from '@/lib/leafApi'
import type { CaseSummary } from '@/lib/leafApi'

const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatDiseaseLabel(value: string | null | undefined): string {
  return (value || 'Unknown').replace(/_/g, ' ')
}

interface MonthlyTrendPoint {
  label: string
  month: number
  year: number
  count: number
  confidence: number
  totalConfidence: number
}

function buildMonthlyTrend(cases: CaseSummary[]): MonthlyTrendPoint[] {
  const series: MonthlyTrendPoint[] = Array.from({ length: 6 }, (_, index) => {
    const date = new Date()
    date.setMonth(date.getMonth() - (5 - index))
    const monthIndex = date.getMonth()
    const year = date.getFullYear()

    return {
      label: `${monthLabels[monthIndex]} ${year.toString().slice(-2)}`,
      month: monthIndex,
      year,
      count: 0,
      confidence: 0,
      totalConfidence: 0,
    }
  })

  cases.forEach((item) => {
    if (!item.created_at) return
    const created = new Date(item.created_at)
    const monthIndex = created.getMonth()
    const year = created.getFullYear()
    const entry = series.find((month) => month.month === monthIndex && month.year === year)

    if (entry) {
      entry.count += 1
      const confidenceValue = Number(item.confidence || 0) * 100
      entry.totalConfidence += confidenceValue
      entry.confidence = entry.totalConfidence / (entry.count || 1)
    }
  })

  return series
}

interface WeeklyTrendPoint {
  label: string
  count: number
  confidence: number
  totalConfidence: number
}

function buildWeeklyTrend(cases: CaseSummary[]): WeeklyTrendPoint[] {
  const days: WeeklyTrendPoint[] = Array.from({ length: 7 }, (_, index) => {
    const date = new Date()
    date.setDate(date.getDate() - (6 - index))
    return {
      label: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      count: 0,
      confidence: 0,
      totalConfidence: 0,
    }
  })

  cases.forEach((item) => {
    if (!item.created_at) return
    const created = new Date(item.created_at)
    const today = new Date()
    const diffDays = Math.floor((today.getTime() - created.getTime()) / (1000 * 60 * 60 * 24))
    if (diffDays < 0 || diffDays > 6) return
    const entry = days[6 - diffDays] // Reverse order to display oldest to newest
    if (!entry) return
    entry.count += 1
    const confidenceValue = Number(item.confidence || 0) * 100
    entry.totalConfidence += confidenceValue
    entry.confidence = entry.totalConfidence / (entry.count || 1)
  })

  return days
}

interface Segment {
  label: string
  value: number
  color: string
}

function RingChart({ segments }: { segments: Segment[] }) {
  const radius = 56
  const circumference = 2 * Math.PI * radius
  const total = segments.reduce((sum, segment) => sum + segment.value, 0) || 1

  let offset = 0

  return (
    <div className="ring-chart-wrap">
      <svg viewBox="0 0 180 180" className="ring-chart" aria-label="Disease breakdown chart">
        <circle cx="90" cy="90" r={radius} fill="none" stroke="#e9f0ed" strokeWidth="18" />
        {segments.map((segment) => {
          const dashLength = (segment.value / total) * circumference
          const strokeDasharray = `${dashLength} ${circumference - dashLength}`
          const strokeDashoffset = -offset
          offset += dashLength

          return (
            <circle
              key={segment.label}
              cx="90"
              cy="90"
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth="18"
              strokeLinecap="round"
              strokeDasharray={strokeDasharray}
              strokeDashoffset={strokeDashoffset}
              transform="rotate(-90 90 90)"
            />
          )
        })}
        <text x="90" y="84" textAnchor="middle" className="ring-chart__value" style={{ fontSize: '1.2rem', fontWeight: 800, fill: '#123c2b' }}>{total}</text>
        <text x="90" y="104" textAnchor="middle" className="ring-chart__label" style={{ fontSize: '0.62rem', fill: '#607368', textTransform: 'uppercase', letterSpacing: '0.08em' }}>analyses</text>
      </svg>
    </div>
  )
}

export default function UserAnalyticsOverview() {
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const rawAuth = localStorage.getItem('paddyguard_leaf_auth')
    const auth = rawAuth ? JSON.parse(rawAuth) : null
    const role = auth?.role
    const username = auth?.username

    const fetchPromise = role === 'USER' || !role ? getUserHistory() : getCases(username)

    fetchPromise
      .then((data) => {
        setCases(Array.isArray(data) ? data : [])
        setLoading(false)
      })
      .catch(() => {
        setCases([])
        setLoading(false)
      })
  }, [])

  const stats = useMemo(() => {
    if (!cases.length) {
      return {
        total: 0,
        healthy: 0,
        diseased: 0,
        avgConfidence: 0,
        mostCommonDisease: 'No data',
        diseaseBreakdown: [] as Segment[],
        monthlyTrend: buildMonthlyTrend([]),
        weeklyTrend: buildWeeklyTrend([]),
        trendMax: 1,
      }
    }

    const diseaseCounts: Record<string, number> = {}
    let healthyCount = 0
    let diseasedCount = 0
    let confidenceTotal = 0

    cases.forEach((item) => {
      const label = formatDiseaseLabel(item.predicted_disease)
      diseaseCounts[label] = (diseaseCounts[label] || 0) + 1

      if (label.toLowerCase() === 'healthy') {
        healthyCount += 1
      } else {
        diseasedCount += 1
      }

      confidenceTotal += Number(item.confidence || 0) * 100
    })

    const diseaseBreakdown = Object.entries(diseaseCounts)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value)

    const dominantDisease = diseaseBreakdown[0]?.label || 'No data'
    const allColors = ['#1d7b4f', '#4ca1af', '#f39c12', '#dd6b20', '#6b7280', '#a78bfa']
    const avgConfidence = confidenceTotal / cases.length

    let confidenceLevel = 'Low'
    if (avgConfidence >= 80) confidenceLevel = 'High'
    else if (avgConfidence >= 60) confidenceLevel = 'Medium'

    const monthlyTrend = buildMonthlyTrend(cases)
    const weeklyTrend = buildWeeklyTrend(cases)
    const trendMax = Math.max(...weeklyTrend.map((point) => point.count), 1)

    return {
      total: cases.length,
      healthy: healthyCount,
      diseased: diseasedCount,
      avgConfidence,
      confidenceLevel,
      mostCommonDisease: dominantDisease,
      diseaseBreakdown: diseaseBreakdown.map((segment, index) => ({
        ...segment,
        color: allColors[index % allColors.length],
      })),
      monthlyTrend,
      weeklyTrend,
      trendMax,
    }
  }, [cases])

  if (loading) {
    return (
      <section className="card analytics-panel">
        <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>My Analysis Dashboard</h2>
        <p className="muted">Loading your analysis summary...</p>
      </section>
    )
  }

  if (!cases.length) {
    return (
      <section className="card analytics-panel">
        <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>My Analysis Dashboard</h2>
        <div className="empty-dashboard-state">
          <div className="empty-dashboard-state__icon">📊</div>
          <h3 style={{ margin: 0, fontWeight: 'bold' }}>No analysis data available yet</h3>
          <p className="muted">Upload your first rice leaf image to start seeing crop health trends and detection insights.</p>
        </div>
      </section>
    )
  }

  const diseaseSegments = stats.diseaseBreakdown.length ? stats.diseaseBreakdown : [{ label: 'Healthy', value: 1, color: '#1d7b4f' }]
  const maxBarValue = Math.max(...stats.monthlyTrend.map((month) => month.count), 1)

  return (
    <section className="card analytics-panel animate-entrance">
      <div className="analytics-panel__header">
        <div>
          <p className="eyebrow" style={{ margin: 0 }}>Overview</p>
          <h2 style={{ margin: '4px 0 0 0', fontSize: '1.25rem', fontWeight: 'bold' }}>My Analysis Dashboard</h2>
        </div>
        <span className="analytics-panel__badge">{stats.total} analyses</span>
      </div>

      <div className="analytics-grid">
        <div className="summary-card summary-card--primary">
          <span>Total leaves analysed</span>
          <strong>{stats.total}</strong>
        </div>
        <div className="summary-card summary-card--success">
          <span>Healthy leaves</span>
          <strong>{stats.healthy}</strong>
        </div>
        <div className="summary-card summary-card--warning">
          <span>Diseased leaves</span>
          <strong>{stats.diseased}</strong>
        </div>
        <div className="summary-card summary-card--info">
          <span>AI Confidence</span>
          <strong>{stats.confidenceLevel}</strong>
        </div>
      </div>

      <div className="analytics-row">
        <div className="chart-card chart-card--wide">
          <div className="chart-card__header">
            <h3 style={{ fontWeight: 'bold' }}>Most common disease</h3>
            <span>{stats.mostCommonDisease}</span>
          </div>
          <div className="ring-layout">
            <RingChart segments={diseaseSegments} />
            <div className="legend-list">
              {diseaseSegments.map((segment) => (
                <div key={segment.label} className="legend-item">
                  <span className="legend-color" style={{ background: segment.color }} />
                  <span className="legend-label">{segment.label}</span>
                  <strong>{segment.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-card__header">
            <h3 style={{ fontWeight: 'bold' }}>Detection trend</h3>
            <span>Last 6 months</span>
          </div>
          <div className="bar-chart">
            {stats.monthlyTrend.map((month) => (
              <div key={`${month.label}-${month.month}`} className="bar-chart__column">
                <div
                  className="bar-chart__bar"
                  style={{ height: `${(month.count / maxBarValue) * 100}%` }}
                  title={`${month.label}: ${month.count} analyses`}
                />
                <small>{month.label.split(' ')[0]}</small>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="analytics-row">
        <div className="chart-card">
          <div className="chart-card__header">
            <h3 style={{ fontWeight: 'bold' }}>Weekly detection pattern</h3>
            <span>Last 7 days</span>
          </div>
          <svg viewBox="0 0 360 160" className="line-chart" preserveAspectRatio="none" aria-label="Weekly detection pattern">
            <line x1="20" x2="340" y1="130" y2="130" className="axis-line" />
            <line x1="20" x2="20" y1="20" y2="130" className="axis-line" />
            {stats.weeklyTrend.map((point, index) => {
              const x = 30 + index * 45
              const y = 130 - (point.count / stats.trendMax) * 90
              return (
                <g key={point.label}>
                  <circle cx={x} cy={y} r="4" className="line-dot" />
                  <text x={x} y="150" textAnchor="middle" className="chart-label" style={{ fontSize: '10px', fill: '#607368' }}>{point.label.split(' ')[0]}</text>
                </g>
              )
            })}
            <polyline
              points={stats.weeklyTrend.map((point, index) => `${30 + index * 45},${130 - (point.count / stats.trendMax) * 90}`).join(' ')}
              className="trend-line"
            />
          </svg>
        </div>

        <div className="chart-card">
          <div className="chart-card__header">
            <h3 style={{ fontWeight: 'bold' }}>Average confidence</h3>
            <span>Model certainty</span>
          </div>
          <svg viewBox="0 0 360 160" className="line-chart" preserveAspectRatio="none" aria-label="Confidence trend">
            <line x1="20" x2="340" y1="130" y2="130" className="axis-line" />
            <line x1="20" x2="20" y1="20" y2="130" className="axis-line" />
            {stats.weeklyTrend.map((point, index) => {
              const x = 30 + index * 45
              const y = 130 - (point.confidence / 100) * 90
              return (
                <g key={`${point.label}-confidence`}>
                  <circle cx={x} cy={y} r="4" className="confidence-dot" />
                  <text x={x} y="150" textAnchor="middle" className="chart-label" style={{ fontSize: '10px', fill: '#607368' }}>{point.label.split(' ')[0]}</text>
                </g>
              )
            })}
            <polyline
              points={stats.weeklyTrend.map((point, index) => `${30 + index * 45},${130 - (point.confidence / 100) * 90}`).join(' ')}
              className="confidence-line"
            />
          </svg>
        </div>
      </div>
    </section>
  )
}
