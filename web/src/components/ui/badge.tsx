import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex max-w-full items-center gap-1 overflow-hidden rounded-full border px-2.5 py-0.5 text-xs font-medium text-ellipsis whitespace-nowrap transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/10 text-primary',
        secondary: 'border-transparent bg-secondary text-secondary-foreground',
        outline: 'text-foreground',
        // Status tints — mirror the Streamlit STATUS_COLORS palette.
        blue: 'border-transparent',
        violet: 'border-transparent',
        red: 'border-transparent',
        amber: 'border-transparent',
        green: 'border-transparent',
        slate: 'border-transparent',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

const STATUS_STYLE: Record<string, React.CSSProperties> = {
  blue: { color: 'var(--status-blue)', background: 'var(--status-blue-bg)' },
  violet: { color: 'var(--status-violet)', background: 'var(--status-violet-bg)' },
  red: { color: 'var(--status-red)', background: 'var(--status-red-bg)' },
  amber: { color: 'var(--status-amber)', background: 'var(--status-amber-bg)' },
  green: { color: 'var(--status-green)', background: 'var(--status-green-bg)' },
  slate: { color: 'var(--status-slate)', background: 'var(--status-slate-bg)' },
}

function Badge({
  className,
  variant,
  style,
  ...props
}: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  const statusStyle = variant && variant in STATUS_STYLE ? STATUS_STYLE[variant] : undefined
  return (
    <span
      className={cn(badgeVariants({ variant }), className)}
      style={{ ...statusStyle, ...style }}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
