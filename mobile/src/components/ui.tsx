import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { LinearGradient } from 'expo-linear-gradient';
import { useState, type ComponentProps, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View, type TextInputProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '@/lib/api';

import { Logo } from './logo';
import { colors, fonts, gradient, radius, space, type } from '@/theme';

export type IconName = ComponentProps<typeof MaterialIcons>['name'];

// ---------- Layout ----------

/** Screen shell: branded header (logo tile + title), optional subtitle, scrolling body. */
export function Screen({ title, subtitle, badge, children }: { title: string; subtitle?: string; badge?: ReactNode; children: ReactNode }) {
  return (
    <SafeAreaView style={styles.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Logo size={40} />
          <Text style={styles.headerTitle} numberOfLines={1}>
            {title}
          </Text>
          {badge}
        </View>
        {subtitle ? <Text style={[styles.body, styles.muted]}>{subtitle}</Text> : null}
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

/** Uppercase label above a group, as in the reference designs ("PRODUCTIVITY", "ASSESSMENT SETTINGS"). */
export function Section({ label, step, done, children }: { label: string; step?: number; done?: boolean; children: ReactNode }) {
  return (
    <View style={styles.section}>
      <View style={styles.sectionHead}>
        {step !== undefined ? (
          <View style={[styles.stepDot, done && styles.stepDotDone]}>
            {done ? <MaterialIcons name="check" size={14} color={colors.base} /> : <Text style={styles.stepText}>{step}</Text>}
          </View>
        ) : null}
        <Text style={styles.sectionLabel}>{label.toUpperCase()}</Text>
      </View>
      {children}
    </View>
  );
}

/** Luminous card: #12161F, 1px hairline border, faint top highlight. */
export function Card({ children, accent, tint }: { children: ReactNode; accent?: string; tint?: 'violet' }) {
  return (
    <View style={[styles.card, accent ? { borderColor: accent } : null]}>
      <LinearGradient
        colors={tint === 'violet' ? ['rgba(168,85,247,0.22)', 'rgba(99,102,241,0.06)'] : ['rgba(255,255,255,0.04)', 'transparent']}
        style={StyleSheet.absoluteFill}
        pointerEvents="none"
      />
      {children}
    </View>
  );
}

// ---------- Text ----------

export function Body({ children, muted, small, center }: { children: ReactNode; muted?: boolean; small?: boolean; center?: boolean }) {
  return <Text style={[small ? styles.caption : styles.body, muted && styles.muted, center && { textAlign: 'center' }]}>{children}</Text>;
}

export function Title({ children, center }: { children: ReactNode; center?: boolean }) {
  return <Text style={[styles.title, center && { textAlign: 'center' }]}>{children}</Text>;
}

export function Label({ children }: { children: ReactNode }) {
  return <Text style={styles.fieldLabel}>{children}</Text>;
}

// ---------- Controls ----------

export function Button({ label, onPress, loading, disabled, variant = 'primary', icon }: {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'text';
  icon?: IconName;
}) {
  const inactive = disabled || loading;
  const textColor = variant === 'text' ? colors.tertiary : '#fff';
  const content = loading ? (
    <ActivityIndicator color={textColor} />
  ) : (
    <View style={styles.buttonRow}>
      {icon ? <MaterialIcons name={icon} size={20} color={textColor} /> : null}
      <Text style={[styles.buttonText, { color: textColor }]}>{label}</Text>
    </View>
  );
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      style={({ pressed }) => [{ opacity: disabled ? 0.4 : pressed ? 0.85 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] }, variant === 'primary' && !disabled && styles.glow]}>
      {variant === 'primary' ? (
        <LinearGradient colors={gradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.button}>
          {content}
        </LinearGradient>
      ) : (
        <View style={[styles.button, variant === 'secondary' ? styles.secondary : styles.textButton]}>{content}</View>
      )}
    </Pressable>
  );
}

export function Chips<T extends string | number>({ options, value, onChange, format, icons }: {
  options: readonly T[];
  value: T | null;
  onChange: (v: T) => void;
  format?: (v: T) => string;
  icons?: Partial<Record<string, IconName>>;
}) {
  return (
    <View style={styles.row}>
      {options.map((option) => {
        const active = option === value;
        const icon = icons?.[String(option)];
        return (
          <Pressable
            key={String(option)}
            onPress={() => onChange(option)}
            style={[styles.chip, active && styles.chipActive]}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}>
            {icon ? <MaterialIcons name={icon} size={16} color={active ? colors.primary : colors.textFaint} /> : null}
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{format ? format(option) : String(option)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/** 1–5 scale with end anchors. Optional ratings clear when the selected value is tapped again. */
export function Rating({ label, value, onChange, required, low = 'Low', high = 'High' }: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  required?: boolean;
  low?: string;
  high?: string;
}) {
  return (
    <View style={styles.field}>
      <View style={styles.ratingHead}>
        <Text style={styles.fieldLabel}>{label}</Text>
        {!required ? <Text style={[styles.caption, styles.faint]}>optional</Text> : null}
      </View>
      <View style={styles.scale}>
        {[1, 2, 3, 4, 5].map((n) => {
          const active = n === value;
          return (
            <Pressable
              key={n}
              onPress={() => onChange(active && !required ? null : n)}
              style={[styles.scaleItem, active && styles.chipActive]}
              accessibilityRole="radio"
              accessibilityLabel={`${label} ${n} of 5`}
              accessibilityState={{ selected: active }}>
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{n}</Text>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.anchors}>
        <Text style={[styles.caption, styles.faint]}>{low}</Text>
        <Text style={[styles.caption, styles.faint]}>{high}</Text>
      </View>
    </View>
  );
}

export function Field({ label, hint, unit, ...props }: TextInputProps & { label: string; hint?: string; unit?: string }) {
  // Deliberately stateless: re-rendering the box on focus (e.g. a focus glow) made the
  // iOS keyboard open and immediately close. Fixed height, no lineHeight, for the same reason.
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={styles.inputBox}>
        <TextInput
          placeholderTextColor={colors.textFaint}
          selectionColor={colors.indigo}
          autoCapitalize="none"
          autoCorrect={false}
          style={[styles.input, unit ? { paddingRight: 44 } : null]}
          accessibilityLabel={label}
          {...props}
        />
        {unit ? (
          <Text style={[styles.caption, styles.faint, styles.unit]} pointerEvents="none">
            {unit}
          </Text>
        ) : null}
      </View>
      {hint ? <Text style={[styles.caption, styles.muted]}>{hint}</Text> : null}
    </View>
  );
}

/** Settings-style row: icon well, title + description, switch (as in the Profile design). */
export function Toggle({ label, description, icon, value, onChange }: { label: string; description?: string; icon?: IconName; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <Pressable onPress={() => onChange(!value)} style={styles.toggle} accessibilityRole="switch" accessibilityState={{ checked: value }} accessibilityLabel={label}>
      {icon ? <IconWell icon={icon} /> : null}
      <View style={styles.toggleText}>
        <Text style={styles.toggleLabel}>{label}</Text>
        {description ? <Text style={[styles.caption, styles.muted]}>{description}</Text> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ true: colors.indigo, false: colors.raised }}
        ios_backgroundColor={colors.raised}
        thumbColor="#fff"
        style={styles.switch}
      />
    </Pressable>
  );
}

export function IconWell({ icon, color = colors.primary, size = 40 }: { icon: IconName; color?: string; size?: number }) {
  return (
    <View style={[styles.iconWell, { width: size, height: size, borderRadius: size / 2 }]}>
      <MaterialIcons name={icon} size={size * 0.5} color={color} />
    </View>
  );
}

// ---------- Status & results ----------

export function Badge({ label, tone = 'primary' }: { label: string; tone?: 'primary' | 'success' | 'warn' | 'error' }) {
  const color = { primary: colors.primary, success: colors.tertiary, warn: colors.secondary, error: colors.error }[tone];
  return (
    <View style={[styles.badge, { backgroundColor: `${color}1F` }]}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

/** "Your Results" hero from the check-in results design: icon, state label, big value, meter, explanation. */
export function ResultHero({ icon, label, value, tone = 'primary', meter, meterLabel, explanation }: {
  icon: IconName;
  label: string;
  value: string;
  tone?: 'primary' | 'success' | 'warn' | 'error';
  meter?: number; // 0..1
  meterLabel?: string;
  explanation?: string;
}) {
  const color = { primary: colors.primary, success: colors.tertiary, warn: colors.secondary, error: colors.error }[tone];
  return (
    <Card>
      <View style={{ alignItems: 'center', gap: space.sm }}>
        <IconWell icon={icon} color={color} size={64} />
        <Text style={styles.sectionLabel}>{label.toUpperCase()}</Text>
        <Text style={[styles.heroValue, { color: colors.text }]}>{value}</Text>
      </View>
      {meter !== undefined ? (
        <View style={{ gap: space.xs }}>
          {meterLabel ? <Text style={[styles.caption, { color, textAlign: 'right' }]}>{meterLabel}</Text> : null}
          <View style={styles.meter}>
            <LinearGradient colors={[colors.tertiary, colors.error]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={[styles.meterFill, { width: `${Math.max(4, Math.min(100, meter * 100))}%` }]} />
          </View>
        </View>
      ) : null}
      {explanation ? (
        <View style={styles.inset}>
          <Text style={styles.body}>{explanation}</Text>
        </View>
      ) : null}
    </Card>
  );
}

export function KeyValue({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <View style={{ gap: space.base }}>
      {rows.map(([k, v]) => (
        <View key={k} style={styles.kv}>
          <Text style={[styles.caption, styles.muted, { flex: 1 }]}>{k}</Text>
          {typeof v === 'string' || typeof v === 'number' || v === null || v === undefined ? (
            <Text style={[styles.caption, styles.kvValue]} selectable>
              {v ?? '—'}
            </Text>
          ) : (
            v
          )}
        </View>
      ))}
    </View>
  );
}

/** Collapsible block for technical detail (IDs, versions, raw scores) that most people don't need. */
export function Details({ label = 'Technical details', children }: { label?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <View>
      <Pressable onPress={() => setOpen(!open)} style={styles.detailsHead} accessibilityRole="button" accessibilityState={{ expanded: open }}>
        <Text style={[styles.caption, { color: colors.primary }]}>{label}</Text>
        <MaterialIcons name={open ? 'expand-less' : 'expand-more'} size={18} color={colors.primary} />
      </Pressable>
      {open ? <View style={{ gap: space.sm, paddingTop: space.sm }}>{children}</View> : null}
    </View>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error instanceof ApiError ? error : null;
  return (
    <View style={styles.error} accessibilityRole="alert">
      <MaterialIcons name="error-outline" size={20} color={colors.error} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[styles.caption, { color: colors.error, fontFamily: fonts.semibold }]}>{e ? (e.status ? `Request failed (${e.status})` : 'Cannot reach the backend') : 'Something went wrong'}</Text>
        <Text style={[styles.caption, { color: colors.error }]}>{error instanceof Error ? error.message : String(error)}</Text>
        {e?.requestId ? <Text style={[styles.caption, styles.faint]}>Request ID {e.requestId}</Text> : null}
      </View>
    </View>
  );
}

/** Quiet info line with a leading icon (the designs' "Privacy Shield Active" note). */
export function Notice({ children, icon = 'info-outline', tone = 'violet' }: { children: ReactNode; icon?: IconName; tone?: 'violet' | 'cyan' }) {
  const color = tone === 'cyan' ? colors.tertiary : colors.secondary;
  return (
    <View style={styles.notice}>
      <MaterialIcons name={icon} size={18} color={color} style={{ marginTop: 1 }} />
      <Text style={[styles.caption, { color: colors.textMuted, flex: 1 }]}>{children}</Text>
    </View>
  );
}

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.base },
  scroll: { paddingHorizontal: space.gutter, paddingTop: space.base, paddingBottom: space.xl * 2, gap: space.lg },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 48 },
  headerTitle: { ...type.headline, color: colors.text, flex: 1 },
  section: { gap: space.sm },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: space.base },
  sectionLabel: { ...type.label, color: colors.textMuted },
  stepDot: { width: 22, height: 22, borderRadius: 11, borderWidth: 1, borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
  stepDotDone: { backgroundColor: colors.tertiary, borderColor: colors.tertiary },
  stepText: { fontFamily: fonts.label, fontSize: 12, color: colors.textMuted },
  title: { ...type.title, color: colors.text },
  heroValue: { fontFamily: fonts.semibold, fontSize: 26, lineHeight: 32, textAlign: 'center' },
  body: { ...type.body, color: colors.text },
  caption: { ...type.caption, color: colors.text },
  muted: { color: colors.textMuted },
  faint: { color: colors.textFaint },
  card: { backgroundColor: colors.card, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border, padding: space.md, gap: space.md, overflow: 'hidden' },
  button: { minHeight: 52, borderRadius: radius.control, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.lg },
  buttonRow: { flexDirection: 'row', alignItems: 'center', gap: space.base },
  secondary: { backgroundColor: colors.raised },
  textButton: { minHeight: 44 },
  glow: { borderRadius: radius.control, shadowColor: colors.indigo, shadowOpacity: 0.35, shadowRadius: 20, shadowOffset: { width: 0, height: 6 }, elevation: 6 },
  buttonText: { fontFamily: fonts.semibold, fontSize: 16 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space.base },
  chip: { flexDirection: 'row', gap: 6, minHeight: 44, paddingHorizontal: space.md, borderRadius: radius.chip, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'transparent' },
  chipActive: { backgroundColor: colors.chipBg, borderColor: colors.indigo },
  chipText: { fontFamily: fonts.label, fontSize: 14, color: colors.textMuted },
  chipTextActive: { color: colors.primary },
  ratingHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  scale: { flexDirection: 'row', gap: space.base },
  scaleItem: { flex: 1, minHeight: 44, borderRadius: radius.control, backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: 'transparent' },
  anchors: { flexDirection: 'row', justifyContent: 'space-between' },
  field: { gap: 6 },
  fieldLabel: { ...type.label, color: colors.textMuted },
  inputBox: { justifyContent: 'center', backgroundColor: colors.input, borderRadius: radius.control, borderWidth: 1, borderColor: colors.border },
  input: { fontFamily: fonts.regular, fontSize: 16, color: colors.text, height: 48, width: '100%', paddingHorizontal: space.sm },
  unit: { position: 'absolute', right: space.sm },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: space.sm, minHeight: 56 },
  toggleText: { flex: 1, gap: 2, justifyContent: 'center' },
  // No lineHeight: on iOS, Inter with a lineHeight sits low in its box and looks misaligned with the switch.
  toggleLabel: { fontFamily: fonts.regular, fontSize: 16, color: colors.text },
  switch: { alignSelf: 'center' },
  iconWell: { backgroundColor: colors.raised, alignItems: 'center', justifyContent: 'center' },
  kv: { flexDirection: 'row', gap: space.sm, alignItems: 'center' },
  kvValue: { fontFamily: fonts.label, flexShrink: 1, textAlign: 'right', color: colors.text },
  badge: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 6, borderRadius: radius.chip, paddingHorizontal: space.sm, paddingVertical: 4 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  badgeText: { fontFamily: fonts.label, fontSize: 12, letterSpacing: 0.6 },
  meter: { height: 8, borderRadius: 4, backgroundColor: colors.raised, overflow: 'hidden' },
  meterFill: { height: '100%', borderRadius: 4 },
  inset: { backgroundColor: colors.inset, borderRadius: radius.control, padding: space.md },
  detailsHead: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 32 },
  error: { flexDirection: 'row', gap: space.sm, backgroundColor: 'rgba(147, 0, 10, 0.22)', borderColor: 'rgba(255, 180, 171, 0.35)', borderWidth: 1, borderRadius: radius.control, padding: space.sm },
  notice: { flexDirection: 'row', gap: space.sm, paddingHorizontal: space.xs },
});
