import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { api, getPublic, uid, type Connection } from './api';

// Separate participants per data source: the guide forbids mixing public RAVDESS
// audio, synthetic fixtures and genuine local recordings under one ID.
export type Participants = { synthetic: string; publicAudio: string; local?: string };

/** demo = synthetic numbers + public samples; real = camera, microphone and your own entries. */
export type Mode = 'demo' | 'real';
export type Source = 'synthetic_demo' | 'local_research';

type SessionState = {
  loaded: boolean;
  connection: Connection;
  participants: Participants | null;
  mode: Mode;
  setConnection: (c: Connection) => void;
  register: (connection: Connection) => Promise<{ health: any; participants: Participants }>;
  enableReal: () => Promise<void>;
  setMode: (m: Mode) => void;
  resetParticipants: () => void;
  /** Launch screen seen; and a display name kept only on this phone (never sent to the backend). */
  onboarded: boolean;
  setOnboarded: (v: boolean) => void;
  displayName: string;
  setDisplayName: (v: string) => void;
  forgetLocal: () => void;
  resetApp: () => void;
};

const STORAGE_KEY = 'empath.session.v1';
const DEFAULT_KEY = 'local-demo-key-change-me';

/** Phones cannot reach 127.0.0.1 on the laptop; reuse the Expo dev server's LAN host. */
function defaultBaseUrl() {
  const host = Constants.expoConfig?.hostUri?.split(':')[0];
  return host ? `http://${host}:8000` : 'http://127.0.0.1:8000';
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [loaded, setLoaded] = useState(false);
  const [connection, setConnectionState] = useState<Connection>({ baseUrl: defaultBaseUrl(), apiKey: DEFAULT_KEY });
  const [participants, setParticipants] = useState<Participants | null>(null);
  const [mode, setMode] = useState<Mode>('demo');
  const [onboarded, setOnboarded] = useState(false);
  const [displayName, setDisplayName] = useState('');

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((raw) => {
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (saved.connection) setConnectionState(saved.connection);
        if (saved.participants) setParticipants(saved.participants);
        if (saved.mode === 'real' && saved.participants?.local) setMode('real');
        if (saved.onboarded) setOnboarded(true);
        if (typeof saved.displayName === 'string') setDisplayName(saved.displayName);
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    if (loaded) AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({ connection, participants, mode, onboarded, displayName })).catch(() => {});
  }, [loaded, connection, participants, mode, onboarded, displayName]);

  const register = useCallback(async (next: Connection) => {
    setConnectionState(next);
    const health = await getPublic(next, '/health');
    const ids = participants ?? { synthetic: uid('APP'), publicAudio: uid('RAV-APP') };
    await api(next, '/participants', { body: { participant_id: ids.synthetic, data_source: 'synthetic_demo', consent: true, consent_version: 'demo-v1' } });
    await api(next, '/participants', { body: { participant_id: ids.publicAudio, data_source: 'public_dataset', consent: true, consent_version: 'RAVDESS-CC-BY-NC-SA-4.0' } });
    setParticipants(ids);
    return { health, participants: ids };
  }, [participants]);

  /** Registers the local_research participant. The backend refuses it unless ENABLE_RESEARCH_MODE=true. */
  const enableReal = useCallback(async () => {
    if (!participants) throw new Error('Connect and register first.');
    const local = participants.local ?? uid('LOCAL');
    await api(connection, '/participants', { body: { participant_id: local, data_source: 'local_research', consent: true, consent_version: 'local-dev-v1' } });
    setParticipants({ ...participants, local });
    setMode('real');
  }, [connection, participants]);

  const value = useMemo<SessionState>(
    () => ({
      loaded,
      connection,
      participants,
      mode,
      setConnection: setConnectionState,
      register,
      enableReal,
      setMode,
      resetParticipants: () => {
        setParticipants(null);
        setMode('demo');
      },
      onboarded,
      setOnboarded,
      displayName,
      setDisplayName,
      // After deleting real data on the backend: drop the local participant, back to demo.
      forgetLocal: () => {
        setParticipants((p) => (p ? { synthetic: p.synthetic, publicAudio: p.publicAudio } : p));
        setMode('demo');
      },
      // "Sign out" equivalent without authentication: forget everything on this phone.
      resetApp: () => {
        setParticipants(null);
        setMode('demo');
        setDisplayName('');
        setOnboarded(false);
      },
    }),
    [loaded, connection, participants, mode, register, enableReal, onboarded, displayName],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside SessionProvider');
  return value;
}

/** The participant and data source C1, C3 and C4 should use in the current mode. */
export function useActiveParticipant(): { id: string; source: Source; real: boolean } | null {
  const { participants, mode } = useSession();
  if (!participants) return null;
  if (mode === 'real' && participants.local) return { id: participants.local, source: 'local_research', real: true };
  return { id: participants.synthetic, source: 'synthetic_demo', real: false };
}

/**
 * Client operation ID that survives retries: the same logical write keeps its ID
 * until it succeeds (guide: "the same logical retry does not [get a new ID]").
 */
export function usePendingId(prefix: string) {
  const ref = useRef<string | null>(null);
  return useMemo(
    () => ({
      get: () => (ref.current ??= uid(prefix)),
      done: () => {
        ref.current = null;
      },
    }),
    [prefix],
  );
}
