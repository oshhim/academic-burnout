import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { ActivityIndicator, PermissionsAndroid, Platform, StyleSheet, View } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

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

  // On Android the WebView only gets the camera/microphone if the app (Expo Go) already
  // holds the Android permission; without it the page's request hangs silently. Ask first.
  const [allowed, setAllowed] = useState(Platform.OS !== 'android');
  // Callers pass a new onError on every render; keep the latest without asking again.
  const onErrorRef = useRef(props.onError);
  useEffect(() => {
    onErrorRef.current = props.onError;
  });
  useEffect(() => {
    if (Platform.OS !== 'android') return;
    const permission = isFace ? PermissionsAndroid.PERMISSIONS.CAMERA : PermissionsAndroid.PERMISSIONS.RECORD_AUDIO;
    const what = isFace ? 'Camera' : 'Microphone';
    let done = false;
    const finish = (granted: boolean) => {
      if (done) return;
      done = true;
      clearInterval(poll);
      if (granted) setAllowed(true);
      else onErrorRef.current(`${what} access was refused. Allow it in Android Settings → Apps → Expo Go → Permissions (choose "Allow", not "Ask every time"), then try again.`);
    };
    // Expo Go handles permission results itself, so request() may never resolve after the
    // user taps Allow. Poll the actual permission state too and continue as soon as it is granted.
    const poll = setInterval(() => {
      PermissionsAndroid.check(permission).then((granted) => granted && finish(true));
    }, 500);
    PermissionsAndroid.request(permission).then((result) => finish(result === PermissionsAndroid.RESULTS.GRANTED));
    return () => {
      done = true;
      clearInterval(poll);
    };
  }, [isFace]);

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
  waiting: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
