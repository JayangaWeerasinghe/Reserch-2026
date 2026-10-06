import { useState, useRef, useEffect } from 'react'

interface MetricCardWithTooltipProps {
  label: string
  value: string
  tooltipContent: React.ReactNode
}

export default function MetricCardWithTooltip({ label, value, tooltipContent }: MetricCardWithTooltipProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent | TouchEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('touchstart', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('touchstart', handleClickOutside)
    }
  }, [])

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
    }
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen])

  return (
    <div
      className="metric has-tooltip"
      ref={containerRef}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
      onClick={() => setIsOpen(true)}
      onFocus={() => setIsOpen(true)}
      onBlur={(e) => {
        if (containerRef.current && !containerRef.current.contains(e.relatedTarget as Node)) {
          setIsOpen(false)
        }
      }}
      tabIndex={0}
      aria-describedby={isOpen ? 'tooltip-content-' + label.replace(/\s+/g, '-') : undefined}
      aria-expanded={isOpen}
    >
      <span className="metric-label">
        {label}
        <svg
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          fill="currentColor"
          viewBox="0 0 16 16"
          className="info-icon"
          style={{ marginLeft: '4px', cursor: 'pointer', display: 'inline-block' }}
        >
          <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z" />
          <path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z" />
        </svg>
      </span>
      <strong>{value}</strong>

      {isOpen && (
        <div
          id={'tooltip-content-' + label.replace(/\s+/g, '-')}
          className="tooltip-popover"
          role="tooltip"
        >
          {tooltipContent}
        </div>
      )}
    </div>
  )
}
