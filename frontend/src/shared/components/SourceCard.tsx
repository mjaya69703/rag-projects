import React, { useState } from 'react'
import type { SourceRef } from '../types'
import { Badge } from './Badge'
import { Card } from './Card'
import { Icon } from './Icon'

interface SourceCardProps {
  source: SourceRef
  index?: number
}

export const SourceCard: React.FC<SourceCardProps> = ({ source, index }) => {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className={`source-card ${expanded ? 'source-card--expanded' : ''}`} padding="sm" hover>
      <div className="source-card__header" onClick={() => setExpanded(!expanded)} role="button">
        <div className="source-card__title-group">
          {index !== undefined && <span className="source-card__index">[{index + 1}]</span>}
          <span className="source-card__name">{source.source}</span>
          <Badge variant="neutral" size="sm">
            Hal. {source.page}
          </Badge>
          {source.heading && source.heading !== 'Intro' && (
            <span className="source-card__heading">• {source.heading}</span>
          )}
        </div>
        <Icon name={expanded ? 'chevron-down' : 'chevron-right'} size={14} className="source-card__chevron" />
      </div>
      {expanded && (
        <div className="source-card__content">
          <p className="source-card__text">{source.text}</p>
        </div>
      )}
    </Card>
  )
}
