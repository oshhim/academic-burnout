import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import { useActiveParticipant, useSession } from '@/lib/session';
import { colors, fonts } from '@/theme';

import { Badge } from './ui';

/** Header right side: DEMO/REAL chip plus the avatar shortcut to Profile, as in the designs. */
export function ModeBadge({ showAvatar = true }: { showAvatar?: boolean }) {
  const active = useActiveParticipant();
  const { displayName } = useSession();
  const letters = displayName.trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('');
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      {/* Badge aligns itself to the top by default; this wrapper centres it on the avatar. */}
      {active ? (
        <View style={{ justifyContent: 'center', height: 36 }}>
          <Badge label={active.real ? 'REAL' : 'DEMO'} tone={active.real ? 'success' : 'warn'} />
        </View>
      ) : null}
      {showAvatar ? (
        <Pressable
          onPress={() => router.navigate('/profile')}
          hitSlop={6}
          accessibilityRole="button"
          accessibilityLabel="Open profile"
          style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(99,102,241,0.18)', borderWidth: 1, borderColor: 'rgba(128,131,255,0.5)', alignItems: 'center', justifyContent: 'center' }}>
          {letters ? <Text style={{ fontFamily: fonts.semibold, fontSize: 14, color: colors.primary }}>{letters}</Text> : <MaterialIcons name="person-outline" size={20} color={colors.primary} />}
        </Pressable>
      ) : null}
    </View>
  );
}
