import AsyncStorage from '@react-native-async-storage/async-storage';
import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { AppState, Text, TextInput, View } from 'react-native';
import { Body, Button, Card, ErrorBox, Notice, Screen, Section, Title } from './ui';
import { ModeBadge } from './mode-badge';
import type { ActivitySession } from '@/lib/activities';
import { colors, fonts, space } from '@/theme';

const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
export function ActivityPlayer({ session, storageScope, onFinish, onExit, retryContent, busy, error }: {
  session: ActivitySession; storageScope: string; onFinish: (outcome: 'completed' | 'abandoned') => void; onExit: () => void; retryContent?: ReactNode; busy: boolean; error: unknown;
}) {
  const a = session.activity;
  const steps = a.guide_steps ?? a.instructions.map((instruction, i) => ({ title: `Step ${i + 1}`, instruction, duration_seconds: a.duration_seconds / a.instructions.length }));
  const key = `empath.c4.guide.v1:${storageScope}:${session.session_id}`;
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(false);
  const [ready, setReady] = useState(false);
  const [note, setNote] = useState('');
  const saved = useRef(0);
  const started = useRef<number | null>(null);
  const valueNow = useCallback(() => Math.min(a.duration_seconds, saved.current + (started.current === null ? 0 : (Date.now() - started.current) / 1000)), [a.duration_seconds]);
  const persist = useCallback((seconds: number) => AsyncStorage.setItem(key, JSON.stringify({ elapsed: seconds })).catch(() => {}), [key]);
  const pause = useCallback(() => {
    saved.current = valueNow(); started.current = null;
    setElapsed(saved.current); setRunning(false); void persist(saved.current);
  }, [persist, valueNow]);
  useEffect(() => {
    let alive = true;
    AsyncStorage.getItem(key).then((raw) => {
      if (!alive) return;
      const seconds = raw ? JSON.parse(raw).elapsed : 0;
      saved.current = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.min(a.duration_seconds, seconds)) : 0;
      setElapsed(saved.current);
    }).catch(() => {}).finally(() => { if (alive) setReady(true); });
    return () => { alive = false; };
  }, [key, a.duration_seconds]);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      const seconds = valueNow(); setElapsed(seconds); void persist(seconds);
      if (seconds >= a.duration_seconds) pause();
    }, 1000);
    return () => clearInterval(id);
  }, [running, valueNow, pause, a.duration_seconds, persist]);
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => { if (state !== 'active') pause(); });
    return () => sub.remove();
  }, [pause]);
  useFocusEffect(useCallback(() => () => { pause(); setNote(''); }, [pause]));
  let before = 0;
  let index = steps.length - 1;
  for (let i = 0; i < steps.length; i++) {
    if (elapsed < before + steps[i].duration_seconds) { index = i; break; }
    before += steps[i].duration_seconds;
  }
  const done = elapsed >= a.duration_seconds;
  const step = steps[index];
  const nextStep = () => {
    const next = Math.min(a.duration_seconds, steps.slice(0, index + 1).reduce((sum, s) => sum + s.duration_seconds, 0));
    saved.current = next; started.current = running ? Date.now() : null; setElapsed(next); void persist(next);
    if (next >= a.duration_seconds) pause();
  };
  return <Screen eyebrow="Activity in progress" title={a.title} badge={<ModeBadge />}>
    <Card tint="violet">
      <Body small muted>Step {index + 1} of {steps.length} · {done ? 'Suggested time reached' : running ? 'Guide running' : 'Guide paused'}</Body>
      <Title>{done ? 'Take a moment to choose what is next.' : step.title}</Title><Body>{step.instruction}</Body>
      <Text style={{ fontFamily: fonts.label, fontSize: 44, color: colors.primary, textAlign: 'center' }}>{clock(elapsed)} / {clock(a.duration_seconds)}</Text>
      <View accessibilityLabel={`Guide progress ${Math.round(elapsed / a.duration_seconds * 100)} percent`} style={{ height: 8, backgroundColor: colors.raised, borderRadius: 4 }}>
        <View style={{ height: 8, width: `${Math.min(100, elapsed / a.duration_seconds * 100)}%`, backgroundColor: colors.primary, borderRadius: 4 }} />
      </View>
      {!done ? <View style={{ gap: space.sm }}>
        <Button label={running ? 'Pause guide' : elapsed ? 'Resume guide' : 'Begin guide'} icon={running ? 'pause' : 'play-arrow'} disabled={!ready || busy} onPress={() => { if (running) pause(); else { started.current = Date.now(); setRunning(true); } }} />
        <Button label="Move to next step" variant="text" disabled={!ready || busy} onPress={nextStep} />
      </View> : null}
    </Card>
    {a.note_prompt ? <Card><Body>{a.note_prompt}</Body>
      <TextInput accessibilityLabel="Private activity note" value={note} onChangeText={setNote} multiline maxLength={1000} placeholder="Optional private note" placeholderTextColor={colors.textFaint} style={{ minHeight: 100, padding: space.sm, color: colors.text, fontFamily: fonts.regular, backgroundColor: colors.raised, borderRadius: 12 }} />
      <Body small muted>This note stays on this screen and clears when you leave it. It is not uploaded or saved.</Body>
    </Card> : null}
    <Section label="All steps"><Card>{steps.map((s, i) => <Body key={s.title} muted={i !== index}>{i + 1}. {s.title}: {s.instruction}</Body>)}</Card></Section>
    <ErrorBox error={error} />
    {retryContent}
    <Button label="I completed it" icon="check" disabled={busy} onPress={() => { pause(); onFinish('completed'); }} />
    <Button label="Stop without completing" variant="secondary" disabled={busy} onPress={() => { pause(); onFinish('abandoned'); }} />
    <Button label="Return to activities" variant="text" onPress={() => { pause(); setNote(''); onExit(); }} />
    <Notice>The guide pauses when you leave this tab or background the app. You may stop or complete at any time; timing does not verify participation.</Notice>
  </Screen>;
}
