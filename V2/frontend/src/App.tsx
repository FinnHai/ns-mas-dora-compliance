import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import './App.css';

const ScenarioEditor = lazy(() => import('./pages/ScenarioEditor').then((m) => ({ default: m.ScenarioEditor })));
const ValidationView = lazy(() => import('./pages/ValidationView').then((m) => ({ default: m.ValidationView })));
const EvaluationCompareView = lazy(() =>
  import('./pages/EvaluationCompareView').then((m) => ({ default: m.EvaluationCompareView }))
);
const NSMasPipeline = lazy(() =>
  import('./pages/NSMasPipeline').then((m) => ({ default: m.NSMasPipeline }))
);
const GeneratedScenarios = lazy(() =>
  import('./pages/GeneratedScenarios').then((m) => ({ default: m.GeneratedScenarios }))
);

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center' }}>Lade…</div>}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="scenario" element={<ScenarioEditor />} />
              <Route path="scenario/:id" element={<ScenarioEditor />} />
              <Route path="validation/:id" element={<ValidationView />} />
              <Route path="evaluate" element={<EvaluationCompareView />} />
              <Route path="ns-mas" element={<NSMasPipeline />} />
              <Route path="generated" element={<GeneratedScenarios />} />
              <Route path="generated/:id" element={<GeneratedScenarios />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
