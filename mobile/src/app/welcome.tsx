import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { router } from 'expo-router';
import { useRef, useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Svg, { Defs, LinearGradient as SvgGradient, Path, Stop } from 'react-native-svg';

import { Logo } from '@/components/logo';
import { SanctuaryBackground } from '@/components/sanctuary-background';
import { Button } from '@/components/ui';
import { useSession } from '@/lib/session';
import { colors, fonts, radius, space, type } from '@/theme';

// Launch screen, modelled on the onboarding designs (logo header, Skip, illustration,
// headline, body, page dots, gradient Continue). Copy stays within what the app actually does.

function LogoHero() {
  return (
    // Simple single-colour mark; the soft glow now comes from the background.
    <View style={styles.heroWrap}>
      <Logo size={170} color={colors.primary} />
    </View>
  );
}

function CheckInsArt() {
  return (
    <View style={styles.artRow}>
      <View style={styles.artCard}>
        {[styles.cTL, styles.cTR, styles.cBL, styles.cBR].map((corner, i) => (
          <View key={i} style={[styles.corner, corner]} />
        ))}
        <View style={styles.artIcon}>
          <MaterialIcons name="face" size={36} color={colors.primary} />
        </View>
        <Text style={styles.artLabel}>FACIAL</Text>
      </View>
      <View style={styles.artCard}>
        <View style={styles.wave}>
          {[14, 30, 46, 26, 52, 34, 18, 40, 22].map((h, i) => (
            <View key={i} style={[styles.waveBar, { height: h, backgroundColor: i % 2 ? colors.secondary : colors.tertiary }]} />
          ))}
        </View>
        <Text style={styles.artLabel}>VOICE</Text>
      </View>
    </View>
  );
}

function TrendArt({ width }: { width: number }) {
  const w = width - space.gutter * 2 - 2;
  const h = 200;
  return (
    <View style={[styles.chartCard, { height: h + 2 }]}>
      <Svg width={w} height={h}>
        <Defs>
          <SvgGradient id="fill" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={colors.primary} stopOpacity="0.28" />
            <Stop offset="1" stopColor={colors.primary} stopOpacity="0" />
          </SvgGradient>
        </Defs>
        <Path d={`M0 ${h * 0.8} C ${w * 0.35} ${h * 0.82}, ${w * 0.5} ${h * 0.2}, ${w} ${h * 0.18} L ${w} ${h} L 0 ${h} Z`} fill="url(#fill)" />
        <Path d={`M0 ${h * 0.8} C ${w * 0.35} ${h * 0.82}, ${w * 0.5} ${h * 0.2}, ${w} ${h * 0.18}`} stroke={colors.primary} strokeWidth={3} fill="none" />
        <Path d={`M0 ${h * 0.3} C ${w * 0.3} ${h * 0.28}, ${w * 0.55} ${h * 0.9}, ${w} ${h * 0.86}`} stroke={colors.secondary} strokeWidth={2} strokeDasharray="6 6" fill="none" />
      </Svg>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendLine, { backgroundColor: colors.primary }]} />
          <Text style={styles.legendText}>Fatigue</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendLine, { backgroundColor: colors.secondary, opacity: 0.7 }]} />
          <Text style={styles.legendText}>Sleep</Text>
        </View>
      </View>
    </View>
  );
}

function ActivitiesArt() {
  const items = [
    { title: 'A quiet pause', meta: '2 min · Pause', icon: 'pause-circle-outline' as const, top: true },
    { title: 'Step away from the screen', meta: '2 min · Pause', icon: 'visibility-off' as const },
    { title: 'Choose one small next step', meta: '3 min · Planning', icon: 'checklist' as const },
  ];
  return (
    <View style={{ gap: space.sm, width: '100%' }}>
      {items.map((item) => (
        <View key={item.title} style={[styles.miniCard, item.top && styles.miniTop]}>
          <View style={styles.miniIcon}>
            <MaterialIcons name={item.icon} size={20} color={item.top ? colors.secondary : colors.tertiary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.miniTitle}>{item.title}</Text>
            <Text style={styles.miniMeta}>{item.meta}</Text>
          </View>
          {item.top ? <Text style={styles.topPick}>TOP PICK</Text> : null}
        </View>
      ))}
    </View>
  );
}

type Slide = { key: string; art: (width: number) => ReactNode; title: string; body: string };

const SLIDES: Slide[] = [
  {
    key: 'welcome',
    art: () => <LogoHero />,
    title: 'Understand how you’re doing. Work better. Feel better.',
    body: 'EMPath+ is a research prototype for university students: short check-ins, a study diary and small breaks, with your data kept private.',
  },
  {
    key: 'checkins',
    art: () => <CheckInsArt />,
    title: 'Quick check-ins',
    body: 'A short camera or voice check-in compares you with your own normal. Facial video never leaves your phone; only measurements are sent.',
  },
  {
    key: 'patterns',
    art: (width) => <TrendArt width={width} />,
    title: 'Spot patterns early',
    body: 'A one-minute daily diary and a weekly check show how your sleep, study load and fatigue change. Forecasts are research estimates, not a diagnosis.',
  },
  {
    key: 'breaks',
    art: () => <ActivitiesArt />,
    title: 'Small breaks that fit',
    body: 'Get short, optional activities that match your goal and the time you have. Your ratings make the next suggestions better.',
  },
];

