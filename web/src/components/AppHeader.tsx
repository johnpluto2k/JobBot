import { MapPin, Mail } from 'lucide-react'
import type { Profile } from '@/lib/api'

function initials(name?: string | null) {
  if (!name) return '?'
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((n) => n[0]?.toUpperCase() ?? '')
    .join('')
}

export function AppHeader({ profile }: { profile: Profile | null }) {
  const name = profile?.name ?? 'Job Bot'
  return (
    <header className="flex items-center gap-4">
      <div
        className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-full text-base font-semibold text-white ring-2 ring-white/70"
        style={{ background: 'linear-gradient(135deg, var(--primary), #7c3aed)' }}
      >
        {profile?.avatar ? (
          <img src={profile.avatar} alt={name} className="h-full w-full object-cover" />
        ) : (
          initials(name)
        )}
      </div>
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Job Bot <span className="font-normal text-muted-foreground">· Career OS</span>
        </h1>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          {profile?.name && <span className="font-medium text-foreground">{profile.name}</span>}
          {profile?.location && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={13} /> {profile.location}
            </span>
          )}
          {profile?.email && (
            <a href={`mailto:${profile.email}`} className="inline-flex items-center gap-1 hover:text-primary">
              <Mail size={13} /> {profile.email}
            </a>
          )}
        </div>
      </div>
    </header>
  )
}
