import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import Constants from 'expo-constants';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Alert, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { ModeBadge } from '@/components/mode-badge';
import { Badge, Body, Button, Card, Details, ErrorBox, Field, IconWell, KeyValue, Notice, Screen, Section, Title, Toggle, type IconName } from '@/components/ui';
import { api, getPublic } from '@/lib/api';
import { useSession, type Mode } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { colors, fonts, radius, space, type } from '@/theme';

// Profile, modelled on the profile/privacy designs. No sign-in: the name lives only on
// this phone, and "Reset this app" replaces "Sign out".

const EXPORT_LABELS: [string, string][] = [
  ['facial_sessions', 'Facial references and check-ins'],
  ['baselines', 'Facial baselines'],
  ['voice_sessions', 'Voice recordings analysed'],
  ['risk_daily', 'Diary days'],
  ['risk_weekly', 'Weekly checks'],
  ['risk_predictions', 'Forecasts'],
  ['intervention_sessions', 'Activities started'],
  ['intervention_feedback', 'Activity ratings'],
];

function confirm(title: string, message: string, action: string, onConfirm: () => void) {
  if (Platform.OS === 'web') {
    if (globalThis.confirm?.(`${title}\n\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [{ text: 'Cancel', style: 'cancel' }, { text: action, style: 'destructive', onPress: onConfirm }]);
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
}

/** Grouped settings list, as in the design: icon, title + subtitle, trailing control. */
function Row({ icon, title, subtitle, right, onPress, danger, last }: { icon: IconName; title: string; subtitle?: string; right?: ReactNode; onPress?: () => void; danger?: boolean; last?: boolean }) {
  const tint = danger ? colors.error : colors.textMuted;
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [styles.row, !last && styles.rowDivider, pressed && onPress ? { opacity: 0.7 } : null]} accessibilityRole={onPress ? 'button' : undefined}>
      <MaterialIcons name={icon} size={22} color={tint} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[styles.rowTitle, danger && { color: colors.error }]}>{title}</Text>
        {subtitle ? <Text style={styles.rowSub}>{subtitle}</Text> : null}
      </View>
      {right ?? (onPress ? <MaterialIcons name="chevron-right" size={22} color={danger ? colors.error : colors.textFaint} /> : null)}
    </Pressable>
  );
}

function ModeOption({ icon, title, text, selected, onPress }: { icon: IconName; title: string; text: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[styles.option, selected && styles.optionSelected]} accessibilityRole="radio" accessibilityState={{ selected }}>
      <IconWell icon={icon} color={selected ? colors.primary : colors.textFaint} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.optionTitle}>{title}</Text>
        <Text style={styles.optionText}>{text}</Text>
      </View>
      <MaterialIcons name={selected ? 'radio-button-checked' : 'radio-button-unchecked'} size={22} color={selected ? colors.primary : colors.textFaint} />
    </Pressable>
  );
}

export default function ProfileScreen() {
  const session = useSession();
  const { connection, setConnection, participants, register, mode, setMode, enableReal, displayName, setDisplayName, forgetLocal, resetParticipants, resetApp } = session;
  const [baseUrl, setBaseUrl] = useState(connection.baseUrl);
  const [apiKey, setApiKey] = useState(connection.apiKey);
  const [editingConnection, setEditingConnection] = useState(participants === null);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(displayName);
  const [consent, setConsent] = useState(false);
  const [realConsent, setRealConsent] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const [exported, setExported] = useState<Record<string, number> | null>(null);
  const { busy, error, run } = useAction();

  const checkHealth = useCallback(async () => setHealth(await getPublic(connection, '/health')), [connection]);
  useEffect(() => {
    if (participants) run('health', checkHealth);
  }, [participants, checkHealth, run]);

  const connected = participants !== null && !editingConnection;
  const real = mode === 'real' && Boolean(participants?.local);
  // Participants that hold this mode's records.
  const myIds = participants ? (real ? [participants.local!] : [participants.synthetic, participants.publicAudio]) : [];

  const connect = () =>
    run('connect', async () => {
      const result = await register({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() });
      setHealth(result.health);
      setEditingConnection(false);
    });

  const chooseMode = (next: Mode) => {
    setExported(null);
    if (next === 'demo' || participants?.local) setMode(next);
  };

  const exportData = () =>
    run('export', async () => {
      const totals: Record<string, number> = {};
      for (const id of myIds) {
        const data = await api(connection, `/participants/${id}/export`);
        for (const [key] of EXPORT_LABELS) totals[key] = (totals[key] ?? 0) + (Array.isArray(data[key]) ? data[key].length : 0);
      }
      setExported(totals);
    });

  const deleteData = () =>
    confirm(
      real ? 'Delete your real data?' : 'Delete your demo data?',
      'This permanently removes these records from the backend: facial, voice, diary and activities. It cannot be undone.',
      'Delete',
      () =>
        run('delete', async () => {
          for (const id of myIds) await api(connection, `/participants/${id}`, { method: 'DELETE' });
          setExported(null);
          if (real) forgetLocal();
          else {
            resetParticipants();
            setEditingConnection(true);
          }
        }),
    );

  const reset = () =>
    confirm('Reset this app?', 'This forgets your name, connection and participant IDs on this phone. Records already on the backend are kept.', 'Reset', () => {
      resetApp();
      router.replace('/welcome');
    });

  const shownName = displayName.trim() || 'Student';

  return (
    <Screen eyebrow="Profile" title="You," dim="and your data." badge={<ModeBadge showAvatar={false} />}>
      <View style={styles.hero}>
        <LinearGradient colors={[colors.indigo, colors.violet]} style={styles.avatarRing}>
          <View style={styles.avatar}>
            {displayName.trim() ? <Text style={styles.avatarText}>{initials(displayName)}</Text> : <MaterialIcons name="person" size={44} color={colors.primary} />}
          </View>
        </LinearGradient>
        {editingName ? (
          <View style={{ alignSelf: 'stretch', gap: space.sm }}>
            <Field label="Your name" value={nameDraft} onChangeText={setNameDraft} autoCapitalize="words" placeholder="e.g. Oshadi" hint="Stored only on this phone. It is never sent to the backend." />
            <Button label="Save name" onPress={() => { setDisplayName(nameDraft.trim()); setEditingName(false); }} />
          </View>
        ) : (
          <>
            <Text style={styles.name}>{shownName}</Text>
            <Pressable onPress={() => { setNameDraft(displayName); setEditingName(true); }} hitSlop={8}>
              <Text style={styles.editName}>{displayName.trim() ? 'Edit name' : 'Add your name'}</Text>
            </Pressable>
            <View style={styles.chips}>
              <View style={styles.tag}>
                <Text style={styles.tagText}>{real ? 'Real capture' : 'Demo data'}</Text>
              </View>
              {participants ? (
                <View style={[styles.tag, { backgroundColor: 'rgba(76,215,246,0.12)' }]}>
                  <Text style={[styles.tagText, { color: colors.tertiary }]}>{health ? 'Connected' : 'Offline'}</Text>
                </View>
              ) : null}
            </View>
          </>
        )}
      </View>

      <Card>
        <View style={{ flexDirection: 'row', gap: space.sm }}>
          <IconWell icon="shield" />
          <View style={{ flex: 1, gap: space.xs }}>
            <Title>Your Data, Your Control</Title>
            <Body small muted>
              EMPath+ is a private research prototype. Facial video never leaves your phone, records use a pseudonymous ID, and you can export or delete your data at any
              time below.
            </Body>
          </View>
        </View>
      </Card>

      <Section label="Connection">
        {connected ? (
          <Card>
            <View style={styles.statusRow}>
              <IconWell icon={health ? 'cloud-done' : 'cloud-queue'} color={health ? colors.tertiary : colors.textFaint} />
              <View style={{ flex: 1 }}>
                <Title>{health ? 'Connected' : busy === 'health' ? 'Checking…' : 'Connection saved'}</Title>
                <Body small muted>{connection.baseUrl}</Body>
              </View>
              <Button label="Edit" variant="text" onPress={() => setEditingConnection(true)} />
            </View>
            {health ? (
              <View style={styles.chips}>
                <Badge label={`Voice model ${health.voice_model}`} tone={health.voice_model === 'ready' ? 'success' : 'error'} />
                <Badge label={`Risk model ${health.risk_model?.status}`} tone={health.risk_model?.status === 'ready' ? 'success' : 'error'} />
              </View>
            ) : null}
          </Card>
        ) : (
          <Card>
            <Field label="Backend URL" value={baseUrl} onChangeText={setBaseUrl} keyboardType="url" hint="Your laptop's Wi-Fi address on port 8000. Start the backend with --host 0.0.0.0." />
            <Field label="API key" value={apiKey} onChangeText={setApiKey} hint="API_KEY from backend/.env." />
            {participants ? (
              <>
                <Button label="Save" onPress={() => { setConnection({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() }); setEditingConnection(false); }} />
                <Button label="Cancel" variant="secondary" onPress={() => { setBaseUrl(connection.baseUrl); setApiKey(connection.apiKey); setEditingConnection(false); }} />
              </>
            ) : (
              <>
                <Toggle icon="verified-user" label="I consent" description="Store pseudonymous test records on this backend. No names are sent." value={consent} onChange={setConsent} />
                <Button label="Connect and register" icon="link" onPress={connect} loading={busy === 'connect'} disabled={!consent} />
              </>
            )}
          </Card>
        )}
      </Section>

      <ErrorBox error={error} />

      {participants ? (
        <Section label="Data mode">
          <ModeOption icon="science" title="Demo data" text="Synthetic facial numbers, public voice samples, sample diaries." selected={mode === 'demo'} onPress={() => chooseMode('demo')} />
          <ModeOption icon="videocam" title="Real capture" text={participants.local ? 'Your camera, microphone and own entries.' : 'Needs your consent below.'} selected={mode === 'real'} onPress={() => chooseMode('real')} />
          {!participants.local ? (
            <Card>
              <Toggle
                icon="privacy-tip"
                label="I consent to real capture"
                description="Facial measurements from my camera (numbers only, no video), my voice recordings, diary and activity entries are stored on this backend for testing."
                value={realConsent}
                onChange={setRealConsent}
              />
              <Button label="Enable real capture" icon="videocam" onPress={() => run('real', enableReal)} loading={busy === 'real'} disabled={!realConsent} />
            </Card>
          ) : null}
        </Section>
      ) : null}

      {participants ? (
        <Section label="Privacy & data">
          <View style={styles.group}>
            <Row icon="videocam" title="Camera" subtitle="Facial check-ins are measured on this phone; only numbers are sent." right={<Text style={styles.rowValue}>{real ? 'In use' : 'Not used in demo'}</Text>} />
            <Row icon="mic" title="Microphone" subtitle="Voice check-ins upload a short WAV for analysis." right={<Text style={styles.rowValue}>{real ? 'In use' : 'Not used in demo'}</Text>} />
            <Row icon="download" title="Export my data" subtitle={`See every record stored for your ${real ? 'real' : 'demo'} participant.`} onPress={exportData} />
            <Row icon="delete-outline" title={real ? 'Delete my real data' : 'Delete my demo data'} subtitle="Permanently remove these records from the backend." onPress={deleteData} danger last />
          </View>
          {busy === 'export' || busy === 'delete' ? <Body small muted center>{busy === 'export' ? 'Collecting your records…' : 'Deleting…'}</Body> : null}
          {exported ? (
            <Card>
              <Text style={styles.sectionLabel}>STORED RECORDS</Text>
              <KeyValue rows={EXPORT_LABELS.map(([key, label]) => [label, String(exported[key] ?? 0)])} />
            </Card>
          ) : null}
        </Section>
      ) : null}

      <Section label="This device">
        <View style={styles.group}>
          <Row icon="notifications-none" title="Check-in reminders" subtitle="Daily diary and weekly check reminders." right={<Badge label="Coming soon" />} />
          <Row icon="replay" title="Show welcome screens again" onPress={() => router.push('/welcome')} last />
        </View>
        {participants ? (
          <Details label="Participant IDs">
            <KeyValue rows={[['Demo (facial, risk, activities)', participants.synthetic], ['Demo voice (public audio)', participants.publicAudio], ['Real capture', participants.local ?? 'not enabled']]} />
          </Details>
        ) : null}
      </Section>

      <Pressable onPress={reset} style={styles.resetButton} accessibilityRole="button">
        <MaterialIcons name="logout" size={20} color={colors.text} />
        <Text style={styles.resetText}>Reset this app</Text>
      </Pressable>

      <Notice icon="info-outline" tone="cyan">Research prototype. Results are measurements, not a burnout, stress or clinical assessment.</Notice>

      {/* App version from app.json; backend API version from /health when connected. */}
      <Text style={styles.version}>
        {`EMPath+ v${Constants.expoConfig?.version ?? '—'}${health?.api_version ? ` · Backend API v${health.api_version}` : ''}`}
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', gap: space.sm, paddingVertical: space.sm },
  avatarRing: { width: 112, height: 112, borderRadius: 56, alignItems: 'center', justifyContent: 'center' },
  avatar: { width: 104, height: 104, borderRadius: 52, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center' },
  avatarText: { fontFamily: fonts.semibold, fontSize: 36, color: colors.primary },
  name: { fontFamily: fonts.semibold, fontSize: 24, color: colors.text },
  editName: { fontFamily: fonts.label, fontSize: 14, color: colors.primary },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.base, justifyContent: 'center' },
  tag: { backgroundColor: colors.chipBg, borderRadius: radius.chip, paddingHorizontal: space.sm, paddingVertical: 5 },
  tagText: { fontFamily: fonts.label, fontSize: 13, color: colors.primary },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  option: { flexDirection: 'row', alignItems: 'center', gap: space.sm, backgroundColor: colors.card, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border, padding: space.md },
  optionSelected: { borderColor: colors.indigo, backgroundColor: 'rgba(99,102,241,0.08)' },
  optionTitle: { ...type.body, fontFamily: fonts.semibold, color: colors.text },
  optionText: { ...type.caption, color: colors.textMuted },
  group: { backgroundColor: colors.card, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingHorizontal: space.md, paddingVertical: space.sm, minHeight: 60 },
  rowDivider: { borderBottomWidth: 1, borderBottomColor: colors.border },
  rowTitle: { fontFamily: fonts.regular, fontSize: 16, color: colors.text },
  rowSub: { ...type.caption, color: colors.textMuted },
  rowValue: { fontFamily: fonts.label, fontSize: 12, color: colors.textFaint, maxWidth: 110, textAlign: 'right' },
  sectionLabel: { ...type.label, color: colors.textMuted },
  resetButton: { alignSelf: 'center', flexDirection: 'row', alignItems: 'center', gap: space.base, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radius.chip, paddingHorizontal: space.lg, minHeight: 48 },
  resetText: { fontFamily: fonts.semibold, fontSize: 16, color: colors.text },
  version: { fontFamily: fonts.label, fontSize: 12, color: colors.textFaint, textAlign: 'center' },
});
