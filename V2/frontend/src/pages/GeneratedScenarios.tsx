import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import type {
  GeneratedScenarioDetail,
  GeneratedScenarioSummary,
  TTPScenario,
} from '../api/client';
import { ValidationSummary } from '../components/ValidationSummary';
import { getTacticExplanation } from '../data/tacticExplanations';

export function GeneratedScenarios() {
  const { id } = useParams();
  const [list, setList] = useState<GeneratedScenarioSummary[]>([]);
  const [detail, setDetail] = useState<GeneratedScenarioDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      setLoading(true);
      setError(null);
      api
        .getGeneratedScenario(id)
        .then(setDetail)
        .catch((e) => {
          setError(String(e));
          setDetail(null);
        })
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
      api
        .getGeneratedScenarios()
        .then((r) => setList(r.scenarios || []))
        .catch((e) => {
          setError(String(e));
          setList([]);
        })
        .finally(() => setLoading(false));
    }
  }, [id]);

  if (id) {
    return (
      <GeneratedScenarioDetailView
        detail={detail}
        loading={loading}
        error={error}
      />
    );
  }

  return (
    <div className="page">
      <h1>Generierte Szenarien</h1>
      <p className="subtitle">
        NS-MAS und Baseline-Läufe aus Evaluation und Interview
      </p>

      {error && (
        <div className="result-box status-failed">
          <h3>Fehler</h3>
          <p className="error">{error}</p>
        </div>
      )}

      {loading ? (
        <p className="loading">Lade…</p>
      ) : list.length === 0 ? (
        <div className="empty-state">
          <p>Noch keine generierten Szenarien vorhanden.</p>
          <p className="form-hint">
            Führe Evaluation-Runs oder die NS-MAS Pipeline aus – Ergebnisse landen in{' '}
            <code>backend/evaluation/entwicklung_archiv/interview/</code>
          </p>
        </div>
      ) : (
        <div className="scenario-list">
          {list.map((s) => (
            <Link key={s.id} to={`/generated/${s.id}`} className="scenario-card">
              <div className="scenario-meta">
                <span className={`status status-${s.validation_passed ? 'completed' : 'failed'}`}>
                  {s.validation_passed ? 'Valid' : 'Invalid'}
                </span>
                <span>{s.mode === 'baseline' ? 'Baseline' : 'NS-MAS'}</span>
                {s.auditor_iterations != null && (
                  <span title="KG Auditor Iterationen">
                    {s.auditor_iterations} Iter.
                  </span>
                )}
                {s.elapsed_seconds != null && (
                  <span>{s.elapsed_seconds.toFixed(0)}s</span>
                )}
                {s.validation_passed != null && (
                  <span
                    className={`scenario-score ${s.validation_passed ? 'valid' : 'invalid'}`}
                  >
                    {s.validation_passed ? '✓' : '✗'}
                  </span>
                )}
              </div>
              <p className="scenario-context">
                <strong>{s.label}</strong>
                {s.timestamp && ` · ${s.timestamp}`}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function GeneratedScenarioDetailView({
  detail,
  loading,
  error,
}: {
  detail: GeneratedScenarioDetail | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) return <p className="loading">Lade…</p>;
  if (error) {
    return (
      <div className="page">
        <h1>Fehler</h1>
        <div className="result-box status-failed">
          <p className="error">{error}</p>
          <Link to="/generated" className="btn btn-secondary" style={{ marginTop: '1rem' }}>
            Zurück zur Liste
          </Link>
        </div>
      </div>
    );
  }
  if (!detail) return null;

  const ttp = detail.ttp as TTPScenario | null;
  const allPhases = ttp?.phases ?? [];
  const validation = detail.validation as {
    overall_valid?: boolean;
    action_alignment_score?: number;
    results?: Array<{ order: number; is_valid: boolean; message: string }>;
    tactic_coverage?: number;
    technique_validity?: number;
    technique_mapping?: number;
    sequence_valid?: boolean;
    sequence_message?: string;
  } | null;

  return (
    <div className="page">
      <div className="actions">
        <Link to="/generated" className="btn btn-secondary">
          ← Zurück zur Liste
        </Link>
      </div>

      <h1>{detail.id.replace(/_/g, ' ')}</h1>
      <p className="subtitle">
        {String(detail.metadata?.mode ?? '—')} ·{' '}
        {detail.metadata?.timestamp ? String(detail.metadata.timestamp) : '—'}
        {detail.metadata?.elapsed_seconds != null
          ? ` · ${Number(detail.metadata.elapsed_seconds).toFixed(1)}s`
          : ''}
      </p>

      {detail.narrative && (
        <div className="result-box">
          <h3>Narrativ</h3>
          <p className="report-narrative">{detail.narrative}</p>
        </div>
      )}

      {ttp && (
        <div className="result-box">
          <h3>TTP-Szenario</h3>
          <div className="validation-result">
            <div className="ttp-meta-row">
              <div>
                <div className="meta-label">Zielorganisation</div>
                <div className="meta-value">{ttp.target_organization ?? '—'}</div>
              </div>
              <div>
                <div className="meta-label">Threat Actor</div>
                <div className="meta-value">{ttp.threat_actor ?? '—'}</div>
              </div>
            </div>
            <div className="events">
              <h4>{allPhases.length} Phasen</h4>
              {allPhases.map((phase, pi) => (
                <div key={pi} className={pi > 0 ? 'phase-section' : ''}>
                  <div className="event-tactic">
                    Phase: {phase.phase ?? '—'}
                    {phase.high_level_goals?.length
                      ? ` – ${phase.high_level_goals.join(', ')}`
                      : ''}
                  </div>
                  {(phase.steps ?? []).map((s, si) => (
                    <div key={si} className="event">
                      <span className="event-order">{s.step_id ?? si + 1}</span>
                      <span
                        className="event-tactic"
                        title={getTacticExplanation(s.tactic)}
                      >
                        {s.technique_id ?? s.tactic ?? '−'}
                      </span>
                      <span className="event-desc">{s.description ?? '—'}</span>
                      {s.tactic && getTacticExplanation(s.tactic) && (
                        <span className="event-explanation">
                          {getTacticExplanation(s.tactic)}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {validation && (
        <ValidationSummary
          validation={{
            overall_valid: validation.overall_valid ?? false,
            action_alignment_score: validation.action_alignment_score ?? 0,
            results: validation.results ?? [],
            tactic_coverage: validation.tactic_coverage,
            technique_validity: validation.technique_validity,
            technique_mapping: validation.technique_mapping,
            sequence_valid: validation.sequence_valid,
            sequence_message: validation.sequence_message,
          }}
        />
      )}

      {!ttp && !detail.narrative && !validation && (
        <div className="result-box">
          <p className="loading">Keine Szenario-Daten vorhanden.</p>
        </div>
      )}
    </div>
  );
}
