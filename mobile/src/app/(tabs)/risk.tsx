import { useRef, useState } from 'react';
import { View } from 'react-native';

import { ModeBadge } from '@/components/mode-badge';
import { NeedsSetup } from '@/components/needs-setup';
import { Body, Button, Card, Chips, Details, ErrorBox, Field, KeyValue, Notice, Rating, ResultHero, Screen, Section } from '@/components/ui';
import { api, uid } from '@/lib/api';
import { RISK_STATUS } from '@/lib/explain';
import { colomboDate, sampleDiary, type RiskProfile } from '@/lib/fixtures';
import { useActiveParticipant, usePendingId, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { space } from '@/theme';

const DAYS = [0, -1, -2] as const;
const dayLabel = (d: number) => (d === 0 ? 'Today' : d === -1 ? 'Yesterday' : `${-d} days ago`);

const NUMBER_FIELDS = [
  ['sleep_hours', 'Sleep', 'decimal', 'h'],
  ['study_minutes', 'Study', 'int', 'min'],
  ['break_minutes', 'Breaks', 'int', 'min'],
  ['late_study_minutes', 'Late-night study', 'int', 'min'],
  ['planned_tasks', 'Tasks planned', 'int', ''],
  ['completed_tasks', 'Tasks done', 'int', ''],
] as const;

type DailyText = Record<(typeof NUMBER_FIELDS)[number][0], string>;
const EMPTY_DAILY: DailyText = { sleep_hours: '', study_minutes: '', break_minutes: '', late_study_minutes: '', planned_tasks: '', completed_tasks: '' };
const NO_DAILY_RATINGS = { fatigue: null, mental_strain: null, concentration_readiness: null };

/** Blank stays missing (omitted); 0 is a real observation. Never Number(''). */
function parseDaily(text: DailyText) {
  const out: Record<string, number> = {};
  for (const [key, label, kind] of NUMBER_FIELDS) {
    const raw = text[key].trim();
    if (!raw) continue;
    const value = kind === 'int' ? Number.parseInt(raw, 10) : Number.parseFloat(raw);
    if (!Number.isFinite(value) || (kind === 'int' && String(value) !== raw)) throw new Error(`${label}: enter a ${kind === 'int' ? 'whole number' : 'number'} or leave it blank.`);
    out[key] = value;
  }
  return out;
}

function RiskScreenContent() {
  const { connection } = useSession();
  const active = useActiveParticipant();
  const { busy, error, run } = useAction();
  // Keep reported_at for a pending record so a retry sends identical content.
  const pendingReportedAt = useRef<Record<string, string>>({});
  const predictionId = usePendingId('pred');

  const [samplePid, setSamplePid] = useState<string | null>(null);
  const [dailyDay, setDailyDay] = useState<number>(0);
  const [daily, setDaily] = useState<DailyText>(EMPTY_DAILY);
  const [dailyRatings, setDailyRatings] = useState<Record<string, number | null>>(NO_DAILY_RATINGS);
  const [weekly, setWeekly] = useState<Record<string, number | null>>({ exhaustion: null, disengagement: null, academic_efficacy: null });
  const [savedDaily, setSavedDaily] = useState<string | null>(null);
  const [savedWeekly, setSavedWeekly] = useState(false);
  const [profile, setProfile] = useState<RiskProfile>('rising');
  const [prediction, setPrediction] = useState<any>(null);

  if (!active) return <Screen eyebrow="Component 3 · Risk" title="Risk"><NeedsSetup /></Screen>;
  const pid = samplePid ?? active.id;
  const common = { participant_id: active.id, data_source: active.source, consent: true };
  const reportedAt = (recordId: string) => (pendingReportedAt.current[recordId] ??= new Date().toISOString());
  const ratingsBody = (r: Record<string, number | null>) => Object.fromEntries(Object.entries(r).filter(([, v]) => v !== null));

  const submitDaily = () =>
    run('daily', async () => {
      // One daily record per date: the date-based ID makes retries safe and edits a 409 conflict.
      const observedOn = colomboDate(dailyDay);
      const recordId = `daily-${observedOn}`;
      const body = { ...common, client_record_id: recordId, observed_on: observedOn, reported_at: reportedAt(recordId), ...parseDaily(daily), ...ratingsBody(dailyRatings) };
      await api(connection, '/risk/daily', { body });
      delete pendingReportedAt.current[recordId];
      setDaily(EMPTY_DAILY);
      setDailyRatings(NO_DAILY_RATINGS);
      setSavedDaily(`${dayLabel(dailyDay)}'s entry saved (${observedOn}).`);
    });

  const submitWeekly = () =>
    run('weekly', async () => {
      const recordId = `weekly-${colomboDate(0)}`;
      const body = { ...common, client_record_id: recordId, observed_on: colomboDate(0), reported_at: reportedAt(recordId), instrument_version: 'exploratory-exhaustion-item-v1', ...ratingsBody(weekly) };
      await api(connection, '/risk/weekly', { body });
      delete pendingReportedAt.current[recordId];
      setSavedWeekly(true);
    });

  const forecast = (participantId: string) =>
    run('forecast', async () => {
      setPrediction(await api(connection, '/risk/predictions', { body: { participant_id: participantId, client_prediction_id: predictionId.get() } }));
      predictionId.done();
    });

  const loadSample = () =>
    run('sample', async () => {
      const id = uid(`C3-${profile}`);
      await api(connection, '/participants', { body: { participant_id: id, data_source: 'synthetic_demo', consent: true } });
      const { daily: days, weekly: weeks } = sampleDiary(id, profile);
      await api(connection, '/risk/daily/batch', { body: { records: days } });
      for (const record of weeks) await api(connection, '/risk/weekly', { body: record });
      setSamplePid(id);
      setPrediction(await api(connection, '/risk/predictions', { body: { participant_id: id, client_prediction_id: 'sample-forecast' } }));
    });

  const snapshot = prediction?.snapshot;
  const status = prediction ? RISK_STATUS[prediction.status] ?? { title: prediction.status, text: '' } : null;
  const hasInput = Object.values(daily).some((v) => v.trim()) || Object.values(dailyRatings).some((v) => v !== null);

  // Two fields per row keeps the diary short on a phone.
  const pairs = [NUMBER_FIELDS.slice(0, 2), NUMBER_FIELDS.slice(2, 4), NUMBER_FIELDS.slice(4, 6)];

  return (
    <Screen eyebrow="Component 3 · Risk" title="Your weeks," dim="and where they’re heading." badge={<ModeBadge />}>
      <Section label="Daily diary">
        <Card>
          <Chips options={DAYS} value={dailyDay} onChange={setDailyDay} format={dayLabel} />
          {pairs.map((pair) => (
            <View key={pair[0][0]} style={{ flexDirection: 'row', gap: space.sm }}>
              {pair.map(([key, label, kind, unit]) => (
                <View key={key} style={{ flex: 1 }}>
                  <Field label={label} unit={unit} value={daily[key]} onChangeText={(t) => setDaily({ ...daily, [key]: t })} keyboardType={kind === 'int' ? 'number-pad' : 'decimal-pad'} placeholder="—" />
                </View>
              ))}
            </View>
          ))}
          <Body small muted>Leave anything you didn’t track blank. Blank means unknown; 0 means none.</Body>
          <Rating label="Fatigue" value={dailyRatings.fatigue} onChange={(v) => setDailyRatings({ ...dailyRatings, fatigue: v })} />
          <Rating label="Mental strain" value={dailyRatings.mental_strain} onChange={(v) => setDailyRatings({ ...dailyRatings, mental_strain: v })} />
          <Rating label="Ready to concentrate" value={dailyRatings.concentration_readiness} onChange={(v) => setDailyRatings({ ...dailyRatings, concentration_readiness: v })} low="Not ready" high="Very ready" />
          <Button label="Save entry" icon="save" onPress={submitDaily} loading={busy === 'daily'} disabled={!hasInput} />
          {savedDaily ? <Notice icon="check-circle" tone="cyan">{savedDaily}</Notice> : null}
        </Card>
      </Section>

      <Section label="This week">
        <Card>
          <Rating label="Exhaustion" value={weekly.exhaustion} onChange={(v) => { setWeekly({ ...weekly, exhaustion: v }); setSavedWeekly(false); }} required />
          <Rating label="Disengagement" value={weekly.disengagement} onChange={(v) => { setWeekly({ ...weekly, disengagement: v }); setSavedWeekly(false); }} />
          <Rating label="Academic efficacy" value={weekly.academic_efficacy} onChange={(v) => { setWeekly({ ...weekly, academic_efficacy: v }); setSavedWeekly(false); }} />
          <Button
            label={savedWeekly ? 'Weekly check saved' : 'Save weekly check'}
            icon={savedWeekly ? 'check' : undefined}
            variant="secondary"
            onPress={submitWeekly}
            loading={busy === 'weekly'}
            disabled={weekly.exhaustion === null || savedWeekly}
          />
        </Card>
      </Section>

      <Section label="Forecast">
        <Card>
          <Body small muted>
            {active.real
              ? 'Your real entries are stored and summarised. The bundled model was trained only on simulated people, so real records are not scored.'
              : 'A score needs at least 7 earlier days. Try your own diary, or load a 14-day sample history.'}
          </Body>
          <Button label="Forecast my diary" icon="insights" variant="secondary" onPress={() => { setSamplePid(null); forecast(active.id); }} loading={busy === 'forecast'} />
          {active.real ? null : (
            <>
              <Chips options={['steady', 'rising'] as const} value={profile} onChange={setProfile} format={(p) => (p === 'steady' ? 'Steady sample' : 'Rising sample')} icons={{ steady: 'trending-flat', rising: 'trending-up' }} />
              <Button label="Load sample and forecast" icon="auto-graph" onPress={loadSample} loading={busy === 'sample'} />
            </>
          )}
        </Card>
      </Section>

      <ErrorBox error={error} />

      {prediction && status ? (
        <Section label="Your forecast">
          {prediction.risk ? (
            <ResultHero
              icon="insights"
              label="Next-week exhaustion proxy"
              value={prediction.risk.model_probability >= prediction.risk.decision_threshold ? 'Higher proxy score' : 'Lower proxy score'}
              tone={prediction.risk.model_probability >= prediction.risk.decision_threshold ? 'warn' : 'success'}
              meter={prediction.risk.model_probability}
              meterLabel={`${status.title} ${prediction.risk.model_probability.toFixed(2)}`}
              explanation={`${status.text} Forecast window ${snapshot.target_start} to ${snapshot.target_end}.`}
            />
          ) : (
            <ResultHero
              icon="hourglass-empty"
              label="Next-week exhaustion proxy"
              value={status.title}
              explanation={`${status.text}${snapshot ? ` You have ${snapshot.daily_report_count} of 7 daily entries in the last 14 days.` : ''}`}
            />
          )}
          <Details>
            <KeyValue
              rows={[
                ['Participant', pid],
                ['Status', prediction.status],
                ['Daily entries used', String(snapshot?.daily_report_count ?? '—')],
                ['Days with sleep/study/tasks', String(snapshot?.behavior_report_days ?? '—')],
                ['Weekly check available', snapshot ? (snapshot.weekly_report_available ? 'yes' : 'no') : '—'],
                ['Lookback', snapshot ? `${snapshot.lookback_start} → ${snapshot.lookback_end}` : '—'],
                ['Missing features', snapshot?.missing_feature_names?.length ? snapshot.missing_feature_names.join(', ') : 'none'],
                ['Reasons', snapshot?.reasons?.length ? snapshot.reasons.join(', ') : 'none'],
              ]}
            />
            {prediction.warnings.map((w: string) => (
              <Body key={w} small muted>
                {w}
              </Body>
            ))}
          </Details>
        </Section>
      ) : null}

      <Notice icon="info-outline">An exploratory single-question proxy, not a burnout diagnosis. Study days use Sri Lanka time.</Notice>
    </Screen>
  );
}

/** Remount when the participant changes so no state leaks between demo and real data. */
export default function RiskScreen() {
  const active = useActiveParticipant();
  return <RiskScreenContent key={active?.id ?? 'none'} />;
}
