import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';

import { ModeBadge } from '@/components/mode-badge';
import { NeedsSetup } from '@/components/needs-setup';
import { Badge, Body, Button, Card, Chips, Details, ErrorBox, IconWell, KeyValue, Notice, Rating, Screen, Section, Title, Toggle } from '@/components/ui';
import { api } from '@/lib/api';
import { CATEGORY_ICON, GOAL_ICON, capitalize } from '@/lib/explain';
import { useActiveParticipant, usePendingId, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { colors, fonts, space } from '@/theme';

const CATEGORIES = ['pause', 'movement', 'planning', 'reflection', 'audio'] as const;
const STRATEGIES = ['generic', 'preference', 'adaptive'] as const;
const GOALS = ['rest', 'refocus', 'organize', 'reflect'] as const;
const TIMES = [120, 300, 600] as const;

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

function Timer({ since, target }: { since: string; target: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.floor((now - Date.parse(since)) / 1000));
  return (
    <View style={{ alignItems: 'center', gap: 2 }}>
      <Text style={{ fontFamily: fonts.label, fontSize: 48, lineHeight: 56, color: seconds >= target ? colors.tertiary : colors.text }}>{clock(seconds)}</Text>
      <Body small muted>{seconds >= target ? 'Suggested time reached' : `Suggested ${clock(target)}`}</Body>
    </View>
  );
}

/** Short reasons from the ranking explanation, in plain words. */
function reasons(e: any) {
  const out: string[] = [];
  if (e.goal_match >= 1) out.push('Fits your goal');
  if (e.preference_used && e.category_preference >= 0.75) out.push('A type you rated highly');
  if (e.feedback_count > 0) out.push(`Uses your ${e.feedback_count} rating${e.feedback_count > 1 ? 's' : ''}`);
  if (e.recent_repeat_penalty > 0) out.push('Done recently');
  return out.length ? out : ['Fits your time'];
}

function ActivitiesScreenContent() {
  const { connection } = useSession();
  const active = useActiveParticipant();
  const { busy, error, run } = useAction();
  const prefId = usePendingId('pref');
  const offerId = usePendingId('offer');
  const startId = usePendingId('start');
  const eventId = usePendingId('event');
  const feedbackId = usePendingId('fb');

  const [ratings, setRatings] = useState<Record<string, number>>({ pause: 3, movement: 3, planning: 3, reflection: 3, audio: 3 });
  const [allowMovement, setAllowMovement] = useState(true);
  const [allowAudio, setAllowAudio] = useState(true);
  const [prefsSaved, setPrefsSaved] = useState(false);
  const [strategy, setStrategy] = useState<(typeof STRATEGIES)[number]>('adaptive');
  const [goal, setGoal] = useState<(typeof GOALS)[number]>('refocus');
  const [seconds, setSeconds] = useState<number>(300);
  const [offer, setOffer] = useState<any>(null);
  const [session, setSession] = useState<any>(null);
  const [outcome, setOutcome] = useState<'completed' | 'abandoned' | null>(null);
  const [helpfulness, setHelpfulness] = useState<number | null>(null);
  const [wouldRepeat, setWouldRepeat] = useState<boolean | null>(null);
  const [feedbackSaved, setFeedbackSaved] = useState(false);

  if (!active) return <Screen title="Activities"><NeedsSetup /></Screen>;
  const common = { participant_id: active.id, data_source: active.source, consent: true };
  const prefChanged = () => setPrefsSaved(false);

  const savePrefs = () =>
    run('prefs', async () => {
      await api(connection, '/interventions/preferences', {
        body: { ...common, client_update_id: prefId.get(), category_ratings: ratings, excluded_activity_ids: [], allow_movement: allowMovement, allow_audio: allowAudio, max_duration_seconds: 600 },
      });
      prefId.done();
      setPrefsSaved(true);
    });

  const requestOffer = () =>
    run('offer', async () => {
      const response = await api(connection, '/interventions/recommendations', {
        body: { ...common, client_request_id: offerId.get(), strategy, goal, available_seconds: seconds, limit: 3 },
      });
      offerId.done();
      setOffer(response);
      setSession(null);
      setOutcome(null);
      setHelpfulness(null);
      setWouldRepeat(null);
      setFeedbackSaved(false);
    });

  const start = (activityId: string) =>
    run(`start-${activityId}`, async () => {
      setSession(await api(connection, '/interventions/sessions', { body: { ...common, client_session_id: startId.get(), recommendation_id: offer.recommendation_id, activity_id: activityId } }));
      startId.done();
    });

  const finish = (result: 'completed' | 'abandoned') =>
    run(result, async () => {
      await api(connection, '/interventions/events', { body: { ...common, client_event_id: eventId.get(), session_id: session.session_id, outcome: result } });
      eventId.done();
      setOutcome(result);
    });

  const sendFeedback = () =>
    run('feedback', async () => {
      await api(connection, '/interventions/feedback', { body: { ...common, client_feedback_id: feedbackId.get(), session_id: session.session_id, helpfulness, would_repeat: wouldRepeat } });
      feedbackId.done();
      setFeedbackSaved(true);
    });

  // While an activity runs, show only the activity.
  if (session && !outcome) {
    const a = session.activity;
    return (
      <Screen title="Activity" badge={<ModeBadge />}>
        <Card tint="violet">
          <View style={{ alignItems: 'center', gap: space.sm }}>
            <IconWell icon={CATEGORY_ICON[a.category as keyof typeof CATEGORY_ICON] ?? 'spa'} color={colors.secondary} size={64} />
            <Title center>{a.title}</Title>
            <Timer since={session.started_at} target={a.duration_seconds} />
          </View>
        </Card>
        <Section label="Steps">
          <Card>
            {a.instructions.map((step: string, i: number) => (
              <View key={step} style={{ flexDirection: 'row', gap: space.sm }}>
                <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center' }}>
                  <Text style={{ fontFamily: fonts.label, color: colors.primary }}>{i + 1}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Body>{step}</Body>
                </View>
              </View>
            ))}
          </Card>
        </Section>
        <ErrorBox error={error} />
        <Button label="I completed it" icon="check" onPress={() => finish('completed')} loading={busy === 'completed'} />
        <Button label="Stop without completing" variant="secondary" onPress={() => finish('abandoned')} loading={busy === 'abandoned'} />
        <Notice icon="info-outline">Completion is your own report; the timer is a guide, not a check.</Notice>
      </Screen>
    );
  }

  return (
    <Screen title="Activities" badge={<ModeBadge />} subtitle="Short, optional activities that fit your time and preferences.">
      {outcome === 'completed' && !feedbackSaved ? (
        <Section label="How was it?">
          <Card>
            <Rating label="Helpfulness" value={helpfulness} onChange={setHelpfulness} required low="Not helpful" high="Very helpful" />
            <Body small muted>Would you do it again?</Body>
            <Chips options={['yes', 'no'] as const} value={wouldRepeat === null ? null : wouldRepeat ? 'yes' : 'no'} onChange={(v) => setWouldRepeat(v === 'yes')} format={capitalize} icons={{ yes: 'thumb-up-off-alt', no: 'thumb-down-off-alt' }} />
            <Button label="Send feedback" onPress={sendFeedback} loading={busy === 'feedback'} disabled={helpfulness === null || wouldRepeat === null} />
            <Button label="Skip" variant="text" onPress={() => setFeedbackSaved(true)} />
          </Card>
        </Section>
      ) : null}

      {outcome ? (
        <Notice icon={outcome === 'completed' ? 'check-circle' : 'pause-circle-outline'} tone="cyan">
          {outcome === 'completed' ? (feedbackSaved ? 'Nice work. New options will reflect your feedback.' : 'Activity completed.') : 'Activity stopped. That is fine; nothing is counted against you.'}
        </Notice>
      ) : null}

      <Section label="What do you need?">
        <Card>
          <Chips options={GOALS} value={goal} onChange={setGoal} format={capitalize} icons={GOAL_ICON} />
          <Body small muted>Time available</Body>
          <Chips options={TIMES} value={seconds} onChange={setSeconds} format={(s) => `${s / 60} min`} icons={{ 120: 'timer', 300: 'timer', 600: 'timer' }} />
          <Button label={offer ? 'Get new options' : 'Show options'} icon="auto-awesome" onPress={requestOffer} loading={busy === 'offer'} />
        </Card>
      </Section>

      <ErrorBox error={error} />

      {/* An offer starts one activity; after that, ask for new options. */}
      {offer && !session ? (
        <Section label="Recommended for you">
          {offer.status === 'no_eligible_activity' || offer.options.length === 0 ? (
            <Card>
              <View style={{ alignItems: 'center', gap: space.sm }}>
                <IconWell icon="search-off" size={56} />
                <Title center>Nothing fits right now</Title>
                <Body muted center>Try more time or allow more activity types in your preferences. Your limits are never relaxed silently.</Body>
              </View>
            </Card>
          ) : (
            offer.options.map((option: any, index: number) => {
              const a = option.activity;
              return (
                <Card key={a.activity_id} tint={index === 0 ? 'violet' : undefined}>
                  {index === 0 ? <Badge label="TOP PICK" tone="warn" /> : null}
                  <Title>{a.title}</Title>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.base }}>
                    <View style={chipStyle}>
                      <MaterialIcons name="schedule" size={16} color={colors.textMuted} />
                      <Text style={chipText}>{Math.round(a.duration_seconds / 60)} min</Text>
                    </View>
                    <View style={chipStyle}>
                      <MaterialIcons name={CATEGORY_ICON[a.category as keyof typeof CATEGORY_ICON] ?? 'spa'} size={16} color={colors.tertiary} />
                      <Text style={[chipText, { color: colors.tertiary }]}>{capitalize(a.category)}</Text>
                    </View>
                  </View>
                  <Body small muted>{reasons(option.explanation).join(' · ')}</Body>
                  <Button label="Start activity" icon="play-arrow" variant={index === 0 ? 'primary' : 'secondary'} onPress={() => start(a.activity_id)} loading={busy === `start-${a.activity_id}`} />
                  <Details label="Why this ranking">
                    <KeyValue
                      rows={[
                        ['Score', option.score.toFixed(3)],
                        ['Goal match', String(option.explanation.goal_match)],
                        ['Time fit', String(option.explanation.duration_fit)],
                        ['Preference', String(option.explanation.category_preference)],
                        ['Feedback estimate', `${option.explanation.feedback_posterior.toFixed(3)} from ${option.explanation.feedback_count} rating(s)`],
                      ]}
                    />
                  </Details>
                </Card>
              );
            })
          )}
        </Section>
      ) : null}

      <Section label="Your preferences">
        <Details label={prefsSaved ? 'Preferences saved · edit' : 'Set preferences (optional)'}>
          <Card>
            {CATEGORIES.map((c) => (
              <Rating key={c} label={capitalize(c)} value={ratings[c]} onChange={(v) => { setRatings({ ...ratings, [c]: v ?? 3 }); prefChanged(); }} required low="Dislike" high="Love" />
            ))}
            <Toggle icon="directions-walk" label="Movement activities" value={allowMovement} onChange={(v) => { setAllowMovement(v); prefChanged(); }} />
            <Toggle icon="headphones" label="Audio activities" value={allowAudio} onChange={(v) => { setAllowAudio(v); prefChanged(); }} />
            <Button label={prefsSaved ? 'Saved' : 'Save preferences'} icon={prefsSaved ? 'check' : undefined} variant="secondary" onPress={savePrefs} loading={busy === 'prefs'} disabled={prefsSaved} />
          </Card>
          <Body small muted>Ranking strategy (for testing)</Body>
          <Chips options={STRATEGIES} value={strategy} onChange={setStrategy} format={capitalize} />
        </Details>
      </Section>

      <Notice icon="info-outline">Optional activities, not treatment. Ratings help ranking and are never required.</Notice>
    </Screen>
  );
}

const chipStyle = { flexDirection: 'row' as const, alignItems: 'center' as const, gap: 6, backgroundColor: colors.raised, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6 };
const chipText = { fontFamily: fonts.label, fontSize: 13, color: colors.textMuted };

/** Remount when the participant changes so no state leaks between demo and real data. */
export default function ActivitiesScreen() {
  const active = useActiveParticipant();
  return <ActivitiesScreenContent key={active?.id ?? 'none'} />;
}
