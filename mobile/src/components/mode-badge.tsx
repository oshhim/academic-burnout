import { useActiveParticipant } from '@/lib/session';

import { Badge } from './ui';

/** Header chip showing whether this screen sends demo or real data. */
export function ModeBadge() {
  const active = useActiveParticipant();
  if (!active) return null;
  return <Badge label={active.real ? 'REAL' : 'DEMO'} tone={active.real ? 'success' : 'warn'} />;
}
