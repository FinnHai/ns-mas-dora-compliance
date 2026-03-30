import { useState } from 'react';
import { api } from '../api/client';
import type { EvaluationCompareResponse, ScenarioGenerateRequest } from '../api/client';
import { ValidationSummary } from '../components/ValidationSummary';
import { getTacticExplanation } from '../data/tacticExplanations';

export function EvaluationCompareView() {
  const [threatContext, setThreatContext] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EvaluationCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!threatContext.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const req: ScenarioGenerateRequest = {
        threat_context: threatContext,
        duration_hours: 24,
      };
      const data = await api.evaluateCompare(req);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fehler beim Vergleich');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h1>Evaluation: Neuro vs. Baseline</h1>
      <p className="subtitle">
        Vergleicht Action Alignment Scores beider Modi mit gleichem Bedrohungskontext
      </p>

      <form onSubmit={handleCompare} className="editor-form">
        <div className="form-group">
          <label htmlFor="threat">Bedrohungskontext *</label>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ marginBottom: '0.5rem' }}
            onClick={() =>
              setThreatContext(
                'Ransomware-Angriff über Phishing: Kriminelle Gruppe nutzt E-Mail-Kampagne, um Ransomware in ein Finanzinstitut einzuschleusen. Ziele: ERP-System, Dateiserver, E-Mail.'
              )
            }
          >
            Beispiel laden
          </button>
          <textarea
            id="threat"
            value={threatContext}
            onChange={(e) => setThreatContext(e.target.value)}
            placeholder="z.B. Ransomware-Angriff über Phishing..."
            rows={4}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Vergleiche…' : 'Beide Modi vergleichen'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="evaluation-compare">
          <h3>Vergleichsergebnis</h3>
          <div className="compare-grid">
            <div className="compare-column">
              <h4>Neuro-symbolisch</h4>
              <p className="compare-score">
                Action Alignment: {(result.neuro_validation.action_alignment_score * 100).toFixed(0)}%
              </p>
              <ValidationSummary validation={result.neuro_validation} compact />
              <div className="events events-compact">
                {result.neuro.events.map((e) => (
                  <div key={e.order} className="event">
                    <span className="event-order">{e.order}</span>
                    <span className="event-tactic" title={getTacticExplanation(e.tactic_id)}>
                      {e.tactic_id || '-'}
                    </span>
                    <span className="event-desc">{e.description}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="compare-column">
              <h4>Baseline (reines LLM)</h4>
              <p className="compare-score">
                Action Alignment: {(result.baseline_validation.action_alignment_score * 100).toFixed(0)}%
              </p>
              <ValidationSummary validation={result.baseline_validation} compact />
              <div className="events events-compact">
                {result.baseline.events.map((e) => (
                  <div key={e.order} className="event">
                    <span className="event-order">{e.order}</span>
                    <span className="event-tactic" title={getTacticExplanation(e.tactic_id)}>
                      {e.tactic_id || '-'}
                    </span>
                    <span className="event-desc">{e.description}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="compare-delta">
            <strong>Differenz:</strong>{' '}
            {(result.neuro_validation.action_alignment_score - result.baseline_validation.action_alignment_score) * 100 >
            0
              ? '+'
              : ''}
            {(
              (result.neuro_validation.action_alignment_score -
                result.baseline_validation.action_alignment_score) *
              100
            ).toFixed(0)}
            % (Neuro vs. Baseline)
          </div>
        </div>
      )}
    </div>
  );
}
