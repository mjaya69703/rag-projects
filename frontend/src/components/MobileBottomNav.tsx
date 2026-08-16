import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Icon, type IconName } from '../shared/components'

interface NavItem {
  to?: string
  label: string
  icon: IconName
  onClick?: () => void
  isAction?: boolean
}

interface MobileBottomNavProps {
  onOpenMenu: () => void
  isMenuOpen: boolean
}

export function MobileBottomNav({ onOpenMenu, isMenuOpen }: MobileBottomNavProps) {
  const location = useLocation()

  const items: NavItem[] = [
    { to: '/', label: 'Chat', icon: 'chat' },
    { to: '/library', label: 'Library', icon: 'library' },
    { to: '/flashcards', label: 'Cards', icon: 'cards' },
    { to: '/quiz', label: 'Quiz', icon: 'quiz' },
    {
      label: 'Menu',
      icon: isMenuOpen ? 'x' : 'menu',
      onClick: onOpenMenu,
      isAction: true,
    },
  ]

  // Check if current route is one of the secondary pages accessed via menu
  const isSecondaryActive = ['/progress', '/glossary', '/settings'].some((p) =>
    location.pathname.startsWith(p)
  )

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile Navigation">
      <div className="mobile-bottom-nav__inner">
        {items.map((item) => {
          if (item.isAction) {
            const isActive = isMenuOpen || isSecondaryActive
            return (
              <button
                key={item.label}
                type="button"
                className={`mobile-nav-btn ${isActive ? 'active' : ''}`}
                onClick={item.onClick}
                aria-label={item.label}
              >
                <div className="mobile-nav-icon-wrap">
                  <Icon name={item.icon} size={20} />
                  {isSecondaryActive && !isMenuOpen && <span className="mobile-nav-dot" />}
                </div>
                <span className="mobile-nav-label">{item.label}</span>
              </button>
            )
          }

          return (
            <NavLink
              key={item.to}
              to={item.to!}
              className={({ isActive }) => `mobile-nav-btn ${isActive ? 'active' : ''}`}
              end={item.to === '/'}
            >
              <div className="mobile-nav-icon-wrap">
                <Icon name={item.icon} size={20} />
              </div>
              <span className="mobile-nav-label">{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
