import { useState } from 'react';
import { STEP_EXPLANATIONS } from '../data/tacticExplanations';

export interface ExecutionStepData {
  step: string;
  iteration: number;
  timestamp: string;
  detail: string;
  payload: Record<string, unknown>;
}

interface ExecutionTraceProps {
  steps: ExecutionStepData[];
}

const stepLabels: Record<string, string> = {
  generator: 'Generator',
  validator: 'Validator',
  auditor: 'Auditor',
  retry: 'Retry',
};

export function ExecutionTrace({ steps }: ExecutionTraceProps) {
  if (steps.length === 0) return null;

  return (
    <div className="execution-trace">
      <h4>Ablauf</h4>
      <p className="trace-explanation">
        Generator erzeugt Schritte, Validator prüft sie gegen den MITRE ATT&CK Graph.
      </p>
      <div className="trace-timeline">
        {steps.map((s, i) => (
          <TraceStep key={i} step={s} />
        ))}
      </div>
    </div>
  );
}

function TraceStep({ step }: { step: ExecutionStepData }) {
  const [expanded, setExpanded] = useState(false);
  const label = stepLabels[step.step] ?? step.step;
  const explanation = STEP_EXPLANATIONS[step.step];

  return (
    <div className={`trace-step trace-step-${step.step}`}>
      <div className="trace-step-header" onClick={() => setExpanded(!expanded)}>
        <span className="trace-step-badge" title={explanation}>{label}</span>
        <span className="trace-step-iteration">#{step.iteration}</span>
        <span className="trace-step-detail">{step.detail}</span>
        <span className="trace-step-toggle">{expanded ? '−' : '+'}</span>
      </div>
      {explanation && (
        <div className="trace-step-explanation">{explanation}</div>
      )}
      {expanded && (
        <div className="trace-step-payload">
          <pre>{JSON.stringify(step.payload, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
