import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';
import { View } from 'react-native';
import { ActivityPlayer } from '@/components/activity-player';
import { ModeBadge } from '@/components/mode-badge';
import { NeedsSetup } from '@/components/needs-setup';
import { Badge, Body, Button, Card, Chips, Details, ErrorBox, KeyValue, Notice, Rating, Screen, Section, Title, Toggle } from '@/components/ui';
import { api, uid } from '@/lib/api';
import { COMPONENTS, COMPONENT_NAMES, contextReason, useActivityWrite, type Activity, type ActivitySession, type Component, type Integration, type Strategy } from '@/lib/activities';
import { GOAL_ICON, capitalize } from '@/lib/explain';
import { useActiveParticipant, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';

const CATEGORIES = ['pause', 'movement', 'planning', 'reflection', 'audio'] as const;
const STRATEGIES = ['multimodal_weighted', 'adaptive', 'preference', 'generic'] as const;
const GOALS = ['rest', 'refocus', 'organize', 'reflect'] as const;
const MASKS = ['none', 'facial', 'voice', 'risk', 'facial+voice', 'facial+risk', 'voice+risk', 'all'] as const;
const labelMask = (s: string) => s === 'none' ? 'None' : s === 'all' ? 'All three' : s.split('+').map((c) => ({ facial: 'C1', voice: 'C2', risk: 'C3' })[c as Component]).join(' + ');

function ContextCard({ value }: { value: Integration | null }) {
  if (!value) return <Body small muted>Context will be checked when you ask for options.</Body>;
  return <Card>
    <Title>{value.fallback ? 'Activities work on their own' : 'Available check-ins add context'}</Title>
    <Body small muted>{value.fallback ? 'Your goal, saved preferences and earlier activity ratings are enough. No other assessment is required.' : 'Your goal, preferences and feedback remain the main part of the ranking. Only usable results add a smaller context contribution.'}</Body>
    {COMPONENTS.map((k) => <View key={k} style={{ gap: 2 }}><Body small>{COMPONENT_NAMES[k]} · {value.modalities[k].available ? (value.modalities[k].origin === 'synthetic_fixture' ? 'Simulated result' : 'Completed demo result') : contextReason(value.modalities[k].reason)}</Body></View>)}
    {!value.fallback ? <Details label="Context weights"><KeyValue rows={COMPONENTS.map((k): [string, string] => [COMPONENT_NAMES[k], `${(value.normalized_weights[k] * 100).toFixed(1)}% of context`])} /><Body small muted>Context contributes {(value.context_share * 100).toFixed(0)}% of the ranking. These are experimental policy weights.</Body></Details> : null}
  </Card>;
}

function ActivitiesScreenContent() {
  const { connection } = useSession();
  const active = useActiveParticipant()!;
  const { busy, error, run } = useAction();
  const write = useActivityWrite(connection, active.id);
  const lock = useRef(false);
  const dirty = useRef(false);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [ratings, setRatings] = useState<Record<string, number>>({ pause: 3, movement: 3, planning: 3, reflection: 3, audio: 3 });
  const [allowMovement, setAllowMovement] = useState(true);
  const [allowAudio, setAllowAudio] = useState(true);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [maxDuration, setMaxDuration] = useState(600);
  const [prefsSaved, setPrefsSaved] = useState(false);
  const [catalog, setCatalog] = useState<Activity[]>([]);
  const [strategy, setStrategy] = useState<Strategy>('multimodal_weighted');
  const [useContext, setUseContext] = useState(true);
  const [context, setContext] = useState<Integration | null>(null);
  const [demoId, setDemoId] = useState<string | null>(null);
  const [mask, setMask] = useState<(typeof MASKS)[number]>('all');
  const [faceScenario, setFaceScenario] = useState<'persistent' | 'returned' | 'poor_quality'>('persistent');
  const [voiceScenario, setVoiceScenario] = useState<'sad' | 'neutral' | 'poor_quality'>('sad');
  const [riskScenario, setRiskScenario] = useState<'higher' | 'lower' | 'insufficient_history'>('higher');
  const [goal, setGoal] = useState<(typeof GOALS)[number]>('refocus');
  const [seconds, setSeconds] = useState<number>(300);
  const [offer, setOffer] = useState<any>(null);
  const [session, setSession] = useState<ActivitySession | null>(null);
  const [outcome, setOutcome] = useState<'completed' | 'abandoned' | null>(null);
  const [helpfulness, setHelpfulness] = useState<number | null>(null);
  const [wouldRepeat, setWouldRepeat] = useState<boolean | null>(null);
  const [feedbackStatus, setFeedbackStatus] = useState<'waiting' | 'saved' | 'skipped'>('waiting');
  const [unrated, setUnrated] = useState<ActivitySession[]>([]);
  const [unfinished, setUnfinished] = useState<ActivitySession[]>([]);
  const [recent, setRecent] = useState<ActivitySession[]>([]);
  const common = { participant_id: active.id, data_source: active.source, consent: true };
  const disabled = Boolean(busy) || !write.ready || Boolean(write.pending);
  const previewContext: Integration | null = context && (!useContext || strategy !== 'multimodal_weighted') ? {
    ...context, fallback: true, context_share: 0,
    normalized_weights: { facial: 0, voice: 0, risk: 0 },
    modalities: Object.fromEntries(COMPONENTS.map((k) => [k, { ...context.modalities[k], available: false, reason: 'context_disabled' }])) as Integration['modalities'],
  } : context;
  const applyPrefs = (data: any) => {
    setRatings(data.preferences.category_ratings); setAllowAudio(data.preferences.allow_audio); setAllowMovement(data.preferences.allow_movement);
    setExcluded(data.preferences.excluded_activity_ids); setMaxDuration(data.preferences.max_duration_seconds); setPrefsSaved(data.version > 0);
  };
  const load = useCallback(async () => {
    const [state, cat, ctx] = await Promise.all([
      api(connection, `/interventions/state/${active.id}`), api(connection, '/interventions/catalog'),
      api<Integration>(connection, `/interventions/context/${active.id}${demoId ? `?demo_context_id=${demoId}` : ''}`),
    ]);
    return { state, cat, ctx };
  }, [connection, active.id, demoId]);
  useFocusEffect(useCallback(() => {
    let alive = true;
    load().then(({ state, cat, ctx }) => {
      if (!alive) return;
      if (!dirty.current) applyPrefs(state.preferences);
      setCatalog(cat.activities); setContext(ctx); setUnrated(state.unrated); setUnfinished(state.unfinished); setRecent(state.recent); setLoadError(null);
    }).catch((e) => { if (alive) setLoadError(e); });
    return () => { alive = false; };
  }, [load]));
  const refresh = async () => {
    const { state, cat, ctx } = await load();
    if (!dirty.current) applyPrefs(state.preferences);
    setCatalog(cat.activities); setContext(ctx); setUnrated(state.unrated); setUnfinished(state.unfinished); setRecent(state.recent); setLoadError(null);
  };
  const task = (name: string, action: () => Promise<void>) => {
    if (lock.current) return;
    lock.current = true;
    void run(name, async () => { try { await action(); } finally { lock.current = false; } });
  };
  const resetFeedback = () => { setHelpfulness(null); setWouldRepeat(null); setFeedbackStatus('waiting'); };
  const accept = async ({ kind, result }: { kind: string; result: any }) => {
    if (kind === 'prefs') { dirty.current = false; applyPrefs(result); setOffer(null); }
    if (kind === 'offer') { setOffer(result); setContext(result.integration); setSession(null); setOutcome(null); resetFeedback(); }
    if (kind === 'start') { setSession(result); setOutcome(null); resetFeedback(); }
    if (kind === 'event') { setSession(result.session); setOutcome(result.session.status); resetFeedback(); await refresh(); }
    if (kind === 'feedback') { setFeedbackStatus('saved'); await refresh(); }
    if (kind === 'fixture') {
      setDemoId(result.demo_context_id); setOffer(null);
      setContext(await api<Integration>(connection, `/interventions/context/${active.id}?demo_context_id=${result.demo_context_id}`));
    }
  };
  const submit = (kind: string, path: string, body: Record<string, unknown>) => task(kind, async () => accept(await write.send({ kind, path, body })));
  const prefChanged = () => { dirty.current = true; setPrefsSaved(false); };
  const requestOffer = () => submit('offer', '/interventions/recommendations', { ...common, client_request_id: uid('offer'), strategy, goal, available_seconds: seconds, limit: 4,
    context_mode: useContext ? 'latest_eligible' : 'none', ...(useContext && strategy === 'multimodal_weighted' && demoId ? { demo_context_id: demoId } : {}) });
  const finish = (result: 'completed' | 'abandoned') => submit('event', '/interventions/events', { ...common, client_event_id: uid('end'), session_id: session!.session_id, outcome: result });
  const pendingCard = write.pending ? <Card><Title>A request needs a retry</Title><Body small muted>The original request is saved. Retry it unchanged to recover the response. Clearing it does not undo a write that reached the server.</Body>
    <Button label="Retry saved request" disabled={Boolean(busy)} onPress={() => task('retry', async () => accept(await write.retry()))} />
    <Button label="Clear pending request and refresh" variant="text" disabled={Boolean(busy)} onPress={() => task('clear', async () => { await write.discard(); await refresh(); })} /></Card> : null;

  if (session && !outcome) return <ActivityPlayer key={session.session_id} session={session} storageScope={`${connection.baseUrl}:${active.id}`} busy={disabled} error={error} onFinish={finish} retryContent={pendingCard} onExit={() => { setSession(null); setOutcome(null); task('refresh', refresh); }} />;

  return <Screen eyebrow="Component 4 · Activities" title="A small reset," dim="chosen for you." badge={<ModeBadge />}>
    {pendingCard}<ErrorBox error={error ?? loadError} />
    {outcome === 'completed' && feedbackStatus === 'waiting' ? <Section label="How was it?"><Card>
      <Rating label="Helpfulness" value={helpfulness} onChange={setHelpfulness} required low="Not helpful" high="Very helpful" />
      <Body small muted>Would you choose this again?</Body>
      <Chips options={['yes', 'no'] as const} value={wouldRepeat === null ? null : wouldRepeat ? 'yes' : 'no'} onChange={(v) => setWouldRepeat(v === 'yes')} format={capitalize} />
      <Button label="Send feedback" disabled={disabled || helpfulness === null || wouldRepeat === null} onPress={() => submit('feedback', '/interventions/feedback', { ...common, client_feedback_id: uid('fb'), session_id: session!.session_id, helpfulness, would_repeat: wouldRepeat })} />
      <Button label="Skip for now" variant="text" disabled={Boolean(busy)} onPress={() => setFeedbackStatus('skipped')} />
    </Card></Section> : null}
    {outcome ? <Notice tone="cyan">{outcome === 'abandoned' ? 'Activity stopped. No negative helpfulness rating is inferred.' : feedbackStatus === 'saved' ? 'Feedback saved. Future options can use this rating.' : feedbackStatus === 'skipped' ? 'Activity completed. No rating was submitted.' : 'Activity completed. Feedback is optional.'}</Notice> : null}

    {unfinished.length > 0 && !session ? <Section label="Continue an activity">{unfinished.map((s) => <Card key={s.session_id}><Title>{s.activity.title}</Title><Button label="Resume activity" disabled={disabled} onPress={() => { setSession(s); setOutcome(null); resetFeedback(); }} /></Card>)}</Section> : null}

    <Section label="What do you need?"><Card>
      <Chips options={GOALS} value={goal} onChange={setGoal} format={capitalize} icons={GOAL_ICON} />
      <Body small muted>Time available</Body><Chips options={[60, 120, 300, 600] as const} value={seconds} onChange={setSeconds} format={(s) => `${s / 60} min`} />
      <Toggle label="Use available check-ins" description="Optional. Activities work even if you skip every assessment." icon="tune" value={useContext} onChange={(v) => { setUseContext(v); setOffer(null); }} />
      <Button label={offer ? 'Get new options' : 'Show options'} icon="auto-awesome" disabled={disabled || unfinished.length > 0} onPress={requestOffer} loading={busy === 'offer'} />
      {unfinished.length > 0 ? <Body small muted>Resume and finish or stop your current activity before requesting more options.</Body> : null}
    </Card></Section>
    <ContextCard value={offer?.integration ?? previewContext} />
    {active.real ? <Notice>Weighted mappings are currently evaluated with synthetic data. Your real activities continue using goals, preferences and feedback.</Notice> : null}

    {offer && !session ? <Section label="Recommended for you">
      {!offer.options.length ? <Card><Title>Nothing fits right now</Title><Body>Try more time or review your activity exclusions. Your limits are always respected.</Body></Card> : offer.options.map((option: any, i: number) => {
        const a: Activity = option.activity;
        const e = option.explanation;
        const used = Object.keys(e.component_contributions ?? {}) as Component[];
        return <Card key={a.activity_id} tint={i === 0 ? 'violet' : undefined}>
          {i === 0 ? <Badge label="TOP PICK" /> : null}<Title>{a.title}</Title>
          <Body small muted>{a.duration_seconds < 120 ? `${a.duration_seconds} sec` : `${a.duration_seconds / 60} min`} · {capitalize(a.category)} · {a.guide_steps?.length ?? 3} guided steps</Body>
          <Body>{a.summary ?? a.instructions[0]}</Body>
          <Body small muted>{[e.goal_match ? 'Fits your goal' : 'Fits your time', e.preference_used && e.category_preference >= .75 ? 'A type you like' : null, e.feedback_used && e.feedback_count ? `Uses ${e.feedback_count} earlier rating(s)` : null, used.length ? `Context: ${used.map((k) => COMPONENT_NAMES[k].split(' · ')[0]).join(', ')}` : null].filter(Boolean).join(' · ')}</Body>
          <Button label="Start guided activity" icon="play-arrow" disabled={disabled} onPress={() => submit('start', '/interventions/sessions', { ...common, client_session_id: uid('start'), recommendation_id: offer.recommendation_id, activity_id: a.activity_id })} />
          <Details label="Why this ranking"><KeyValue rows={[
            ['Ranking score', option.score.toFixed(3)], ['Own activity score', e.independent_score_before_penalty.toFixed(3)],
            ['Context share', `${Math.round(e.context_share * 100)}%`], ['Context compatibility', e.context_score === null ? 'Not used' : e.context_score.toFixed(3)],
            ['Repeat adjustment', String(e.recent_repeat_penalty)], ...used.map((k): [string, string] => [COMPONENT_NAMES[k], `+${e.component_contributions[k].final_score_contribution.toFixed(3)} context contribution`]),
          ]} /><Body small muted>This is a policy ranking score, not a probability of health improvement.</Body></Details>
        </Card>;
      })}
    </Section> : null}

    <Section label="Your preferences"><Details label={prefsSaved ? 'Saved preferences · edit' : 'Set preferences (optional)'}><Card>
      {CATEGORIES.map((c) => <Rating key={c} label={capitalize(c)} value={ratings[c]} required onChange={(v) => { setRatings({ ...ratings, [c]: v ?? 3 }); prefChanged(); }} low="Dislike" high="Like" />)}
      <Toggle label="Movement activities" value={allowMovement} onChange={(v) => { setAllowMovement(v); prefChanged(); }} />
      <Toggle label="Audio activities" value={allowAudio} onChange={(v) => { setAllowAudio(v); prefChanged(); }} />
      <Body small muted>Maximum activity duration</Body><Chips options={[60, 120, 300, 600] as const} value={maxDuration} onChange={(v) => { setMaxDuration(v); prefChanged(); }} format={(s) => `${s / 60} min`} />
      <Details label="Exclude specific activities">{catalog.map((a) => <Toggle key={a.activity_id} label={a.title} description={excluded.includes(a.activity_id) ? 'Excluded' : 'Allowed'} value={!excluded.includes(a.activity_id)} onChange={(allow) => { setExcluded(allow ? excluded.filter((id) => id !== a.activity_id) : [...excluded, a.activity_id]); prefChanged(); }} />)}</Details>
      <Button label="Save preferences" disabled={disabled || prefsSaved} onPress={() => submit('prefs', '/interventions/preferences', { ...common, client_update_id: uid('pref'), category_ratings: ratings, excluded_activity_ids: excluded, allow_movement: allowMovement, allow_audio: allowAudio, max_duration_seconds: maxDuration })} />
      <Body small muted>Save changes before requesting options.</Body>
    </Card></Details></Section>

    {!active.real ? <Section label="Synthetic comparison"><Details label="Try optional component scenarios"><Card>
      <Body>Simulate completed component results without running the other assessments. These fixtures exist only in C4 and never change C1–C3 data.</Body>
      <Chips options={MASKS} value={mask} onChange={setMask} format={labelMask} />
      <Body small muted>C1 visual pattern</Body><Chips options={['persistent', 'returned', 'poor_quality'] as const} value={faceScenario} onChange={setFaceScenario} format={capitalize} />
      <Body small muted>C2 acted-style fixture</Body><Chips options={['sad', 'neutral', 'poor_quality'] as const} value={voiceScenario} onChange={setVoiceScenario} format={capitalize} />
      <Body small muted>C3 proxy fixture</Body><Chips options={['higher', 'lower', 'insufficient_history'] as const} value={riskScenario} onChange={setRiskScenario} format={capitalize} />
      <Button label="Load synthetic scenario" disabled={disabled} onPress={() => {
        setStrategy('multimodal_weighted'); setUseContext(true);
        submit('fixture', '/interventions/demo-contexts', { ...common, client_update_id: uid('fixture'), components: mask === 'all' ? [...COMPONENTS] : mask === 'none' ? [] : mask.split('+'), facial_scenario: faceScenario, voice_scenario: voiceScenario, risk_scenario: riskScenario });
      }} />
      {demoId ? <Button label="Use actual completed demo check-ins instead" variant="secondary" disabled={disabled} onPress={() => { setDemoId(null); setOffer(null); }} /> : null}
      <Notice>Fixtures expire after 30 minutes. These mappings test the algorithm; they do not establish which activities help real users.</Notice>
    </Card></Details></Section> : null}

    <Details label="Compare ranking strategies"><Chips options={STRATEGIES} value={strategy} onChange={(v) => { setStrategy(v); setOffer(null); }} format={(s) => s === 'multimodal_weighted' ? 'Optional context' : capitalize(s)} /><Body small muted>Generic uses goal/time. Preference adds your likes. Adaptive adds earlier ratings. Optional context also weights usable component results.</Body></Details>
    {unrated.filter((s) => s.session_id !== session?.session_id).length > 0 ? <Details label="Rate an earlier completed activity">{unrated.filter((s) => s.session_id !== session?.session_id).map((s) => <Card key={s.session_id}><Body>{s.activity.title}</Body><Button label="Give optional feedback" disabled={disabled} onPress={() => { setSession(s); setOutcome('completed'); resetFeedback(); }} /></Card>)}</Details> : null}
    <Details label="Recent activities">{recent.length ? recent.map((s) => <Body small key={s.session_id}>{s.activity.title} · {capitalize(s.status)}</Body>) : <Body small muted>No activity history yet.</Body>}</Details>
    <Button label="Refresh saved state" variant="text" disabled={Boolean(busy)} onPress={() => task('refresh', refresh)} />
    <Notice>Optional everyday activities. You choose what to do and may stop at any time.</Notice>
  </Screen>;
}
export default function ActivitiesScreen() {
  const active = useActiveParticipant();
  const { connection } = useSession();
  if (!active) return <Screen title="Activities"><NeedsSetup /></Screen>;
  return <ActivitiesScreenContent key={`${connection.baseUrl}:${active.id}`} />;
}
