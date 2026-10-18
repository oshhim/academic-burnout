import { StyleSheet, View } from 'react-native';
import Svg, { Defs, Ellipse, RadialGradient, Stop } from 'react-native-svg';

import { colors } from '@/theme';

// Aurora backdrop for the launch screen: two soft, out-of-focus pools of light at
// the top (indigo top-right, faint cyan top-left) that fade to the dark base well
// before the text. Built from radial gradients, which look like blur and are cheap
// to render on phones. Decorative only (hidden from accessibility).

const W = 390;
const H = 844;

export function AuroraBackground({ intensity = 1 }: { intensity?: number }) {
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Svg width="100%" height="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMin slice">
        <Defs>
          <RadialGradient id="indigo" cx="50%" cy="50%" r="50%">
            <Stop offset="0" stopColor={colors.indigo} stopOpacity={0.3 * intensity} />
            <Stop offset="0.55" stopColor={colors.indigo} stopOpacity={0.1 * intensity} />
            <Stop offset="1" stopColor={colors.indigo} stopOpacity={0} />
          </RadialGradient>
          <RadialGradient id="cyan" cx="50%" cy="50%" r="50%">
            <Stop offset="0" stopColor={colors.tertiary} stopOpacity={0.14 * intensity} />
            <Stop offset="1" stopColor={colors.tertiary} stopOpacity={0} />
          </RadialGradient>
        </Defs>
        <Ellipse cx={W * 0.78} cy={H * 0.05} rx={W * 0.75} ry={H * 0.32} fill="url(#indigo)" />
        <Ellipse cx={W * 0.05} cy={H * 0.2} rx={W * 0.55} ry={H * 0.2} fill="url(#cyan)" />
      </Svg>
    </View>
  );
}
