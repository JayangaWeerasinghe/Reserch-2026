import { useState, useEffect } from 'react'

const STAGES = [
  'Uploading image',
  'Validating image',
  'Running EfficientNetB3 classification',
  'Checking OOD and confidence',
  'Generating Grad-CAM',
  'Estimating severity',
  'Resolving Sri Lankan location',
  'Retrieving live weather',
  'Calculating climate risk',
  'Estimating yield loss',
  'Saving case',
]

interface AnalysisProgressProps {
  isComplete: boolean
  hasError: boolean
}

export default function AnalysisProgress({ isComplete, hasError }: AnalysisProgressProps) {
  const [activeStage, setActiveStage] = useState(0)

  useEffect(() => {
    if (isComplete || hasError) return

    const interval = setInterval(() => {
      setActiveStage((curr) => {
        if (curr < STAGES.length - 1) {
          return curr + 1
        }
        return curr
      })
    }, 1200)

    return () => clearInterval(interval)
  }, [isComplete, hasError])

  return (
    <div className="analysis-progress">
      <h3 style={{ margin: '0 0 1rem 0', fontWeight: 'bold' }}>Analyzing Field Data</h3>
      <div className="stepper">
        {STAGES.map((stage, index) => {
          let statusClass = 'pending'
          if (isComplete) {
            statusClass = 'completed'
          } else if (hasError && index >= activeStage) {
            statusClass = index === activeStage ? 'failed' : 'pending'
          } else if (index < activeStage) {
            statusClass = 'completed'
          } else if (index === activeStage) {
            statusClass = 'active'
          }

          return (
            <div key={index} className={`step ${statusClass}`}>
              <div className="step-indicator">
                {statusClass === 'completed' && '✓'}
                {statusClass === 'failed' && '✕'}
                {statusClass === 'active' && <span className="pulse"></span>}
                {statusClass === 'pending' && <span className="dot"></span>}
              </div>
              <div className="step-label" style={{ fontSize: '0.9rem' }}>{stage}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
