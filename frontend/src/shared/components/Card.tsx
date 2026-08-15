import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean
  glow?: boolean
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export const Card: React.FC<CardProps> = ({
  children,
  glass = true,
  glow = false,
  hover = false,
  padding = 'md',
  className = '',
  ...props
}) => {
  const glassClass = glass ? 'card--glass' : 'card--solid'
  const glowClass = glow ? 'card--glow' : ''
  const hoverClass = hover ? 'card--hover' : ''
  const paddingClass = `card--p-${padding}`

  return (
    <div className={`card ${glassClass} ${glowClass} ${hoverClass} ${paddingClass} ${className}`.trim()} {...props}>
      {children}
    </div>
  )
}
