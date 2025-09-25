import { registerRootComponent } from 'expo';
import { ExpoRoot } from 'expo-router';

function App() {
  return <ExpoRoot context={require.context('./app', true, /^(?!.*\/test\/).*\.(js|jsx|ts|tsx)$/)} />;
}

registerRootComponent(App);