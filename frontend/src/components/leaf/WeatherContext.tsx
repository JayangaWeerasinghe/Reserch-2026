import { useState, useEffect } from 'react'
import { refreshWeather } from '@/lib/leafApi'
import { leafTranslations } from '@/lib/leafTranslations'

interface WeatherContextProps {
  caseId: string
  initialLocation: { city: string; district: string | null; latitude: number; longitude: number }
  initialWeather: any
  initialRisk: any
  onWeatherUpdate: (data: any) => void
}

export default function WeatherContext({
  caseId,
  initialLocation,
  initialWeather,
  initialRisk,
  onWeatherUpdate,
}: WeatherContextProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [lang, setLang] = useState<'en' | 'si'>('en')

  useEffect(() => {
    const storedLang = localStorage.getItem('paddyguard_leaf_lang') as 'en' | 'si'
    if (storedLang) setLang(storedLang)
  }, [caseId])

  const t = leafTranslations[lang]

  const handleRefresh = async () => {
    try {
      setLoading(true)
      setError('')
      const data = await refreshWeather(caseId)
      onWeatherUpdate(data)
    } catch {
      setError(lang === 'si' ? 'දේශගුණික දත්ත යාවත්කාලීන කිරීමට අපොහොසත් විය' : 'Failed to refresh weather')
    } finally {
      setLoading(false)
    }
  }

  const weather = initialWeather
  const location = initialLocation
  const riskScore = initialRisk?.climate_risk_score ?? 0

  return (
    <div className="weather-dashboard animate-entrance">
      <div className="weather-header">
        <h3 style={{ margin: 0, fontWeight: 'bold' }}>{t.liveWeatherTitle}</h3>
        <button onClick={handleRefresh} disabled={loading} className="refresh-btn">
          {loading ? t.refreshing : t.refreshWeatherBtn}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="weather-meta">
        <p>
          <strong>{t.location}:</strong> {location.city}
          {location.district ? `, ${location.district}` : ''} ({location.latitude?.toFixed(4)},{' '}
          {location.longitude?.toFixed(4)})
        </p>
        <p className="muted">{t.sourceOpenMeteo}</p>
      </div>

      <div className="weather-grid">
        <div className="weather-tile tile-temp">
          <span className="tile-label">{t.meanTemp7d}</span>
          <div className="tile-value">{weather?.history_mean_temperature_c?.toFixed(1) ?? '-'}°C</div>
        </div>
        <div className="weather-tile tile-humidity">
          <span className="tile-label">{t.meanHumid7d}</span>
          <div className="tile-value">{weather?.history_mean_humidity_pct?.toFixed(1) ?? '-'}%</div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${Math.min(100, weather?.history_mean_humidity_pct || 0)}%` }}
            ></div>
          </div>
        </div>
        <div className="weather-tile tile-rain">
          <span className="tile-label">{t.totalRain7d}</span>
          <div className="tile-value">{weather?.history_total_rainfall_mm?.toFixed(1) ?? '-'} mm</div>
        </div>
        <div className="weather-tile tile-wind">
          <span className="tile-label">{t.meanMaxWind}</span>
          <div className="tile-value">{weather?.history_mean_max_wind_kmh?.toFixed(1) ?? 0} km/h</div>
        </div>
        <div className="weather-tile tile-forecast">
          <span className="tile-label">{t.forecast3d}</span>
          <div className="forecast-mini">
            <div>Max: {weather?.forecast_mean_max_temperature_c?.toFixed(1) ?? '-'}°C</div>
            <div>Min: {weather?.forecast_mean_min_temperature_c?.toFixed(1) ?? '-'}°C</div>
            <div>Rain: {weather?.forecast_total_rainfall_mm?.toFixed(1) ?? '-'} mm</div>
            <div>Hum: {weather?.forecast_mean_humidity_pct?.toFixed(1) ?? '-'}%</div>
          </div>
        </div>
        <div className="weather-tile tile-risk">
          <span className="tile-label">{t.climateRiskScore}</span>
          <div className="tile-value">{riskScore}%</div>
          <div className="progress-bar">
            <div className="progress-fill risk-fill" style={{ width: `${riskScore}%` }}></div>
          </div>
        </div>
      </div>
      <div className="warning disclaimer">
        <strong>Important:</strong> Climate-risk estimate is a research estimate.
      </div>
    </div>
  )
}
