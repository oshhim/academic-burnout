import { useMemo } from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';

import { facePage, voicePage, type FaceProtocol } from '@/lib/capture/pages';
import { colors, radius } from '@/theme';

export type FaceResult = { recordedAt: string; frames: number; windows: any[] };
export type VoiceResult = { base64: string; sampleRate: number; durationSec: number; recordedAt: string };

type Props =
  | { kind: 'face'; protocol: FaceProtocol; onFace: (r: FaceResult) => void; onCancel: () => void; onError: (message: string) => void }
  | { kind: 'voice'; onVoice: (r: VoiceResult) => void; onError: (message: string) => void };

/**
 * Hosts a capture page in a WebView. The https baseUrl gives the page a secure
 * context, which browsers require before granting camera or microphone access.
 */
export function CaptureView(props: Props) {
  const isFace = props.kind === 'face';
  // The face page fills most of the screen below the header; the voice recorder is compact.
  const { height: windowHeight } = useWindowDimensions();
  const height = isFace ? Math.max(440, windowHeight - 330) : 230;
  const protocol = isFace ? props.protocol : null;
  const html = useMemo(() => (protocol ? facePage(protocol) : voicePage()), [protocol]);

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
  };

  return (
    <View style={[styles.frame, isFace && styles.bare, { height }]}>
      <WebView
        source={{ html, baseUrl: 'https://localhost' }}
        originWhitelist={['*']}
        onMessage={onMessage}
        javaScriptEnabled
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
        mediaCapturePermissionGrantType="grant"
        style={styles.webview}
        onError={(e) => props.onError(e.nativeEvent.description)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { borderRadius: radius.card, overflow: 'hidden', borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  bare: { borderWidth: 0, backgroundColor: colors.base, borderRadius: 0 },
  webview: { flex: 1, backgroundColor: 'transparent' },
});
