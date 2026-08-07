/** Ikon SVG — satu sistem stroke currentColor, defs ada di index.html. */
export function Icon({ name, className = 'icon' }: { name: string; className?: string }) {
  return (
    <svg className={className} aria-hidden="true">
      <use href={`#${name}`} />
    </svg>
  )
}
