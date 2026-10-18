import { useMemo } from 'react';
import { SvgXml } from 'react-native-svg';

import { gradientMarkSvg, markSvg } from '@/brand/logo';

/**
 * EMPath+ logo: transparent vector mark (sharp at any size). Brand gradient by
 * default; pass `color` for a calm single-colour version.
 */
export function Logo({ size = 40, color }: { size?: number; color?: string }) {
  const xml = useMemo(() => (color ? markSvg(color, { size, scale: 1.12 }) : gradientMarkSvg({ size, scale: 1.12 })), [size, color]);
  return <SvgXml xml={xml} width={size} height={size} accessibilityLabel="EMPath+" />;
}
