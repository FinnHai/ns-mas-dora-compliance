import { useEffect, useState, useRef } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { AgentConfigData, ScenarioResponse } from '../api/client';
import { AgentConfigPanel } from '../components/AgentConfigPanel';
import { ExecutionTrace } from '../components/ExecutionTrace';
import { ValidationSummary } from '../components/ValidationSummary';
import { getTacticExplanation } from '../data/tacticExplanations';

export function ScenarioEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [threatContext, setThreatContext] = useState('');
  const [durationHours, setDurationHours] = useState(24);
  const [additionalContext, setAdditionalContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [loadedScenario, setLoadedScenario] = useState<Awaited<ReturnType<typeof api.getScenario>> | null>(null);
  const [agentConfig, setAgentConfig] = useState<AgentConfigData | null>(null);
  const [baselineMode, setBaselineMode] = useState(false);
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (id) {
      api.getScenario(id).then(setLoadedScenario).catch(() => setLoadedScenario(null));
    } else {
      setLoadedScenario(null);
      api.getAgentConfig().then(setAgentConfig).catch(() => setAgentConfig(null));
    }
  }, [id]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [liveLogs]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threatContext.trim()) return;
    setLoading(true);
    setResult(null);
    setLiveLogs([]);
    try {
      for await (const event of api.generateScenarioStream(
        {
          threat_context: threatContext,
          duration_hours: durationHours,
          additional_context: additionalContext || undefined,
          agent_config: agentConfig ?? undefined,
        },
        baselineMode
      )) {
        if (event.type === 'log' && event.message) {
          setLiveLogs((prev) => [...prev, event.message!]);
        } else if (event.type === 'complete' && event.result) {
          setResult(event.result as ScenarioResponse);
          if (event.result.id) navigate(`/scenario/${event.result.id}`);
        } else if (event.type === 'error' && event.message) {
          setResult({
            id: '',
            status: 'failed',
            events: [],
            threat_context: threatContext,
            audit_feedback: [],
            error_message: event.message,
          });
        }
      }
    } catch (err) {
      setResult({
        id: '',
        status: 'failed',
        events: [],
        threat_context: threatContext,
        audit_feedback: [],
        error_message: String(err),
      });
    } finally {
      setLoading(false);
    }
  };

  const trace = loadedScenario?.execution_trace ?? result?.execution_trace ?? [];
  const validation = loadedScenario?.validation ?? result?.validation;
  const resultMap = validation?.results ? Object.fromEntries(validation.results.map((r) => [r.order, r])) : {};

  return (
    <div className="page">
      <h1>{id ? 'Szenario' : 'Neues Szenario'}</h1>
      <p className="subtitle">
        {id ? 'Details und MITRE-Validierung' : 'Bedrohungskontext beschreiben und generieren'}
      </p>

      {loadedScenario && (
        <div className={`result-box status-${loadedScenario.status}`}>
          <h3>Szenario {loadedScenario.id.slice(0, 8)}</h3>
          <p><strong>Status:</strong> {loadedScenario.status}</p>
          {loadedScenario.status === 'failed' && loadedScenario.error_message && (
            <p className="error">{loadedScenario.error_message}</p>
          )}
          <p><strong>Kontext:</strong> {loadedScenario.threat_context}</p>
          {loadedScenario.events.length > 0 && (
            <div className="events">
              <h4>Ereignisse</h4>
              <p className="events-explanation">
                Jedes Ereignis entspricht einem Schritt in der MITRE ATT&CK Kill Chain.
              </p>
              {loadedScenario.events.map((e) => {
                const res = resultMap[e.order];
                return (
                  <div key={e.order} className="event">
                    <span className="event-order">{e.order}</span>
                    <span
                      className={`event-validation-badge ${res ? (res.is_valid ? 'valid' : 'invalid') : ''}`}
                      title={res?.message}
                    >
                      {res ? (res.is_valid ? '✓' : '✗') : '−'}
                    </span>
                    <span className="event-tactic" title={getTacticExplanation(e.tactic_id)}>
                      {e.tactic_id || '-'}
                    </span>
                    <span className="event-desc">{e.description}</span>
                    {e.tactic_id && getTacticExplanation(e.tactic_id) && (
                      <span className="event-explanation">{getTacticExplanation(e.tactic_id)}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {validation && <ValidationSummary validation={validation} />}
          {trace.length > 0 && <ExecutionTrace steps={trace} />}
          <Link to={`/validation/${id}`} className="btn btn-primary" style={{ marginTop: '1rem' }}>
            Detaillierte Validierung
          </Link>
        </div>
      )}

      {!id && (
        <>
          <AgentConfigPanel
            config={agentConfig}
            onChange={setAgentConfig}
          />
          <form onSubmit={handleSubmit} className="editor-form">
            <div className="form-group">
              <label htmlFor="threat">Bedrohungskontext *</label>
              <div className="form-group-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setThreatContext(
                      'Ransomware-Angriff über Phishing: Kriminelle Gruppe nutzt E-Mail-Kampagne, um Ransomware in ein Finanzinstitut einzuschleusen. Ziele: ERP-System, Dateiserver, E-Mail.'
                    );
                    setAdditionalContext('Typischer Kill-Chain-Ablauf: Initial Access → Execution → Persistence → Credential Access → Lateral Movement → Impact.');
                  }}
                >
                  Beispiel laden
                </button>
              </div>
              <textarea
                id="threat"
                value={threatContext}
                onChange={(e) => setThreatContext(e.target.value)}
                placeholder="z.B. Ransomware-Angriff über Phishing, Ziele: ERP-System, E-Mail"
                rows={4}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="duration">Zeitrahmen (Stunden)</label>
              <input
                id="duration"
                type="number"
                min={1}
                max={168}
                value={durationHours}
                onChange={(e) => setDurationHours(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={baselineMode}
                  onChange={(e) => setBaselineMode(e.target.checked)}
                />
                Baseline-Modus (ohne Graph-Validierung)
              </label>
              <span className="form-hint">
                Reines LLM ohne MITRE ATT&CK Validierung – für Vergleichsevaluation
              </span>
            </div>
            <div className="form-group">
              <label htmlFor="additional">Zusätzlicher Kontext</label>
              <textarea
                id="additional"
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                placeholder="Optionale Angaben..."
                rows={2}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Generiere…' : 'Generieren'}
            </button>
            {loading && liveLogs.length > 0 && (
              <div className="live-logs">
                <h4>Live-Logs</h4>
                <div className="live-logs-content">
                  {liveLogs.map((msg, i) => (
                    <div key={i} className="live-log-line">
                      {msg}
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              </div>
            )}
          </form>
        </>
      )}

      {result && !id && (
        <div className={`result-box status-${result.status}`}>
          <h3>Ergebnis</h3>
          {result.status === 'failed' && result.error_message && (
            <p className="error">{result.error_message}</p>
          )}
          {result.events.length > 0 && (
            <div className="events">
              <h4>Ereignisse</h4>
              <p className="events-explanation">
                Jedes Ereignis entspricht einem Schritt in der MITRE ATT&CK Kill Chain.
              </p>
              {result.events.map((e) => {
                const res = resultMap[e.order];
                return (
                  <div key={e.order} className="event">
                    <span className="event-order">{e.order}</span>
                    <span
                      className={`event-validation-badge ${res ? (res.is_valid ? 'valid' : 'invalid') : ''}`}
                      title={res?.message}
                    >
                      {res ? (res.is_valid ? '✓' : '✗') : '−'}
                    </span>
                    <span className="event-tactic" title={getTacticExplanation(e.tactic_id)}>
                      {e.tactic_id || '-'}
                    </span>
                    <span className="event-desc">{e.description}</span>
                    {e.tactic_id && getTacticExplanation(e.tactic_id) && (
                      <span className="event-explanation">{getTacticExplanation(e.tactic_id)}</span>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {result.validation && <ValidationSummary validation={result.validation} />}
          {result.audit_feedback.length > 0 && (
            <div className="audit-feedback">
              <h4>Audit-Feedback</h4>
              <ul>
                {result.audit_feedback.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}
          {trace.length > 0 && <ExecutionTrace steps={trace} />}
        </div>
      )}
    </div>
  );
}
