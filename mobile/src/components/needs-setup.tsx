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
        <Body muted center>Connect to the backend on the Setup tab to start testing.</Body>
      </View>
      <Button label="Go to Setup" icon="arrow-forward" onPress={() => router.navigate('/')} />
    </Card>
  );
}
