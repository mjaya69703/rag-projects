import React from 'react'
import { Icon, type IconName } from './Icon'

export type ButtonVariant = 'primary' | 'secondary' | 'glass' | 'danger' | 'warning' | 'ghost' | 'success'
export type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  iconPosition?: 'left' | 'right'
  loading?: boolean
  glow?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  loading = false,
  glow = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = 'btn'
  const variantClass = `btn--${variant}`
  const sizeClass = size !== 'md' ? `btn--${size}` : ''
  const glowClass = glow ? 'btn--glow' : ''
  const loadingClass = loading ? 'btn--loading' : ''

  return (
    <button
      className={`${baseClasses} ${variantClass} ${sizeClass} ${glowClass} ${loadingClass} ${className}`.trim()}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="btn__spinner" aria-hidden="true" />
      ) : icon && iconPosition === 'left' ? (
        <Icon name={icon} size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} className="btn__icon" />
      ) : null}
      {children && <span className="btn__label">{children}</span>}
      {!loading && icon && iconPosition === 'right' ? (
        <Icon name={icon} size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} className="btn__icon" />
      ) : null}
    </button>
  )
}