export default function WelcomeScreen() {
  const { width } = useWindowDimensions();
  const { setOnboarded, participants } = useSession();
  const scroller = useRef<ScrollView>(null);
  const [index, setIndex] = useState(0);
  // Horizontal pages don't stretch vertically; measure the pager so each slide can centre itself.
  const [pageHeight, setPageHeight] = useState(0);
  const last = index === SLIDES.length - 1;

  const finish = () => {
    setOnboarded(true);
    router.replace(participants ? '/facial' : '/profile');
  };

  const next = () => {
    if (last) return finish();
    scroller.current?.scrollTo({ x: width * (index + 1), animated: true });
    setIndex(index + 1);
  };

  const onScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => setIndex(Math.round(e.nativeEvent.contentOffset.x / width));

  return (
    <SafeAreaView style={styles.screen}>
      <SanctuaryBackground />
      <View style={styles.header}>
        <Logo size={40} />
        <Text style={styles.brand}>EMPath+</Text>
        {!last ? (
          <Pressable onPress={finish} hitSlop={12} accessibilityRole="button">
            <Text style={styles.skip}>Skip</Text>
          </Pressable>
        ) : null}
      </View>

      <ScrollView ref={scroller} horizontal pagingEnabled showsHorizontalScrollIndicator={false} onMomentumScrollEnd={onScrollEnd} style={{ flex: 1 }} onLayout={(e) => setPageHeight(e.nativeEvent.layout.height)}>
        {SLIDES.map((slide) => (
          <View key={slide.key} style={[styles.slide, { width, height: pageHeight || undefined }]}>
            <View style={styles.artArea}>{slide.art(width)}</View>
            <Text style={styles.title}>{slide.title}</Text>
            <Text style={styles.body}>{slide.body}</Text>
          </View>
        ))}
      </ScrollView>

      <View style={styles.footer}>
        <View style={styles.dots}>
          {SLIDES.map((s, i) => (
            <View key={s.key} style={[styles.dot, i === index && styles.dotActive]} />
          ))}
        </View>
        <Button label={last ? 'Get started' : 'Continue'} icon={last ? 'arrow-forward' : undefined} onPress={next} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.base },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingHorizontal: space.gutter, paddingVertical: space.base },
  brand: { ...type.title, color: colors.text, flex: 1 },
  skip: { fontFamily: fonts.label, fontSize: 15, color: colors.textMuted },
  slide: { paddingHorizontal: space.gutter, justifyContent: 'center', gap: space.md },
  artArea: { minHeight: 260, alignItems: 'center', justifyContent: 'center', marginBottom: space.base },
  title: { fontFamily: fonts.bold, fontSize: 28, lineHeight: 34, color: colors.text, textAlign: 'center', letterSpacing: -0.3 },
  body: { ...type.body, color: colors.textMuted, textAlign: 'center' },
  footer: { paddingHorizontal: space.gutter, paddingBottom: space.md, gap: space.lg },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: space.base },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.raised },
  dotActive: { width: 24, backgroundColor: colors.primary },
  heroWrap: { width: 240, height: 240, alignItems: 'center', justifyContent: 'center' },
  artRow: { flexDirection: 'row', gap: space.md },
  artCard: { width: 150, height: 190, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, alignItems: 'center', justifyContent: 'center', gap: space.md },
  artIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center' },
  artLabel: { ...type.label, color: colors.textMuted },
  corner: { position: 'absolute', width: 22, height: 22, borderColor: colors.primary },
  cTL: { top: 14, left: 14, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 10 },
  cTR: { top: 14, right: 14, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 10 },
  cBL: { bottom: 14, left: 14, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 10 },
  cBR: { bottom: 14, right: 14, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 10 },
  wave: { flexDirection: 'row', alignItems: 'center', gap: 5, height: 64 },
  waveBar: { width: 6, borderRadius: 3 },
  chartCard: { width: '100%', borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, overflow: 'hidden', justifyContent: 'flex-end' },
  legend: { position: 'absolute', left: space.md, bottom: space.md, flexDirection: 'row', gap: space.md },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendLine: { width: 16, height: 3, borderRadius: 2 },
  legendText: { ...type.caption, color: colors.textMuted },
  miniCard: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md, borderRadius: radius.card, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border },
  miniTop: { backgroundColor: 'rgba(168,85,247,0.14)', borderColor: 'rgba(168,85,247,0.35)' },
  miniIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center' },
  miniTitle: { fontFamily: fonts.semibold, fontSize: 15, color: colors.text },
  miniMeta: { ...type.caption, color: colors.textMuted },
  topPick: { fontFamily: fonts.label, fontSize: 11, color: colors.secondary, letterSpacing: 0.6 },
});
