import { LinearGradient } from 'expo-linear-gradient';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { Modal, View } from 'react-native';

import { CaptureView, type FaceResult } from '@/components/capture-view';
import { ModeBadge } from '@/components/mode-badge';
import { NeedsSetup } from '@/components/needs-setup';
import { Body, Button, Card, Chips, Details, ErrorBox, KeyValue, Notice, Rating, ResultHero, Screen, Section, Toggle } from '@/components/ui';
import { api } from '@/lib/api';
import { FACE_EXTRACTOR_VERSION } from '@/lib/capture/face-math';
import { TASK_PROMPT, type FaceProtocol } from '@/lib/capture/pages';
import { LEVEL, qualityTips, temporalText } from '@/lib/explain';
import { facialSession, type FacialScenario } from '@/lib/fixtures';
import { useActiveParticipant, usePendingId, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { colors, gradient, radius, space } from '@/theme';

const SCENARIOS: FacialScenario[] = ['stable', 'return', 'persistent', 'poor_quality'];

type Ratings = { fatigue: number | null; mental_strain: number | null; concentration_readiness: number | null };
const NO_RATINGS: Ratings = { fatigue: null, mental_strain: null, concentration_readiness: null };

function Progress({ value, total }: { value: number; total: number }) {
  return (
    <View style={{ flexDirection: 'row', gap: space.xs }}>
      {Array.from({ length: total }, (_, i) => (
        // Purple accent for progress, as in the editorial design.
        i < value ? (
          <LinearGradient key={i} colors={gradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={{ flex: 1, height: 6, borderRadius: radius.chip }} />
        ) : (
          <View key={i} style={{ flex: 1, height: 6, borderRadius: radius.chip, backgroundColor: colors.raised }} />
        )
      ))}
    </View>
  );
}

function FacialScreenContent() {
  const { connection } = useSession();
  const active = useActiveParticipant();
  const pid = active?.id;
  const { busy, error, run } = useAction();
  const calibrationId = usePendingId('cal');
  const checkinId = usePendingId('chk');

  const [calibrations, setCalibrations] = useState<any[]>([]);
  const [baseline, setBaseline] = useState<any>(null);
  const [scenario, setScenario] = useState<FacialScenario>('return');
  const [capture, setCapture] = useState<FaceProtocol | null>(null);
  const [calmConfirmed, setCalmConfirmed] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [ratings, setRatings] = useState<Ratings>(NO_RATINGS);
  const [ratingSaved, setRatingSaved] = useState(false);

  const refresh = useCallback(async () => {
    if (!pid) return;
    const history = await api(connection, `/facial/history/${pid}?kind=calibration&limit=100`);
    setCalibrations(history.sessions);
    const baselines = await api<any[]>(connection, `/facial/baselines/${pid}`);
    // The API lists newest first; pick the highest version rather than relying on order.
    setBaseline(baselines.reduce<any>((latest, b) => (!latest || b.version > latest.version ? b : latest), null));
  }, [connection, pid]);

  useEffect(() => {
    run('load', refresh);
  }, [refresh, run]);

  if (!active || !pid) return <Screen eyebrow="Component 1 · Facial" title="Facial"><NeedsSetup /></Screen>;

  const accepted = calibrations.filter((s) => s.status === 'accepted');
  // References not yet in the current baseline: the progress bar counts these, so it starts
  // empty again after each baseline and a fresh set of 3 can replace it.
  // "New" means recorded after the newest reference in the current baseline.
  const inBaseline = new Set<string>(baseline?.session_ids ?? []);
  const newestInBaseline = Math.max(0, ...accepted.filter((s) => inBaseline.has(s.session_id)).map((s) => Date.parse(s.recorded_at)));
  const fresh = accepted.filter((s) => !inBaseline.has(s.session_id) && Date.parse(s.recorded_at) > newestInBaseline);
  const freshCount = Math.min(fresh.length, 3);

  const showResult = (response: any) => {
    setResult(response);
    setRatings(NO_RATINGS);
    setRatingSaved(false);
  };

  // Demo mode: synthetic numerical windows.
  const addSyntheticCalibration = () =>
    run('calibration', async () => {
      // Dated in the past so they always end before a check-in starts.
      const index = calibrations.length;
      const recordedAt = new Date(Date.now() - 3 * 86400000 + index * 3600000);
      await api(connection, '/facial/calibrations', { body: facialSession({ participantId: pid, clientSessionId: calibrationId.get(), recordedAt, calibrationIndex: index }) });
      calibrationId.done();
      await refresh();
    });

  const syntheticCheckIn = () =>
    run('checkin', async () => {
      const response = await api(connection, '/facial/checkins', {
        body: facialSession({ participantId: pid, clientSessionId: checkinId.get(), recordedAt: new Date(Date.now() - 120000), scenario }),
      });
      checkinId.done();
      showResult(response);
    });

  // Real mode: numbers measured from the camera by the capture WebView.
  const submitCapture = (protocol: FaceProtocol, face: FaceResult) =>
    run(protocol === 'neutral_only' ? 'calibration' : 'checkin', async () => {
      setCapture(null);
      const calibration = protocol === 'neutral_only';
      const pending = calibration ? calibrationId : checkinId;
      const body = {
        participant_id: pid,
        client_session_id: pending.get(),
        data_source: 'local_research',
        feature_schema_version: 'facial-window-v1',
        extractor_version: FACE_EXTRACTOR_VERSION,
        recorded_at: face.recordedAt,
        consent: true,
        baseline_condition_confirmed: calibration,
        protocol,
        windows: face.windows,
      };
      const response = await api(connection, calibration ? '/facial/calibrations' : '/facial/checkins', { body });
      pending.done();
      if (calibration) {
        await refresh();
        if (response.status !== 'accepted') showResult(response);
        else setResult(null);
      } else {
        showResult(response);
      }
    });

  const createBaseline = () =>
    run('baseline', async () => {
      await api(connection, '/facial/baselines', { body: { participant_id: pid, session_ids: fresh.slice(-10).map((s) => s.session_id) } });
      await refresh();
    });

  const saveRatings = () =>
    run('ratings', async () => {
      await api(connection, `/facial/self-reports/${result.session_id}`, { body: ratings });
      setRatingSaved(true);
    });

  // Full-screen camera in a modal, over the normal screen (covers the header and tab bar).
  const captureModal = (
    <Modal visible={capture !== null} animationType="fade" presentationStyle="fullScreen" statusBarTranslucent onRequestClose={() => setCapture(null)}>
      <StatusBar style="light" />
      {capture ? (
        <CaptureView
          kind="face"
          protocol={capture}
          onFace={(face) => submitCapture(capture, face)}
          onCancel={() => setCapture(null)}
          onError={(message) => {
            setCaptureError(message);
            setCapture(null);
          }}
        />
      ) : null}
    </Modal>
  );

  const level = result?.deviation ? LEVEL[result.deviation.level] : null;

  return (
    <>
      <Screen eyebrow="Component 1 · Facial" title="Your face," dim="compared with your normal." badge={<ModeBadge />}>
        <Section label="Reference" step={1} done={Boolean(baseline)}>
          <Card>
            {baseline ? <Body>{`Baseline ready (version ${baseline.version}, from ${baseline.session_ids.length} references)`}</Body> : null}
            <View style={{ gap: space.base }}>
              <Body small muted>{baseline ? `New references: ${freshCount} of 3` : `${freshCount} of 3 references recorded`}</Body>
              <Progress value={freshCount} total={3} />
              {baseline && fresh.length === 0 ? <Body small muted>To update your baseline, record 3 new references.</Body> : null}
            </View>
            {active.real ? (
              <>
                <Body small muted>Record each in good light, at different times, when you feel normal and calm.</Body>
                <Toggle icon="self-improvement" label="I feel normal and calm now" value={calmConfirmed} onChange={setCalmConfirmed} />
                <Button
                  label={baseline ? 'Record new reference' : 'Record reference'}
                  icon="videocam"
                  variant={freshCount >= 3 ? 'secondary' : 'primary'}
                  onPress={() => { setCaptureError(null); setCapture('neutral_only'); }}
                  loading={busy === 'calibration'}
                  disabled={!calmConfirmed}
                />
              </>
            ) : (
              <Button label="Add synthetic reference" icon="add" variant={freshCount >= 3 ? 'secondary' : 'primary'} onPress={addSyntheticCalibration} loading={busy === 'calibration'} />
            )}
            {fresh.length >= 3 ? (
              <Button label={baseline ? 'Replace baseline with new references' : 'Create baseline'} icon="done-all" onPress={createBaseline} loading={busy === 'baseline'} />
            ) : null}
          </Card>
        </Section>

        <Section label="Check-in" step={2} done={Boolean(result?.deviation)}>
          <Card>
            {active.real ? (
              <Body small muted>{`15 s neutral → 15 s task (“${TASK_PROMPT}”) → 15 s quiet observation.`}</Body>
            ) : (
              <>
                <Body small muted>Choose a constructed scenario to send.</Body>
                <Chips options={SCENARIOS} value={scenario} onChange={setScenario} format={(s) => s.replace('_', ' ')} />
              </>
            )}
            <Button
              label={active.real ? 'Start camera check-in' : 'Run check-in'}
              icon={active.real ? 'videocam' : 'play-arrow'}
              onPress={active.real ? () => { setCaptureError(null); setCapture('neutral_task_recovery'); } : syntheticCheckIn}
              loading={busy === 'checkin'}
              disabled={!baseline}
            />
            {!baseline ? <Body small muted center>Create your baseline first.</Body> : null}
          </Card>
        </Section>

        <ErrorBox error={error ?? captureError} />

        {result ? (
          <Section label="Your result">
            {level ? (
              <ResultHero
                icon="face"
                label="Visual change"
                value={level.title}
                tone={level.tone}
                meter={result.deviation.mean_absolute_standardized_deviation / 3}
                meterLabel={`${result.deviation.mean_absolute_standardized_deviation.toFixed(2)} on the reference scale`}
                explanation={[level.text, temporalText(result.temporal)].filter(Boolean).join(' ')}
              />
            ) : (
              <ResultHero
                icon="videocam-off"
                label={result.protocol === 'neutral_only' ? 'Reference not usable' : 'Check-in not usable'}
                value="Let's try again"
                tone="error"
                explanation={qualityTips(result.quality.reasons).join('. ') + '.'}
              />
            )}
            <Details>
              <KeyValue
                rows={[
                  ['Usable fraction', String(result.quality.usable_fraction)],
                  ['Most changed features', result.deviation?.top_changed_features.join(', ') ?? '—'],
                  ['Phase deviations', result.temporal ? Object.entries(result.temporal.phase_deviations).map(([k, v]) => `${k} ${v}`).join(' · ') : '—'],
                  ['Extractor', result.extractor_version],
                  ['Session ID', result.session_id],
                ]}
              />
              {result.warnings.map((w: string) => (
                <Body key={w} small muted>
                  {w}
                </Body>
              ))}
            </Details>
          </Section>
        ) : null}

        {result?.deviation && result.protocol === 'neutral_task_recovery' ? (
          <Section label="How do you feel?" step={3} done={ratingSaved}>
            <Card>
              <Rating label="Fatigue" value={ratings.fatigue} onChange={(v) => setRatings({ ...ratings, fatigue: v })} required />
              <Rating label="Mental strain" value={ratings.mental_strain} onChange={(v) => setRatings({ ...ratings, mental_strain: v })} required />
              <Rating label="Ready to concentrate" value={ratings.concentration_readiness} onChange={(v) => setRatings({ ...ratings, concentration_readiness: v })} required low="Not ready" high="Very ready" />
              <Button
                label={ratingSaved ? 'Saved' : 'Save'}
                icon={ratingSaved ? 'check' : undefined}
                onPress={saveRatings}
                loading={busy === 'ratings'}
                disabled={ratingSaved || Object.values(ratings).some((v) => v === null)}
              />
            </Card>
          </Section>
        ) : null}

        <Notice icon={active.real ? 'shield' : 'science'} tone={active.real ? 'cyan' : 'violet'}>
          {active.real
            ? `Measured on this phone with MediaPipe; only numbers are sent. Thresholds are provisional.`
            : 'Demo data: synthetic numbers. Switch to Real capture on Profile to use the camera.'}
        </Notice>
      </Screen>
      {captureModal}
    </>
  );
}

/** Remount when the participant changes so no state leaks between demo and real data. */
export default function FacialScreen() {
  const active = useActiveParticipant();
  return <FacialScreenContent key={active?.id ?? 'none'} />;
}
