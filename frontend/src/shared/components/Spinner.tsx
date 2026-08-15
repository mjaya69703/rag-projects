import React from 'react'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  text?: string
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className = '', text }) => {
  return (
    <div className={`spinner-container spinner--${size} ${className}`.trim()} role="status" aria-label="Loading">
      <div className="spinner-circle" />
      {text && <p className="spinner-text">{text}</p>}
    </div>
  )
}
