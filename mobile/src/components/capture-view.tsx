import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Camera } from 'expo-camera';
import { ActivityIndicator, Linking, Platform, StyleSheet, View } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Body, Button } from '@/components/ui';
import { facePage, voicePage, type FaceProtocol } from '@/lib/capture/pages';
import { colors } from '@/theme';

export type FaceResult = { recordedAt: string; frames: number; windows: any[] };
export type VoiceResult = { base64: string; sampleRate: number; durationSec: number; recordedAt: string };

type Props =
  | { kind: 'face'; protocol: FaceProtocol; onFace: (r: FaceResult) => void; onCancel: () => void; onError: (message: string) => void }
  | {
      kind: 'voice';
      onVoice: (r: VoiceResult) => void;
      onError: (message: string) => void;
      /** Page actions after a result: 'reset' (record again), 'retry' (upload again), 'details'. */
      onEvent?: (type: 'reset' | 'retry' | 'details') => void;
      /** Lets the screen send the result into the page (window.__result). */
      webRef?: RefObject<WebView | null>;
    };

/**
 * Hosts a capture page in a WebView. The https baseUrl gives the page a secure
 * context, which browsers require before granting camera or microphone access.
 */
export function CaptureView(props: Props) {
  const isFace = props.kind === 'face';
  // The face page is full screen (its controls sit inside the safe areas); the voice recorder fills
  // the Voice tab below its header, so it needs no insets.
  const { top, bottom } = useSafeAreaInsets();
  const protocol = isFace ? props.protocol : null;
  const html = useMemo(() => (protocol ? facePage(protocol, { top, bottom }) : voicePage()), [protocol, top, bottom]);

  // On Android the WebView only gets the camera/microphone once the app holds the permission. In Expo Go
  // that must be granted through Expo's own permission system (Android's PermissionsAndroid is not
  // enough: the page's request then waits forever), so ask with expo-camera before mounting the page.
  const [allowed, setAllowed] = useState(Platform.OS !== 'android');
  // Shown in place of the page when access is refused (the Voice page cannot show errors before it exists).
  const [refused, setRefused] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  // Callers pass a new onError on every render; keep the latest without asking again.
  const onErrorRef = useRef(props.onError);
  useEffect(() => {
    onErrorRef.current = props.onError;
  });
  useEffect(() => {
    if (Platform.OS !== 'android') return;
    let active = true;
    const what = isFace ? 'Camera' : 'Microphone';
    (isFace ? Camera.requestCameraPermissionsAsync() : Camera.requestMicrophonePermissionsAsync())
      .then((result) => {
        if (!active) return;
        if (result.granted) return setAllowed(true);
        const message = `${what} access was refused. Allow it in Android Settings → Apps → Expo Go → Permissions, then try again.`;
        setRefused(message);
        onErrorRef.current(message);
      })
      .catch((e) => {
        if (!active) return;
        const message = `${what} permission could not be requested: ${e?.message ?? e}`;
        setRefused(message);
        onErrorRef.current(message);
      });
    return () => {
      active = false;
    };
  }, [isFace, attempt]);

  const onMessage = (event: WebViewMessageEvent) => {
    let message: any;
    try {
      message = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }
    if (message.type === 'error') props.onError(message.message);
    else if (message.type === 'face' && props.kind === 'face') props.onFace(message);
    else if (message.type === 'cancel' && props.kind === 'face') props.onCancel();
    else if (message.type === 'audio' && props.kind === 'voice') props.onVoice(message);
    else if ((message.type === 'reset' || message.type === 'retry' || message.type === 'details') && props.kind === 'voice') props.onEvent?.(message.type);
  };

  return (
    <View style={isFace ? styles.full : styles.voice}>
      {allowed ? (
        <WebView
          ref={props.kind === 'voice' ? props.webRef : undefined}
          source={{ html, baseUrl: 'https://localhost' }}
          originWhitelist={['*']}
          onMessage={onMessage}
          javaScriptEnabled
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          mediaCapturePermissionGrantType="grant"
          // The face page handles the safe areas itself. Without these, iOS adds its own insets
          // after the first paint, and the full-screen camera visibly rescales ("zooms") to fit.
          contentInsetAdjustmentBehavior="never"
          automaticallyAdjustContentInsets={false}
          scrollEnabled={false}
          bounces={false}
          // Android WebViews otherwise scale page text by the system font size, breaking the layout.
          textZoom={100}
          style={styles.webview}
          onError={(e) => props.onError(e.nativeEvent.description)}
        />
      ) : refused ? (
        <View style={styles.waiting}>
          <Body muted center>{refused}</Body>
          <Button
            label="Try again"
            icon="refresh"
            onPress={() => {
              setRefused(null);
              setAttempt((n) => n + 1);
            }}
          />
          <Button label="Open settings" icon="settings" variant="secondary" onPress={() => Linking.openSettings()} />
        </View>
      ) : (
        <View style={styles.waiting}>
          <ActivityIndicator color={colors.primary} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  full: { flex: 1, backgroundColor: '#000' },
  voice: { flex: 1 },
  webview: { flex: 1, backgroundColor: 'transparent' },
  waiting: { flex: 1, alignItems: 'stretch', justifyContent: 'center', gap: 12, padding: 24 },
});
