import { Search } from 'lucide-react'
import { Input } from '@/components/ui/input'

/**
 * Search box + result count for the long tables.
 *
 * The tracker holds 200+ companies and the pipeline renders up to 100 postings,
 * neither with any way to search, sort or filter - finding one company meant
 * scrolling. Press `/` anywhere outside a field to jump into the box.
 */
export function TableToolbar({
  value, onChange, placeholder, shown, total, children,
}: {
  value: string
  onChange: (v: string) => void
  placeholder: string
  shown: number
  total: number
  children?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-[14rem] flex-1">
        <Search
          size={15}
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          data-table-search
          className="pl-9"
        />
      </div>
      {children}
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {shown === total ? `${total}` : `${shown} of ${total}`}
      </span>
    </div>
  )
}
