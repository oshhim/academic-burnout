import MaterialIcons from '@expo/vector-icons/MaterialIcons';
import { Tabs } from 'expo-router';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import type { IconName } from '@/components/ui';
import { colors, fonts } from '@/theme';

const TABS: { name: string; title: string; icon: IconName }[] = [
  { name: 'facial', title: 'Facial', icon: 'face' },
  { name: 'voice', title: 'Voice', icon: 'graphic-eq' },
  { name: 'risk', title: 'Risk', icon: 'insights' },
  { name: 'activities', title: 'Activities', icon: 'self-improvement' },
  { name: 'profile', title: 'Profile', icon: 'person-outline' },
];

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textFaint,
        // Room for the pill and label above the home indicator.
        tabBarStyle: { backgroundColor: colors.base, borderTopColor: colors.border, height: 68 + insets.bottom, paddingTop: 6, paddingBottom: insets.bottom + 8 },
        tabBarLabelStyle: { fontFamily: fonts.label, fontSize: 11, lineHeight: 14 },
      }}>
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            // Active tab sits in a soft indigo pill, as in the reference designs.
            tabBarIcon: ({ color, focused }) => (
              <View style={{ width: 48, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: focused ? 'rgba(99,102,241,0.18)' : 'transparent' }}>
                <MaterialIcons name={tab.icon} color={String(color)} size={22} />
              </View>
            ),
          }}
        />
      ))}
      {/* Entry redirect, not a tab. */}
      <Tabs.Screen name="index" options={{ href: null }} />
    </Tabs>
  );
}
