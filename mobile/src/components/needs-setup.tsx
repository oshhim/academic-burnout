import { router } from 'expo-router';
import { View } from 'react-native';

import { space } from '@/theme';

import { Body, Button, Card, IconWell, Title } from './ui';

export function NeedsSetup() {
  return (
    <Card>
      <View style={{ alignItems: 'center', gap: space.sm }}>
        <IconWell icon="link-off" size={56} />
        <Title center>Not connected yet</Title>
        <Body muted center>Connect to the backend on the Profile tab to start testing.</Body>
      </View>
      <Button label="Go to Profile" icon="arrow-forward" onPress={() => router.navigate('/profile')} />
    </Card>
  );
}
