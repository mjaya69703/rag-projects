import React from 'react'
import { Card } from './Card'
import { Icon, type IconName } from './Icon'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: IconName
  trend?: string
  trendType?: 'positive' | 'negative' | 'neutral'
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendType = 'neutral',
}) => {
  return (
    <Card className="stat-card" hover>
      <div className="stat-card__header">
        <span className="stat-card__title">{title}</span>
        {icon && (
          <div className="stat-card__icon-wrap">
            <Icon name={icon} size={18} />
          </div>
        )}
      </div>
      <div className="stat-card__value">{value}</div>
      {(subtitle || trend) && (
        <div className="stat-card__footer">
          {trend && <span className={`stat-card__trend stat-card__trend--${trendType}`}>{trend}</span>}
          {subtitle && <span className="stat-card__subtitle">{subtitle}</span>}
        </div>
      )}
    </Card>
  )
}
