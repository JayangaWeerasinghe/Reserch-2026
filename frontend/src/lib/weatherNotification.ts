/**
 * Weather notification service.
 * Uses Open-Meteo free API — no API key needed.
 * Checks weather for farmer's saved district using district center coords.
 * Sends a browser notification with the current weather conditions for
 * that district, and keeps a small history the bell icon can show.
 */

// District center coordinates for Sri Lanka
const DISTRICT_COORDS: Record<string, { lat: number; lon: number }> = {
  'Colombo': { lat: 6.927, lon: 79.861 },
  'Kandy': { lat: 7.291, lon: 80.636 },
  'Galle': { lat: 6.053, lon: 80.220 },
  'Polonnaruwa': { lat: 7.940, lon: 81.000 },
  'Anuradhapura': { lat: 8.311, lon: 80.403 },
  'Kurunegala': { lat: 7.486, lon: 80.362 },
  'Ratnapura': { lat: 6.680, lon: 80.399 },
  'Badulla': { lat: 6.989, lon: 81.055 },
  'Matara': { lat: 5.945, lon: 80.535 },
  'Hambantota': { lat: 6.124, lon: 81.118 },
  'Trincomalee': { lat: 8.577, lon: 81.233 },
  'Batticaloa': { lat: 7.717, lon: 81.700 },
  'Ampara': { lat: 7.301, lon: 81.672 },
  'Vavuniya': { lat: 8.751, lon: 80.497 },
  'Jaffna': { lat: 9.661, lon: 80.025 },
  'Puttalam': { lat: 8.031, lon: 79.844 },
  'Matale': { lat: 7.468, lon: 80.624 },
  'Nuwara Eliya': { lat: 6.970, lon: 80.770 },
  'Kegalle': { lat: 7.252, lon: 80.342 },
  'Kalutara': { lat: 6.583, lon: 79.960 },
  'Gampaha': { lat: 7.091, lon: 80.016 },
  'Monaragala': { lat: 6.872, lon: 81.350 },
}

// Default fallback for unknown districts
const DEFAULT_COORDS = { lat: 7.873, lon: 80.772 } // Center of Sri Lanka

interface WeatherAlert {
  message: string
  sinhalaMessage: string
}

export interface StoredNotification {
  id: string
  title: string
  body: string
  timestamp: number
  read: boolean
}

const NOTIFICATIONS_KEY = 'paddyguard_weather_notifications'
const MAX_STORED_NOTIFICATIONS = 20
export const WEATHER_NOTIFICATION_EVENT = 'paddyguard-weather-notification'

export function getNotifications(): StoredNotification[] {
  try {
    const raw = localStorage.getItem(NOTIFICATIONS_KEY)
    return raw ? (JSON.parse(raw) as StoredNotification[]) : []
  } catch {
    return []
  }
}

function saveNotification(title: string, body: string): void {
  const record: StoredNotification = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    title,
    body,
    timestamp: Date.now(),
    read: false,
  }
  const existing = getNotifications()
  const updated = [record, ...existing].slice(0, MAX_STORED_NOTIFICATIONS)
  localStorage.setItem(NOTIFICATIONS_KEY, JSON.stringify(updated))
  window.dispatchEvent(new CustomEvent(WEATHER_NOTIFICATION_EVENT))
}

export function markAllNotificationsRead(): void {
  const existing = getNotifications()
  if (existing.every((n) => n.read)) return
  const updated = existing.map((n) => ({ ...n, read: true }))
  localStorage.setItem(NOTIFICATIONS_KEY, JSON.stringify(updated))
  window.dispatchEvent(new CustomEvent(WEATHER_NOTIFICATION_EVENT))
}

function getDistrictCoords(district: string): { lat: number; lon: number } {
  // Try exact match first
  if (DISTRICT_COORDS[district]) return DISTRICT_COORDS[district]
  // Try partial match
  const key = Object.keys(DISTRICT_COORDS).find((k) =>
    district.toLowerCase().includes(k.toLowerCase()) ||
    k.toLowerCase().includes(district.toLowerCase())
  )
  return key ? DISTRICT_COORDS[key] : DEFAULT_COORDS
}

