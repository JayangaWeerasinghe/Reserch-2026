import { forwardRef, useState } from 'react'
import type { InputHTMLAttributes } from 'react'
import { Eye, EyeOff } from 'lucide-react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  sinhalaLabel?: boolean
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, sinhalaLabel, className = '', type = 'text', ...rest }, ref) => {
    const [show, setShow] = useState(false)
    const isPassword = type === 'password'

    return (
      <div className="w-full">
        {label && (
          <label className={`mb-1.5 block text-sm font-medium text-forest ${sinhalaLabel ? 'font-sinhala' : ''}`}>
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            type={isPassword && show ? 'text' : type}
            className={`h-12 w-full rounded-xl border bg-beige px-4 text-forest placeholder:text-forest-muted/70
              outline-none transition-colors focus:border-forest
              ${error ? 'border-red-soft' : 'border-beige'} ${className}`}
            {...rest}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-forest-muted"
              tabIndex={-1}
            >
              {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          )}
        </div>
        {error && <p className="mt-1 text-sm text-red-soft">{error}</p>}
      </div>
    )
  }
)

Input.displayName = 'Input'
export default Input
