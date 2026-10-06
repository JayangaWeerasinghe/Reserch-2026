import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ImagePlus, X, MapPin, Globe, AlertTriangle, MessageCircle } from 'lucide-react'
import toast from 'react-hot-toast'

// Scoped UI Primitives
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

// Scoped Leaf components
import AnalysisProgress from '@/components/leaf/AnalysisProgress'
import WeatherContext from '@/components/leaf/WeatherContext'
import MetricCardWithTooltip from '@/components/leaf/MetricCardWithTooltip'
import HistoryTable from '@/components/leaf/HistoryTable'
import ActivityModal from '@/components/leaf/ActivityModal'
import UserAnalyticsOverview from '@/components/leaf/UserAnalyticsOverview'

// Scoped Leaf APIs & helpers
import { analyzeLeaf, deleteCase, getCases, getUserHistory, getLeafAuth } from '@/lib/leafApi'
import type { AnalyzeResult, CaseSummary } from '@/lib/leafApi'
import { useAuthStore } from '@/store/authStore'
import { leafTranslations } from '@/lib/leafTranslations'

import '@/components/leaf/leafStyles.css'

type Tab = 'analyze' | 'history'

const LEAF_ANALYSIS_STORAGE_KEY = 'paddyguard_leaf_analysis_state'

type PersistedLeafAnalysisState = {
  tab: Tab
  lang: 'en' | 'si'
  showLocation: boolean
  city: string
  latitude: string
  longitude: string
  fieldArea: string
  affectedField: string
  expectedYield: string
  treatmentApplied: boolean
  preview: string | null
  result: AnalyzeResult | null
  error: string
  duplicateError: any
}

