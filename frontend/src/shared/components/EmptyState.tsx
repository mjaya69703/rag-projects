import React from 'react'
import { Button } from './Button'
import { Icon, type IconName } from './Icon'

interface EmptyStateProps {
  icon?: IconName
  title: string
  description?: string
  actionLabel?: string
  actionIcon?: IconName
  onAction?: () => void
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon = 'sparkles',
  title,
  description,
  actionLabel,
  actionIcon,
  onAction,
}) => {
  return (
    <div className="empty-state">
      <div className="empty-state__icon-wrap">
        <Icon name={icon} size={32} />
      </div>
      <h4 className="empty-state__title">{title}</h4>
      {description && <p className="empty-state__description">{description}</p>}
      {actionLabel && onAction && (
        <Button variant="primary" icon={actionIcon} onClick={onAction} className="empty-state__action">
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
