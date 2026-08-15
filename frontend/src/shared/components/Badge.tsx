import React from 'react'
import { Icon, type IconName } from './Icon'

export type BadgeVariant = 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'neutral'

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  icon?: IconName
  dot?: boolean
  size?: 'sm' | 'md'
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'primary',
  icon,
  dot = false,
  size = 'md',
  className = '',
  ...props
}) => {
  return (
    <span className={`badge badge--${variant} badge--${size} ${className}`.trim()} {...props}>
      {dot && <span className="badge__dot" />}
      {icon && <Icon name={icon} size={size === 'sm' ? 10 : 12} className="badge__icon" />}
      <span className="badge__text">{children}</span>
    </span>
  )
}