export default function LeafDisease() {
  const [tab, setTab] = useState<Tab>('analyze')
  const [lang, setLang] = useState<'en' | 'si'>('en')

  // Form fields
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [showLocation, setShowLocation] = useState(false)
  const [city, setCity] = useState('Gampaha')
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const [fieldArea, setFieldArea] = useState('1')
  const [affectedField, setAffectedField] = useState('10')
  const [expectedYield, setExpectedYield] = useState('1800')
  const [treatmentApplied, setTreatmentApplied] = useState(false)

  // Analysis states
  const [analyzing, setAnalyzing] = useState(false)
  const [result, setResult] = useState<AnalyzeResult | null>(null)
  const [error, setError] = useState('')
  const [duplicateError, setDuplicateError] = useState<any>(null)

  // History states
  const [cases, setCases] = useState<CaseSummary[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [selectedCase, setSelectedCase] = useState<CaseSummary | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const leafAuth = getLeafAuth()
  const isStaff = leafAuth?.role === 'EXPERT' || leafAuth?.role === 'SUPER_ADMIN'
  const [sessionExpired, setSessionExpired] = useState(false)

  function handleReLogin() {
    logout()
    navigate('/login')
  }

  const clearLeafAnalysisState = () => {
    if (preview?.startsWith('blob:')) {
      URL.revokeObjectURL(preview)
    }

    sessionStorage.removeItem(LEAF_ANALYSIS_STORAGE_KEY)
    setResult(null)
    setError('')
    setDuplicateError(null)
    setPreview(null)
    setFile(null)
  }

  useEffect(() => {
    try {
      const rawState = sessionStorage.getItem(LEAF_ANALYSIS_STORAGE_KEY)
      if (!rawState) return

      const savedState = JSON.parse(rawState) as Partial<PersistedLeafAnalysisState>

      if (savedState.lang === 'si' || savedState.lang === 'en') {
        setLang(savedState.lang)
      }

      setTab(savedState.tab === 'history' ? 'history' : 'analyze')
      setShowLocation(Boolean(savedState.showLocation))
      setCity(savedState.city || 'Gampaha')
      setLatitude(savedState.latitude || '')
      setLongitude(savedState.longitude || '')
      setFieldArea(savedState.fieldArea || '1')
      setAffectedField(savedState.affectedField || '10')
      setExpectedYield(savedState.expectedYield || '1800')
      setTreatmentApplied(Boolean(savedState.treatmentApplied))

      if (savedState.preview) {
        setPreview(savedState.preview)
      }

      if (savedState.result) {
        setResult(savedState.result)
      }

      if (savedState.error) {
        setError(savedState.error)
      }

      if (savedState.duplicateError) {
        setDuplicateError(savedState.duplicateError)
      }
    } catch {
      sessionStorage.removeItem(LEAF_ANALYSIS_STORAGE_KEY)
    }
  }, [])

  useEffect(() => {
    const persistedState: PersistedLeafAnalysisState = {
      tab,
      lang,
      showLocation,
      city,
      latitude,
      longitude,
      fieldArea,
      affectedField,
      expectedYield,
      treatmentApplied,
      preview,
      result,
      error,
      duplicateError,
    }

    if ((result || error || duplicateError || preview) && !(file && !preview)) {
      sessionStorage.setItem(LEAF_ANALYSIS_STORAGE_KEY, JSON.stringify(persistedState))
      return
    }

    if (!file && !preview && !result && !error && !duplicateError) {
      sessionStorage.removeItem(LEAF_ANALYSIS_STORAGE_KEY)
    }
  }, [tab, lang, showLocation, city, latitude, longitude, fieldArea, affectedField, expectedYield, treatmentApplied, preview, result, error, duplicateError, file])

  // Initialize language selection
  useEffect(() => {
    const storedLang = localStorage.getItem('paddyguard_leaf_lang') as 'en' | 'si'
    if (storedLang) {
      setLang(storedLang)
    }
  }, [])

  // Load history when switching tab
  useEffect(() => {
    if (tab === 'history') loadHistory()
  }, [tab])

  const t = leafTranslations[lang]

  const toggleLanguage = () => {
    const newLang = lang === 'en' ? 'si' : 'en'
    setLang(newLang)
    localStorage.setItem('paddyguard_leaf_lang', newLang)
    toast.success(newLang === 'en' ? 'Language switched to English' : 'භාෂාව සිංහලට වෙනස් කරන ලදී')
  }

  async function loadHistory() {
    setLoadingHistory(true)
    setSessionExpired(false)
    try {
      const data = isStaff ? await getCases(leafAuth?.username) : await getUserHistory()
      setCases(Array.isArray(data) ? data : [])
    } catch (err: unknown) {
      if ((err as { response?: { status?: number } }).response?.status === 401) {
        setSessionExpired(true)
      } else {
        toast.error('Failed to load history')
      }
    } finally {
      setLoadingHistory(false)
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0]
    if (!selected) return

    if (preview?.startsWith('blob:')) {
      URL.revokeObjectURL(preview)
    }

    setFile(selected)

    const reader = new FileReader()
    reader.onload = () => {
      const nextPreview = typeof reader.result === 'string' ? reader.result : URL.createObjectURL(selected)
      setPreview(nextPreview)
    }
    reader.readAsDataURL(selected)

    setDuplicateError(null)
    setError('')
    e.target.value = ''
  }

  function clearFile() {
    clearLeafAnalysisState()
  }

  function useMyLocation() {
    if (!navigator.geolocation) {
      toast.error('Geolocation not supported')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(String(pos.coords.latitude))
        setLongitude(String(pos.coords.longitude))
        toast.success('Location captured')
      },
      () => toast.error('Could not get location')
    )
  }

  async function handleAnalyze() {
    if (!file) {
      toast.error(t.selectLeafImageError)
      return
    }

    setAnalyzing(true)
    setResult(null)
    setError('')
    setDuplicateError(null)

    try {
      const data = await analyzeLeaf({
        file,
        city: city || undefined,
        latitude: latitude ? Number(latitude) : undefined,
        longitude: longitude ? Number(longitude) : undefined,
        field_area_acres: Number(fieldArea) || 1,
        affected_field_percentage: Number(affectedField) || 0,
        rice_variety: 'Unknown',
        growth_stage: 'Tillering',
        created_by: leafAuth?.username || user?.email,
      })
      setResult(data)
    } catch (err: unknown) {
      const respData = (err as any).response?.data
      if (respData && respData.error === 'duplicate_upload') {
        setDuplicateError(respData)
      } else {
        const msg = respData?.detail || (err as Error).message || 'Analysis failed. Please try again.'
        setError(msg)
        toast.error(msg)
      }
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleDelete(caseId: string) {
    try {
      await deleteCase(caseId)
      setCases((prev) => prev.filter((c) => c.case_id !== caseId))
      toast.success('Case deleted successfully')
    } catch {
      toast.error('Failed to delete case')
    }
  }

  const handleWeatherUpdate = (updatedData: any) => {
    if (result) {
      setResult({
        ...result,
        weather: updatedData.weather,
        yield_loss: updatedData.yield_loss,
        calculation_breakdown: {
          ...result.calculation_breakdown,
          ...updatedData.calculation_breakdown,
        },
      })
    }
  }

  // Calculation Tooltips
  const getDiseaseTooltip = () => (
    <>
      <p>The EfficientNetB3 model compares the image against four trained classes.</p>
      <p>The displayed disease is the class with the highest softmax probability.</p>
      <p>Classes are Bacterial Blight, Brown Spot, Healthy, and Leaf Blast.</p>
    </>
  )

  const getConfidenceTooltip = (br: any) => {
    if (!br?.disease) return null
    return (
      <>
        <p>Confidence is calculated using softmax from the model logits.</p>
        <p>Formula:<br />confidence = exp(selected logit) / sum(exp(all logits)) × 100</p>
        <p className="mt-2"><em>Model confidence is not the same as guaranteed diagnostic accuracy.</em></p>
        <div className="mt-2">
          <strong>Class Probabilities:</strong>
          <ul className="text-sm list-disc pl-4 mt-1">
            {Object.entries(br.disease.class_probabilities || {}).map(([c, p]: [string, any]) => (
              <li key={c}>{c.replace(/_/g, ' ')}: {(p * 100).toFixed(2)}%</li>
            ))}
          </ul>
        </div>
      </>
    )
  }

  const getSeverityTooltip = (br: any) => {
    if (!br?.severity) return null
    return (
      <>
        <p>Severity estimates how much of the visible leaf area appears affected by disease symptoms.</p>
        <p>Current severity is a Grad-CAM attention-area proxy.</p>
        <p>Heatmap values are normalized from 0 to 1.</p>
        <p>Pixels ≥ {br.severity.activation_threshold} are counted as active.</p>
        <p>Formula:<br />severity = active Grad-CAM pixels / total pixels × 100</p>
        <p className="mt-2 text-xs">
          Active pixels: {br.severity.active_pixel_count}<br />
          Total pixels: {br.severity.total_pixel_count}
        </p>
        <ul className="text-xs list-disc pl-4 mt-2 mb-2">
          <li>0–5% Negligible</li>
          <li>5–15% Mild</li>
          <li>15–30% Moderate</li>
          <li>30–50% Severe</li>
          <li>above 50% Critical</li>
        </ul>
        <p className="text-xs text-yellow-600"><em>This is an indicative attention proxy, not an exact lesion segmentation result.</em></p>
      </>
    )
  }

  const getClimateTooltip = (br: any) => {
    if (!br?.climate) return null
    return (
      <>
        <p>Climate Risk represents how favorable current or supplied environmental conditions are for disease development.</p>
        <p>climate risk = 100 × (<br />
          {br.climate.weights.humidity} × humidity risk +<br />
          {br.climate.weights.rainfall} × rainfall risk +<br />
          {br.climate.weights.temperature} × temperature risk +<br />
          {br.climate.weights.forecast_rain} × forecast-rain risk<br />
        )</p>
        <div className="mt-2 text-xs">
          <strong>Inputs:</strong>
          <ul className="list-disc pl-4 mt-1">
            <li>7d Temp: {br.climate.history_mean_temperature_c}°C</li>
            <li>7d Hum: {br.climate.history_mean_humidity_pct}%</li>
            <li>7d Rain: {br.climate.history_total_rainfall_mm}mm</li>
            <li>Forecast Rain: {br.climate.forecast_total_rainfall_mm}mm</li>
          </ul>
        </div>
      </>
    )
  }

  const getLossTooltip = (br: any) => {
    if (!br?.loss) return null
    return (
      <>
        <p>Loss Risk estimates the potential crop impact based on disease severity and other configured risk factors.</p>
        <p>raw loss = disease base risk + 0.32 × severity percentage + 0.18 × affected-field percentage + 0.12 × climate-risk percentage</p>
        <p className="mt-2">loss risk = raw loss × growth-stage factor {br.loss.treatment_applied ? '× 0.82 (treatment)' : ''}</p>
      </>
    )
  }

  const getRiskLevelTooltip = () => (
    <>
      <ul className="list-disc pl-4">
        <li>below 5% = Low</li>
        <li>5% to below 15% = Moderate</li>
        <li>15% to below 30% = High</li>
        <li>30% or above = Critical</li>
      </ul>
    </>
  )

  const getEstimatedLossTooltip = (br: any) => {
    if (!br?.estimated_loss) return null
    return (
      <>
        <p>Estimated Loss converts the predicted loss risk into an approximate crop quantity.</p>
        <p>expected healthy yield = field area in acres × expected yield in kg per acre</p>
        <p className="mt-2">estimated production loss = expected healthy yield × loss-risk percentage / 100</p>
      </>
    )
  }

  const getCaseIdTooltip = () => (
    <p>The Case ID identifies the saved prediction and can later connect farmer feedback, expert validation, and actual harvest outcomes.</p>
  )

  const openCalculationGuide = () => {
    if (typeof window === 'undefined') return
    const pdfUrl = new URL('/docs/PaddyGuard_AI_Prediction_Metrics_Explanation_Guide.pdf', window.location.origin).toString()
    window.open(pdfUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="space-y-6 leaf-module">
      {/* Top bar with Tab navigation and Language Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-2 rounded-xl bg-beige p-1 flex-1 max-w-xs">
          {(['analyze', 'history'] as Tab[]).map((tTab) => (
            <button
              key={tTab}
              onClick={() => setTab(tTab)}
              className={`flex-1 rounded-lg py-2 text-sm font-semibold capitalize transition-colors ${
                tab === tTab ? 'bg-white text-forest shadow-sm' : 'text-forest-muted'
              }`}
            >
              {tTab === 'analyze' ? (lang === 'si' ? 'විශ්ලේෂණය' : 'Analyze') : (lang === 'si' ? 'ඉතිහාසය' : 'My History')}
            </button>
          ))}
        </div>

        <button
          onClick={toggleLanguage}
          className="flex items-center gap-1.5 rounded-xl border border-forest/20 bg-white px-4 py-2 text-sm font-semibold text-forest shadow-sm hover:bg-beige/20 transition-all width-auto"
          style={{ width: 'auto' }}
        >
          <Globe className="h-4 w-4" />
          {lang === 'en' ? 'සිංහල' : 'English'}
        </button>
      </div>

      {tab === 'analyze' && (
        <div className="leaf-grid">
          {/* Left Column - Field Analysis Input Card */}
          <div className="card analysis-card">
            <div className="analysis-hero">
              <span className="analysis-hero__topline">{t.fieldAnalysis}</span>
              <h2 className="analysis-hero__title">{t.startCropHealthCheck}</h2>
              <p className="analysis-hero__text">{t.heroText}</p>
              <ul className="analysis-hero__list">
                <li>{t.bullet1}</li>
                <li>{t.bullet2}</li>
                <li>{t.bullet3}</li>
                <li>{t.bullet4}</li>
              </ul>
              <div className="analysis-hero__mini">
                <strong>{lang === 'si' ? 'PaddyGuard AI සපයයි:' : 'PaddyGuard AI can provide:'}</strong> {t.aiCapabilities}
              </div>
            </div>

            <div className="analysis-form">
              <label className="upload-field">
                <span className="form-label">{t.riceLeafImage}</span>
                {!preview ? (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex min-h-[160px] w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-beige bg-beige/10 hover:border-amber transition-all"
                  >
                    <ImagePlus className="h-8 w-8 text-amber" />
                    <span className="text-sm text-forest-muted">
                      {lang === 'si' ? 'පින්තූරය තෝරන්න' : 'Click to select a leaf image'}
                    </span>
                  </button>
                ) : (
                  <div className="relative">
                    <img src={preview} alt="Leaf preview" className="preview-image" />
                    <button
                      type="button"
                      onClick={clearFile}
                      className="absolute right-2 top-2 rounded-full bg-white/90 p-1.5 text-forest shadow hover:bg-white"
                      style={{ width: 'auto' }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </label>

              <button
                type="button"
                onClick={() => setShowLocation((s) => !s)}
                className="flex items-center gap-1.5 text-sm font-medium text-forest hover:text-forest-light transition-all"
                style={{ background: 'none', color: '#344F1F', border: 'none', width: 'auto', padding: 0, boxShadow: 'none' }}
              >
                <MapPin className="h-4 w-4" />
                {t.locationFieldDetails} {showLocation ? '−' : '+'}
              </button>

              {showLocation && (
                <div className="space-y-4 animate-entrance border-t border-beige/40 pt-3">
                  <Input label={t.city} value={city} onChange={(e) => setCity(e.target.value)} required />
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="Latitude" value={latitude} onChange={(e) => setLatitude(e.target.value)} />
                    <Input label="Longitude" value={longitude} onChange={(e) => setLongitude(e.target.value)} />
                  </div>
                  <Button variant="ghost" size="sm" onClick={useMyLocation} className="w-full justify-start text-xs">
                    <MapPin className="h-4 w-4 mr-1" /> {t.useMyLocation}
                  </Button>
                </div>
              )}

              <div className="form-grid">
                <Input label={t.fieldAreaAcres} type="number" min="0.1" step="0.1" value={fieldArea} onChange={(e) => setFieldArea(e.target.value)} required />
                <Input label={t.affectedFieldPct} type="number" min="0" max="100" value={affectedField} onChange={(e) => setAffectedField(e.target.value)} required />
              </div>

              <div className="form-grid">
                <Input label={t.expectedYield} type="number" min="1" value={expectedYield} onChange={(e) => setExpectedYield(e.target.value)} />
              </div>

              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={treatmentApplied}
                  onChange={(e) => setTreatmentApplied(e.target.checked)}
                />
                <span>{t.treatmentApplied}</span>
              </label>

              <button
                onClick={handleAnalyze}
                disabled={!file || analyzing}
                className="primary-submit-btn"
              >
                {analyzing ? t.analyzingBtn : t.analyzeBtn}
              </button>
            </div>
          </div>

          {/* Right Column - AI Analysis Results Card */}
          <div className="card result-card">
            <div className="result-card__header">
              <h2>{t.result}</h2>
              <span className="result-card__pill">{t.aiAnalysisBadge}</span>
            </div>

            {duplicateError && !analyzing && (
              <div className="warning animate-entrance">
                <h3 className="font-bold text-amber">⚠️ {t.duplicateDetected}</h3>
                <p>{duplicateError.message || t.duplicateMsg}</p>
                {duplicateError.retry_after_seconds !== undefined && (
                  <p style={{ marginTop: '0.5rem', fontWeight: 'bold' }}>
                    {t.tryAgainIn} {Math.ceil(duplicateError.retry_after_seconds / 60)} {t.minutes}.
                  </p>
                )}
              </div>
            )}

            {analyzing && <AnalysisProgress isComplete={false} hasError={false} />}
            {error && !analyzing && <AnalysisProgress isComplete={false} hasError={true} />}

            {!result && !analyzing && !error && !duplicateError && (
              <div className="result-card__empty">
                <div className="result-card__empty-icon">📷</div>
                <p>{t.emptyResultsPlaceholder}</p>
              </div>
            )}

            {result?.prediction?.status === 'OOD' && !analyzing && (
              <div className="warning animate-entrance">
                <h3>{t.oodTitle}</h3>
                <p>{result.prediction.prediction}</p>
                <p>{t.confidence}: {(result.prediction.confidence * 100).toFixed(2)}%</p>
              </div>
            )}

            {result?.prediction?.needs_expert_review && !analyzing && (
              <div className="warning animate-entrance">
                <h3 className="font-bold">{t.expertReviewRequired}</h3>
                <p>{t.expertReviewMsg}</p>
                <p>{t.confidence}: {(result.prediction.confidence * 100).toFixed(2)}%</p>
                {result.case_id && <p className="text-xs font-mono mt-1">Case ID: {result.case_id}</p>}
              </div>
            )}

            {result?.prediction?.status === 'KNOWN' && !analyzing && (
              <div className="animate-entrance space-y-4">
                {(() => {
                  const yieldLoss = result.yield_loss as any
                  return (
                    <>
                      <div className="metric-grid">
                        <MetricCardWithTooltip
                          label={t.disease}
                          value={result.prediction.prediction.replace(/_/g, ' ')}
                          tooltipContent={getDiseaseTooltip()}
                        />
                        <MetricCardWithTooltip
                          label={t.confidence}
                          value={`${(result.prediction.confidence * 100).toFixed(2)}%`}
                          tooltipContent={getConfidenceTooltip(result.calculation_breakdown)}
                        />
                        <MetricCardWithTooltip
                          label={t.severity}
                          value={`${result.prediction.severity_percentage}% (${result.severity_level})`}
                          tooltipContent={getSeverityTooltip(result.calculation_breakdown)}
                        />
                        <MetricCardWithTooltip
                          label={t.lossRisk}
                          value={`${yieldLoss?.predicted_loss_percentage ?? 0}%`}
                          tooltipContent={getLossTooltip(result.calculation_breakdown)}
                        />
                        <MetricCardWithTooltip
                          label={t.riskLevel}
                          value={yieldLoss?.risk_level ?? 'N/A'}
                          tooltipContent={getRiskLevelTooltip()}
                        />
                        <MetricCardWithTooltip
                          label={t.climateRisk}
                          value={`${yieldLoss?.climate_risk_score ?? 0}%`}
                          tooltipContent={getClimateTooltip(result.calculation_breakdown)}
                        />
                        {yieldLoss?.estimated_loss_kg != null && (
                          <MetricCardWithTooltip
                            label={t.estimatedLoss}
                            value={`${yieldLoss.estimated_loss_kg} kg`}
                            tooltipContent={getEstimatedLossTooltip(result.calculation_breakdown)}
                          />
                        )}
                        <MetricCardWithTooltip
                          label={t.caseId}
                          value={result.case_id.substring(0, 12) + '...'}
                          tooltipContent={getCaseIdTooltip()}
                        />
                      </div>

                      <div className="result-guide-box">
                        <button type="button" className="guide-button" onClick={openCalculationGuide}>
                          {t.calculationGuideBtn}
                        </button>
                        <span className="guide-languages">Available in English | සිංහල | தமிழ்</span>
                      </div>

                      <p className="method-note">{t.methodNote}</p>

                      {result.prediction.gradcam_base64 && (
                        <div className="gradcam animate-entrance">
                          <h3>{t.gradCamTitle}</h3>
                          <img src={`data:image/png;base64,${result.prediction.gradcam_base64}`} alt="Grad-CAM visualization" />
                          <small className="disclaimer">{t.gradCamDisclaimer}</small>
                        </div>
                      )}

                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={() =>
                          navigate('/chat', {
                            state: {
                              initialMessage: `Tell me about treatment for ${result.prediction.prediction}`,
                            },
                          })
                        }
                      >
                        <MessageCircle className="h-4 w-4" />
                        ප්‍රතිකාර | Treatment
                      </Button>

                      <WeatherContext
                        caseId={result.case_id}
                        initialLocation={result.location}
                        initialWeather={result.weather}
                        initialRisk={yieldLoss}
                        onWeatherUpdate={handleWeatherUpdate}
                      />

                      <div className="warning disclaimer">
                        <strong>Important:</strong> {yieldLoss?.warning || t.importantDisclaimer}
                      </div>
                    </>
                  )
                })()}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'history' && (
        <div className="space-y-6">
          {sessionExpired ? (
            <div className="card flex flex-col items-center gap-3 py-8 text-center">
              <AlertTriangle className="h-8 w-8 text-amber-dark" />
              <div>
                <p className="font-bold text-forest">Your session has expired</p>
                <p className="mt-1 text-sm text-forest-muted">
                  Please log out and log back in to continue viewing your history.
                </p>
              </div>
              <Button variant="primary" onClick={handleReLogin}>
                Log out &amp; sign in again
              </Button>
            </div>
          ) : (
            <>
              <UserAnalyticsOverview />

              <div className="card">
                <h2 className="text-lg font-bold text-forest mb-4" style={{ margin: '0 0 1rem 0' }}>{t.historyTitle}</h2>
                {loadingHistory ? (
                  <LoadingSpinner labelEn={t.loadingHistory} />
                ) : (
                  <HistoryTable cases={cases} onRowClick={setSelectedCase} onDelete={handleDelete} />
                )}
              </div>

              <ActivityModal caseData={selectedCase} onClose={() => setSelectedCase(null)} />
            </>
          )}
        </div>
      )}
    </div>
  )
}
