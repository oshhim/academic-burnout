import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Defs, Pattern, RadialGradient, Rect, Stop } from 'react-native-svg';

import { colors } from '@/theme';

/**
 * "Digital Sanctuary" backdrop for the launch screen: a faint dot grid with a soft
 * indigo glow behind the illustration. Vector, so it is sharp on every screen and
 * adds nothing to the bundle size. Decorative only (hidden from accessibility).
 */
export function SanctuaryBackground({ glowY = 0.38 }: { glowY?: number }) {
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width="100%" height="100%">
        <Defs>
          <Pattern id="dots" width={22} height={22} patternUnits="userSpaceOnUse">
            <Circle cx={2} cy={2} r={1.1} fill={colors.textMuted} fillOpacity={0.12} />
          </Pattern>
          <RadialGradient id="glow" cx="50%" cy={`${glowY * 100}%`} rx="60%" ry="40%" fx="50%" fy={`${glowY * 100}%`}>
            <Stop offset="0" stopColor={colors.indigo} stopOpacity={0.24} />
            <Stop offset="1" stopColor={colors.indigo} stopOpacity={0} />
          </RadialGradient>
        </Defs>
        <Rect width="100%" height="100%" fill="url(#dots)" />
        <Rect width="100%" height="100%" fill="url(#glow)" />
      </Svg>
    </View>
  );
}