async function fetchWeather(lat: number, lon: number) {
  const url = new URL('https://api.open-meteo.com/v1/forecast')
  url.searchParams.set('latitude', lat.toString())
  url.searchParams.set('longitude', lon.toString())
  url.searchParams.set('hourly', 'precipitation,relativehumidity_2m,windspeed_10m')
  url.searchParams.set('current_weather', 'true')
  url.searchParams.set('forecast_days', '1')
  url.searchParams.set('timezone', 'Asia/Colombo')

  const r = await fetch(url.toString())
  if (!r.ok) throw new Error('Weather fetch failed')
  return r.json()
}

function buildCurrentWeatherMessage(
  district: string,
  data: {
    current_weather?: { temperature: number; windspeed: number; time: string }
    hourly: {
      time: string[]
      precipitation: number[]
      relativehumidity_2m: number[]
      windspeed_10m: number[]
    }
  }
): WeatherAlert {
  const hours = data.hourly
  const currentTime = data.current_weather?.time
  let idx = currentTime ? hours.time.indexOf(currentTime) : -1
  if (idx === -1) idx = 0

  const temperature = data.current_weather?.temperature ?? null
  const humidity = hours.relativehumidity_2m[idx] ?? null
  const rain = hours.precipitation[idx] ?? 0
  const wind = data.current_weather?.windspeed ?? hours.windspeed_10m[idx] ?? null

  const tempStr = temperature !== null ? `${temperature.toFixed(1)}°C` : 'N/A'
  const humidityStr = humidity !== null ? `${humidity}%` : 'N/A'
  const windStr = wind !== null ? `${wind.toFixed(0)} km/h` : 'N/A'

  return {
    message: `Current weather in ${district}: ${tempStr}, ${humidityStr} humidity, ${rain.toFixed(1)}mm rain, wind ${windStr}.`,
    sinhalaMessage: `${district} හි වර්තමාන කාලගුණය: උෂ්ණත්වය ${tempStr}, ආර්ද්‍රතාවය ${humidityStr}, වර්ෂාපතනය ${rain.toFixed(1)}mm, සුළං වේගය ${windStr}.`,
  }
}

async function sendBrowserNotification(alert: WeatherAlert): Promise<void> {
  const title = 'PaddyGuard AI — කාලගුණ යාවත්කාලීනය'
  const body = `${alert.sinhalaMessage}\n\n${alert.message}`

  saveNotification(title, body)

  if (!('Notification' in window)) return
  if (Notification.permission !== 'granted') return

  const icon = '/favicon.svg'

  if ('serviceWorker' in navigator) {
    const reg = await navigator.serviceWorker.ready.catch(() => null)
    if (reg) {
      reg.showNotification(title, { body, icon, badge: icon, tag: 'weather-current' })
      return
    }
  }
  // Fallback to basic notification
  new Notification(title, { body, icon })
}

const LAST_CHECK_KEY = 'paddyguard_weather_last_check'

export async function checkWeatherAndNotify(): Promise<void> {
  try {
    // Only check once per 6 hours to avoid spam
    const lastCheck = localStorage.getItem(LAST_CHECK_KEY)
    if (lastCheck) {
      const diff = Date.now() - parseInt(lastCheck)
      if (diff < 6 * 60 * 60 * 1000) return
    }

    const district = localStorage.getItem('paddyguard_location')
    if (!district) return // User skipped location permission

    if (Notification.permission === 'denied') return
    if (Notification.permission === 'default') {
      await Notification.requestPermission()
    }
    if (Notification.permission !== 'granted') return

    const coords = getDistrictCoords(district)
    const weatherData = await fetchWeather(coords.lat, coords.lon)
    const alert = buildCurrentWeatherMessage(district, weatherData)
    await sendBrowserNotification(alert)

    localStorage.setItem(LAST_CHECK_KEY, Date.now().toString())
  } catch {
    // Weather check is non-critical — never throw
  }
}

export function scheduleWeatherChecks(): void {
  // Check on app load
  checkWeatherAndNotify()
  // Check every 6 hours while app is open
  setInterval(checkWeatherAndNotify, 6 * 60 * 60 * 1000)
}
