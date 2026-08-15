import React from 'react'
import { Icon, type IconName } from './Icon'

export interface TabItem {
  id: string
  label: string
  icon?: IconName
  badge?: string | number
}

interface TabsProps {
  items: TabItem[]
  activeId: string
  onChange: (id: string) => void
  className?: string
}

export const Tabs: React.FC<TabsProps> = ({ items, activeId, onChange, className = '' }) => {
  return (
    <div className={`tabs-wrapper ${className}`.trim()} role="tablist">
      {items.map((tab) => {
        const isActive = tab.id === activeId
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            className={`tab-btn ${isActive ? 'tab-btn--active' : ''}`}
            onClick={() => onChange(tab.id)}
          >
            {tab.icon && <Icon name={tab.icon} size={16} className="tab-icon" />}
            <span className="tab-label">{tab.label}</span>
            {tab.badge !== undefined && <span className="tab-badge">{tab.badge}</span>}
          </button>
        )
      })}
    </div>
  )
}
