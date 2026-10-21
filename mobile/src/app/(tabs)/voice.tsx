import { File, Paths } from 'expo-file-system';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import type { WebView } from 'react-native-webview';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AuroraBackground } from '@/components/aurora-background';
import { CaptureView, type VoiceResult } from '@/components/capture-view';
import { NeedsSetup } from '@/components/needs-setup';
import { ModeBadge } from '@/components/mode-badge';
import { Body, Button, Card, Chips, Details, ErrorBox, KeyValue, Notice, ResultHero, Screen, ScreenHeader, ScreenTitle, Section } from '@/components/ui';
import { api, apiRoot, getPublic, uid, uploadFile } from '@/lib/api';
import { capitalize, qualityTips } from '@/lib/explain';
import { usePendingId, useSession } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { colors, fonts, space } from '@/theme';

type Sample = { filename: string; dataset_recording_id: string; dataset_label: string };
type Recording = { uri: string; recordedAt: string; durationSec: number; clientSessionId: string };

/** Three of the 88 eGeMAPS features in plain words: real measurements, unlike the acted-style label. */
function voiceMeasures(f: Record<string, number>): [string, string][] {
  const fmt = (v: number | undefined, digits: number, unit: string) => (Number.isFinite(v) ? `${(v as number).toFixed(digits)}${unit}` : '—');
  const semitones = f['F0semitoneFrom27.5Hz_sma3nz_amean'];
  // eGeMAPS pitch is in semitones above 27.5 Hz.
  const hz = Number.isFinite(semitones) && semitones > 0 ? 27.5 * 2 ** (semitones / 12) : undefined;
  return [
    ['Pitch', fmt(hz, 0, ' Hz')],
    ['Pitch range', fmt(f['F0semitoneFrom27.5Hz_sma3nz_pctlrange0-2'], 1, ' st')],
    ['Pace', fmt(f.loudnessPeaksPerSec, 1, '/s')],
  ];
}

