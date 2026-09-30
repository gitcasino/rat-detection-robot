import { useCallback } from 'react';

import { BootSequence } from './components/BootSequence';
import { TelemetryProvider } from './hooks/TelemetryProvider';
import { DashboardPage } from './pages/DashboardPage';

export function App() {
  const onBootDone = useCallback(() => undefined, []);

  return (
    <TelemetryProvider>
      <BootSequence onDone={onBootDone} />
      <DashboardPage />
    </TelemetryProvider>
  );
}
