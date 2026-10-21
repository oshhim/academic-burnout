import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useRef, useState } from 'react';
import { api, ApiError, type Connection } from './api';

export const COMPONENTS = ['facial', 'voice', 'risk'] as const;
export type Component = (typeof COMPONENTS)[number];
export type Strategy = 'generic' | 'preference' | 'adaptive' | 'multimodal_weighted';
export type GuideStep = { title: string; instruction: string; duration_seconds: number };
export type Activity = { activity_id: string; title: string; category: string; summary?: string; duration_seconds: number; instructions: string[]; guide_steps?: GuideStep[]; note_prompt?: string | null };
export type ActivitySession = { session_id: string; status: string; activity: Activity; started_at: string; ended_at: string | null };
export type Integration = {
  fallback: boolean; context_share: number; normalized_weights: Record<Component, number>;
  modalities: Record<Component, { available: boolean; reason: string; origin: string; record_id: string | null; mapping_key?: string }>;
  synthetic_mapping_only: boolean; demo_context_id: string | null;
};
export const COMPONENT_NAMES: Record<Component, string> = { facial: 'C1 · Facial', voice: 'C2 · Voice', risk: 'C3 · Diary forecast' };
const REASONS: Record<string, string> = {
  not_completed: 'No completed result', insufficient_quality: 'Capture quality too low', stale_result: 'Result is too old',
  prediction_unavailable: 'No usable prediction', synthetic_mapping_only: 'Weighting is in demo evaluation',
  context_disabled: 'Check-in context switched off', poor_quality: 'Simulated quality failure', insufficient_history: 'Not enough simulated history',
  expired_demo_context: 'Scenario expired; load it again', temporal_result_unavailable: 'Return measurement unavailable',
  future_result: 'Result is not available yet', baseline_unavailable: 'Facial baseline unavailable',
};
export const contextReason = (reason: string) => REASONS[reason] ?? reason.replaceAll('_', ' ');

type Pending = { kind: string; path: string; body: Record<string, unknown> };
/** Persist the exact request before sending it; retries survive a lost response or reload. */
export function useActivityWrite(connection: Connection, participantId: string) {
  const storageKey = `empath.c4.pending.v1:${connection.baseUrl}:${participantId}`;
  const [pending, setPending] = useState<Pending | null>(null);
  const [ready, setReady] = useState(false);
  const current = useRef<Pending | null>(null);
  useEffect(() => {
    let alive = true;
    AsyncStorage.getItem(storageKey).then((raw) => {
      if (!alive) return;
      const saved = raw ? JSON.parse(raw) : null;
      if (saved?.body?.participant_id === participantId && typeof saved.path === 'string') {
        current.current = saved; setPending(saved);
      }
    }).catch(() => {}).finally(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, [storageKey, participantId]);
  const discard = async () => {
    await AsyncStorage.removeItem(storageKey); current.current = null; setPending(null);
  };
  const send = async (item: Pending, retry = false) => {
    if (!ready) throw new Error('Please wait for saved activity state to load.');
    if (!retry && current.current) throw new Error('Retry or clear the pending request first.');
    await AsyncStorage.setItem(storageKey, JSON.stringify(item)); current.current = item; setPending(item);
    try {
      const result = await api(connection, item.path, { body: item.body });
      await discard(); return { kind: item.kind, result };
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) await discard();
      throw e;
    }
  };
  return { pending, ready, discard, send, retry: () => {
    if (!current.current) throw new Error('There is no pending request.');
    return send(current.current, true);
  } };
}
