import React from 'react'
import { Icon, type IconName } from './Icon'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: IconName
  hint?: string
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, hint, className = '', id, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

    return (
      <div className="form-group">
        {label && (
          <label htmlFor={inputId} className="form-label">
            {label}
          </label>
        )}
        <div className="input-wrapper">
          {icon && <Icon name={icon} size={16} className="input-icon" />}
          <input
            ref={ref}
            id={inputId}
            className={`form-input ${icon ? 'form-input--with-icon' : ''} ${error ? 'form-input--error' : ''} ${className}`.trim()}
            {...props}
          />
        </div>
        {error ? <p className="form-error">{error}</p> : hint ? <p className="form-hint">{hint}</p> : null}
      </div>
    )
  }
)

Input.displayName = 'Input'
