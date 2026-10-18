// Design tokens from design-references/screens/empath/DESIGN.md
// ("Digital Sanctuary": dark-first, luminous cards, indigo/violet/cyan accents).

export const colors = {
  base: '#0B0E14', // Level 0
  card: '#12161F', // Level 1
  raised: '#272A31', // surface-container-high: secondary buttons, icon wells
  input: '#07090D',
  inset: '#0E1118', // explanation panels inside cards
  border: 'rgba(255, 255, 255, 0.08)',
  borderStrong: 'rgba(255, 255, 255, 0.15)',
  ink: '#F4F5FA', // brightest text, white pill buttons, logo
  text: '#E1E2EB',
  textMuted: '#C7C4D7',
  textFaint: '#908FA0',
  primary: '#C0C1FF',
  indigo: '#6366F1',
  violet: '#A855F7',
  secondary: '#DDB7FF',
  tertiary: '#4CD7F6',
  error: '#FFB4AB',
  errorContainer: '#93000A',
  chipBg: 'rgba(99, 102, 241, 0.1)',
  warnBg: 'rgba(221, 183, 255, 0.08)',
} as const;

export const gradient = [colors.indigo, colors.violet] as const;

export const space = { xs: 4, base: 8, sm: 12, md: 16, lg: 24, xl: 40, gutter: 20 } as const;

export const radius = { chip: 999, control: 12, card: 16 } as const;

export const fonts = {
  regular: 'Inter_400Regular',
  semibold: 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  label: 'Geist_500Medium',
} as const;

export const type = {
  headline: { fontFamily: fonts.semibold, fontSize: 28, lineHeight: 34, letterSpacing: -0.28 },
  title: { fontFamily: fonts.semibold, fontSize: 20, lineHeight: 28 },
  body: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 24 },
  label: { fontFamily: fonts.label, fontSize: 13, lineHeight: 18, letterSpacing: 0.65 },
  caption: { fontFamily: fonts.regular, fontSize: 12, lineHeight: 16, letterSpacing: 0.24 },
} as const;
