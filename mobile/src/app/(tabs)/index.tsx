import { Redirect } from 'expo-router';

import { useSession } from '@/lib/session';

/** Entry route: launch screen first, then Profile until connected, then Facial. Hidden from the tab bar. */
export default function Index() {
  const { onboarded, participants } = useSession();
  return <Redirect href={!onboarded ? '/welcome' : participants ? '/facial' : '/profile'} />;
}