/** Bottom sheet: the backdrop fades in place while only the panel slides up (and back on close). */
function DetailsSheet({ visible, onClose, children }: { visible: boolean; onClose: () => void; children: ReactNode }) {
  const [anim] = useState(() => new Animated.Value(0));
  const open = () => Animated.timing(anim, { toValue: 1, duration: 280, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
  const close = () => Animated.timing(anim, { toValue: 0, duration: 200, easing: Easing.in(Easing.cubic), useNativeDriver: true }).start(() => onClose());
  const translateY = anim.interpolate({ inputRange: [0, 1], outputRange: [700, 0] });
  return (
    <Modal visible={visible} transparent animationType="none" statusBarTranslucent onShow={open} onRequestClose={close}>
      <Animated.View style={[styles.backdrop, { opacity: anim }]}>
        <Pressable style={{ flex: 1 }} onPress={close} accessibilityLabel="Close details" />
      </Animated.View>
      <Animated.View style={[styles.sheet, { transform: [{ translateY }] }]}>
        <View style={styles.grabber} />
        <View style={styles.sheetHeader}>
          <Text style={styles.sheetTitle}>Technical details</Text>
          <Pressable onPress={close} accessibilityRole="button" hitSlop={12}>
            <Text style={styles.sheetDone}>Done</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={styles.sheetBody}>{children}</ScrollView>
      </Animated.View>
    </Modal>
  );
}

function VoiceScreenContent() {
  const { connection, participants, mode } = useSession();
  const real = mode === 'real' && Boolean(participants?.local);
  const pid = real ? participants?.local : participants?.publicAudio;
  const { busy, error, run, clearError } = useAction();
  const sessionId = usePendingId('voice');

  const [model, setModel] = useState<any>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [result, setResult] = useState<{ label: string | null; response: any } | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const web = useRef<WebView>(null);

  const load = useCallback(async () => {
    const manifest = await getPublic(connection, '/voice-demo/samples');
    setSamples(manifest.samples);
    setSelected((current) => current ?? manifest.samples[0]?.dataset_recording_id ?? null);
    setModel(await api(connection, '/voice/model'));
  }, [connection]);

  useEffect(() => {
    if (pid) run('load', load);
  }, [pid, load, run]);

  // Real mode: show the outcome on the orb screen.
  useEffect(() => {
    if (!real) return;
    const failure = error ?? captureError;
    let payload: object | null = null;
    if (result?.response.prediction) {
      payload = {
        kind: 'ok',
        style: capitalize(result.response.prediction.predicted_emotion_style),
        measures: result.response.features ? voiceMeasures(result.response.features) : [],
        note: 'Acted-speech style: how the audio sounds, not how you feel.',
      };
    } else if (result) {
      payload = { kind: 'unusable', title: "Let's try again", message: qualityTips(result.response.quality.reasons).join('. ') + '.' };
    } else if (failure && busy !== 'analyze') {
      payload = { kind: 'error', title: captureError && !error ? 'Try again' : 'Not sent', message: failure instanceof Error ? failure.message : String(failure), canRetry: Boolean(recording && !uploaded) };
    }
    if (payload) web.current?.injectJavaScript(`window.__result(${JSON.stringify(payload)});true;`);
  }, [real, result, error, captureError, busy, recording, uploaded]);

  if (!pid) return <Screen eyebrow="Component 2 · Voice" title="Voice"><NeedsSetup /></Screen>;

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

  const technicalBody = result ? (
    <>
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
    </>
  ) : null;
  const technical = technicalBody ? <Details>{technicalBody}</Details> : null;

  // Real mode: the recorder fills the tab under the header. The result is shown on the orb screen
  // itself (sent into the page); "Details ›" opens the technical details.
  if (real) {
    return (
      <SafeAreaView style={styles.full} edges={['top']}>
        {/* One background for the header and the recorder (the recorder page is transparent). */}
        <AuroraBackground intensity={0.55} />
        <View style={styles.headerBar}>
          <ScreenHeader badge={<ModeBadge />} />
          <ScreenTitle eyebrow="Component 2 · Voice" title="Your voice," dim="as acoustic features." compact />
        </View>
        <CaptureView
          kind="voice"
          webRef={web}
          onVoice={onVoice}
          onError={setCaptureError}
          onEvent={(type) => {
            if (type === 'details') setDetailsOpen(true);
            else if (type === 'retry' && recording) uploadRecording(recording);
            else if (type === 'reset') {
              setResult(null);
              setRecording(null);
              setCaptureError(null);
              clearError();
            }
          }}
        />
        <DetailsSheet visible={detailsOpen} onClose={() => setDetailsOpen(false)}>
          {technicalBody}
        </DetailsSheet>
      </SafeAreaView>
    );
  }

  return (
    <Screen eyebrow="Component 2 · Voice" title="Your voice," dim="as acoustic features." badge={<ModeBadge />}>
        <Section label="Public sample">
          <Card>
            <Body small muted>Pick a recording from the public RAVDESS acted-speech dataset.</Body>
            <Chips options={samples.map((s) => s.dataset_recording_id)} value={selected} onChange={setSelected} format={(id) => capitalize(samples.find((s) => s.dataset_recording_id === id)?.dataset_label ?? id)} />
            <Button label="Analyze sample" icon="graphic-eq" onPress={analyzeSample} loading={busy === 'analyze'} disabled={!sample} />
          </Card>
        </Section>

      <ErrorBox error={error ?? captureError} />

      {result ? (
          <Section label="Your result">
            {prediction ? (
              <ResultHero
                icon="graphic-eq"
                label="Closest acted speech style"
                value={capitalize(prediction.predicted_emotion_style)}
                explanation={`The actor was asked to sound “${result.label}”. ${prediction.predicted_emotion_style === result.label ? 'The model matched it.' : 'The model picked a different style, which happens: it is right about half the time on this dataset.'}`}
              />
            ) : (
              <ResultHero icon="mic-off" label="Recording not usable" value="Let's try again" tone="error" explanation={qualityTips(result.response.quality.reasons).join('. ') + '.'} />
            )}
            {technical}
          </Section>
      ) : null}

      <Notice icon={real ? 'mic' : 'science'} tone={real ? 'cyan' : 'violet'}>
        {real
          ? 'Your recording is uploaded as a WAV file. The model was trained on acted speech, so its label is not your emotion or wellbeing.'
          : 'Demo data: public RAVDESS acted speech (CC BY-NC-SA 4.0). Switch to Real capture on Profile to use the microphone.'}
      </Notice>
    </Screen>
  );
}

/** Remount when the participant changes so no state leaks between demo and real data. */
export default function VoiceScreen() {
  const { mode, participants } = useSession();
  return <VoiceScreenContent key={`${mode}-${participants?.local ?? participants?.publicAudio ?? 'none'}`} />;
}

const styles = StyleSheet.create({
  full: { flex: 1, backgroundColor: colors.base },
  // Same spacing as Screen (ui.tsx), so the header and title sit exactly where they do on the other tabs.
  headerBar: { paddingHorizontal: space.gutter, paddingTop: space.base, gap: space.lg },
  backdrop: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)' },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    maxHeight: '75%',
    backgroundColor: colors.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
  },
  grabber: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: colors.borderStrong, marginTop: space.base },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space.md,
    paddingTop: space.sm,
    paddingBottom: space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.borderStrong,
  },
  sheetTitle: { flex: 1, fontFamily: fonts.semibold, fontSize: 18, color: colors.ink },
  sheetDone: { fontFamily: fonts.semibold, fontSize: 16, color: colors.primary },
  sheetBody: { paddingHorizontal: space.md, paddingTop: space.md, paddingBottom: space.xl, gap: space.md },
});
