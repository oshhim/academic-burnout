import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ModeBadge } from '@/components/mode-badge';
import { Badge, Body, Button, Card, Details, ErrorBox, Field, IconWell, KeyValue, Notice, Screen, Section, Title, Toggle, type IconName } from '@/components/ui';
import { getPublic } from '@/lib/api';
import { useSession, type Mode } from '@/lib/session';
import { useAction } from '@/lib/use-action';
import { colors, fonts, radius, space, type } from '@/theme';

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

export default function SetupScreen() {
  const { connection, setConnection, participants, register, resetParticipants, mode, setMode, enableReal } = useSession();
  const [baseUrl, setBaseUrl] = useState(connection.baseUrl);
  const [apiKey, setApiKey] = useState(connection.apiKey);
  const [editing, setEditing] = useState(participants === null);
  const [consent, setConsent] = useState(false);
  const [realConsent, setRealConsent] = useState(false);
  const [health, setHealth] = useState<any>(null);
  const { busy, error, run } = useAction();

  const checkHealth = useCallback(async () => setHealth(await getPublic(connection, '/health')), [connection]);

  useEffect(() => {
    if (participants) run('health', checkHealth);
  }, [participants, checkHealth, run]);

  const connect = () =>
    run('connect', async () => {
      const result = await register({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() });
      setHealth(result.health);
      setEditing(false);
    });

  const chooseMode = (next: Mode) => {
    if (next === 'demo' || participants?.local) setMode(next);
  };

  const connected = participants !== null && !editing;

  return (
    <Screen title="Setup" badge={<ModeBadge />} subtitle={connected ? undefined : 'Connect this phone to the EMPath+ backend running on your laptop.'}>
      <Section label="Connection">
        {connected ? (
          <Card>
            <View style={styles.statusRow}>
              <IconWell icon={health ? 'cloud-done' : 'cloud-queue'} color={health ? colors.tertiary : colors.textFaint} />
              <View style={{ flex: 1 }}>
                <Title>{health ? 'Connected' : busy === 'health' ? 'Checking…' : 'Connection saved'}</Title>
                <Body small muted>{connection.baseUrl}</Body>
              </View>
              <Button label="Edit" variant="text" onPress={() => setEditing(true)} />
            </View>
            {health ? (
              <View style={styles.badges}>
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
              <View style={styles.actions}>
                <Button label="Save" onPress={() => { setConnection({ baseUrl: baseUrl.trim(), apiKey: apiKey.trim() }); setEditing(false); }} />
                <Button label="Cancel" variant="secondary" onPress={() => { setBaseUrl(connection.baseUrl); setApiKey(connection.apiKey); setEditing(false); }} />
              </View>
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
          <ModeOption
            icon="videocam"
            title="Real capture"
            text={participants.local ? 'Your camera, microphone and own entries.' : 'Needs your consent below.'}
            selected={mode === 'real'}
            onPress={() => chooseMode('real')}
          />
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
          <Notice icon="shield">Real capture needs ENABLE_RESEARCH_MODE=true in backend/.env. Test only with your own face and voice; that setting is not ethics approval.</Notice>
        </Section>
      ) : null}

      {participants ? (
        <Details label="Participants and reset">
          <KeyValue
            rows={[
              ['Demo (facial, risk, activities)', participants.synthetic],
              ['Demo voice (public audio)', participants.publicAudio],
              ['Real capture', participants.local ?? 'not enabled'],
            ]}
          />
          <Button label="Start over with new participants" variant="secondary" icon="restart-alt" onPress={() => { resetParticipants(); setHealth(null); setConsent(false); setRealConsent(false); setEditing(true); }} />
        </Details>
      ) : null}

      <Notice icon="info-outline" tone="cyan">Research prototype. Results are measurements, not a burnout, stress or clinical assessment.</Notice>
    </Screen>
  );
}

const styles = StyleSheet.create({
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: space.base },
  actions: { gap: space.sm },
  option: { flexDirection: 'row', alignItems: 'center', gap: space.sm, backgroundColor: colors.card, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border, padding: space.md },
  optionSelected: { borderColor: colors.indigo, backgroundColor: 'rgba(99,102,241,0.08)' },
  optionTitle: { ...type.body, fontFamily: fonts.semibold, color: colors.text },
  optionText: { ...type.caption, color: colors.textMuted },
});
