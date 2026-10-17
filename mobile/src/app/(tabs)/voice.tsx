import { File, Paths } from 'expo-file-system';
import { useCallback, useEffect, useState } from 'react';
import { View } from 'react-native';

import { CaptureView, type VoiceResult } from '@/components/capture-view';
import { NeedsSetup } from '@/components/needs-setup';
import { ModeBadge } from '@/components/mode-badge';
import { Body, Button, Card, Chips, Details, ErrorBox, KeyValue, Notice, ResultHero, Screen, Section } from '@/components/ui';
import { api, apiRoot, getPublic, uid, uploadFile } from '@/lib/api';
import { capitalize, qualityTips } from '@/lib/explain';
import { usePendingId, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { space } from '@/theme';

type Sample = { filename: string; dataset_recording_id: string; dataset_label: string };
type Recording = { uri: string; recordedAt: string; durationSec: number; clientSessionId: string };

function VoiceScreenContent() {
  const { connection, participants, mode } = useSession();
  const real = mode === 'real' && Boolean(participants?.local);
  const pid = real ? participants?.local : participants?.publicAudio;
  const { busy, error, run } = useAction();
  const sessionId = usePendingId('voice');

  const [model, setModel] = useState<any>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [result, setResult] = useState<{ label: string | null; response: any } | null>(null);

  const load = useCallback(async () => {
    const manifest = await getPublic(connection, '/voice-demo/samples');
    setSamples(manifest.samples);
    setSelected((current) => current ?? manifest.samples[0]?.dataset_recording_id ?? null);
    setModel(await api(connection, '/voice/model'));
  }, [connection]);

  useEffect(() => {
    if (pid) run('load', load);
  }, [pid, load, run]);

  if (!pid) return <Screen title="Voice"><NeedsSetup /></Screen>;

  const sample = samples.find((s) => s.dataset_recording_id === selected);

  // Backend expects multipart fields "metadata" (JSON text) and "audio" (the WAV).
  const upload = (file: File, metadata: object) => uploadFile(connection, '/voice/checkins', file, 'audio', { metadata: JSON.stringify(metadata) }, 'audio/wav');

  // Demo mode: original public WAV fetched from the backend, uploaded byte-for-byte.
  const analyzeSample = () =>
    run('analyze', async () => {
      if (!sample) return;
      const file = new File(Paths.cache, sample.filename);
      if (!file.exists) await File.downloadFileAsync(`${apiRoot(connection)}/voice-demo/audio/${sample.filename}`, file);
      const response = await upload(file, {
        participant_id: pid,
        client_session_id: sessionId.get(),
        data_source: 'public_dataset',
        consent: true,
        dataset: 'RAVDESS',
        dataset_recording_id: sample.dataset_recording_id,
      });
      sessionId.done();
      setResult({ label: sample.dataset_label, response });
    });

  // Real mode: a PCM16 WAV recorded in the capture WebView. The recording keeps its
  // client ID so a failed upload can be retried without creating a duplicate.
  const uploadRecording = (rec: Recording) =>
    run('analyze', async () => {
      const response = await upload(new File(rec.uri), {
        participant_id: pid,
        client_session_id: rec.clientSessionId,
        data_source: 'local_research',
        consent: true,
        recorded_at: rec.recordedAt,
      });
      setUploaded(true);
      setResult({ label: null, response });
    });

  const onVoice = (voice: VoiceResult) => {
    setCaptureError(null);
    const file = new File(Paths.cache, `recording-${Date.now()}.wav`);
    file.create();
    file.write(voice.base64, { encoding: 'base64' });
    const rec = { uri: file.uri, recordedAt: voice.recordedAt, durationSec: voice.durationSec, clientSessionId: uid('voice') };
    setRecording(rec);
    setUploaded(false);
    uploadRecording(rec);
  };

  const prediction = result?.response.prediction;
  const scores = prediction ? (Object.entries(prediction.decision_scores) as [string, number][]).sort((a, b) => b[1] - a[1]) : [];

  return (
    <Screen title="Voice" badge={<ModeBadge />} subtitle="Acoustic features from a short speech sample.">
      {real ? (
        <Section label="Record">
          <CaptureView kind="voice" onVoice={onVoice} onError={setCaptureError} />
          {busy === 'analyze' ? <Body small muted center>Analyzing your recording…</Body> : null}
          {recording && !uploaded && busy !== 'analyze' ? <Button label="Retry upload" icon="refresh" variant="secondary" onPress={() => uploadRecording(recording)} /> : null}
        </Section>
      ) : (
        <Section label="Public sample">
          <Card>
            <Body small muted>Pick a recording from the public RAVDESS acted-speech dataset.</Body>
            <Chips options={samples.map((s) => s.dataset_recording_id)} value={selected} onChange={setSelected} format={(id) => capitalize(samples.find((s) => s.dataset_recording_id === id)?.dataset_label ?? id)} />
            <Button label="Analyze sample" icon="graphic-eq" onPress={analyzeSample} loading={busy === 'analyze'} disabled={!sample} />
          </Card>
        </Section>
      )}

      <ErrorBox error={error ?? captureError} />

      {result ? (
        <Section label="Your result">
          {prediction ? (
            <ResultHero
              icon="graphic-eq"
              label="Closest acted speech style"
              value={capitalize(prediction.predicted_emotion_style)}
              explanation={
                result.label
                  ? `The actor was asked to sound “${result.label}”. ${prediction.predicted_emotion_style === result.label ? 'The model matched it.' : 'The model picked a different style, which happens: it is right about half the time on this dataset.'}`
                  : 'This is the closest of eight acted speaking styles. It describes how the audio sounds, not how you feel.'
              }
            />
          ) : (
            <ResultHero icon="mic-off" label="Recording not usable" value="Let's try again" tone="error" explanation={qualityTips(result.response.quality.reasons).join('. ') + '.'} />
          )}
          <Details>
            {scores.length ? (
              <View style={{ gap: space.xs }}>
                <Body small muted>Decision scores (uncalibrated, not probabilities)</Body>
                <KeyValue rows={scores.map(([label, score]) => [capitalize(label), score.toFixed(3)])} />
              </View>
            ) : null}
            <KeyValue
              rows={[
                ['Duration', `${result.response.quality.duration_sec.toFixed(2)} s`],
                ['Speech activity', `${Math.round(result.response.quality.active_fraction * 100)}%`],
                ['Level', `${result.response.quality.rms_dbfs.toFixed(1)} dBFS`],
                ['Features extracted', String(result.response.features ? Object.keys(result.response.features).length : 0)],
                ['Model', model?.model_id ?? '—'],
                ['Session ID', result.response.session_id],
              ]}
            />
            {result.response.warnings.map((w: string) => (
              <Body key={w} small muted>
                {w}
              </Body>
            ))}
          </Details>
        </Section>
      ) : null}

      <Notice icon={real ? 'mic' : 'science'} tone={real ? 'cyan' : 'violet'}>
        {real
          ? 'Your recording is uploaded as a WAV file. The model was trained on acted speech, so its label is not your emotion or wellbeing.'
          : 'Demo data: public RAVDESS acted speech (CC BY-NC-SA 4.0). Switch to Real capture on Setup to use the microphone.'}
      </Notice>
    </Screen>
  );
}

/** Remount when the participant changes so no state leaks between demo and real data. */
export default function VoiceScreen() {
  const { mode, participants } = useSession();
  return <VoiceScreenContent key={`${mode}-${participants?.local ?? participants?.publicAudio ?? 'none'}`} />;
}
