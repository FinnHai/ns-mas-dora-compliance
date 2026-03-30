import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ScenarioResponse } from '../api/client';

export function Dashboard() {
  const [scenarios, setScenarios] = useState<ScenarioResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error('Timeout')), 8000)
    );
    Promise.race([api.getScenarios(), timeout])
      .then((d) => setScenarios(d.scenarios || []))
      .catch(() => setScenarios([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <h1>Übersicht</h1>
      <p className="subtitle">DORA-konforme Krisenszenarien für TLPT</p>

      <div className="actions">
        <Link to="/scenario" className="btn btn-primary">
          Neues Szenario
        </Link>
        <Link to="/evaluate" className="btn btn-secondary">
          Neuro vs. Baseline vergleichen
        </Link>
      </div>

      {loading ? (
        <p className="loading">Lade...</p>
      ) : scenarios.length === 0 ? (
        <div className="empty-state">
          <p>Noch keine Szenarien vorhanden.</p>
          <Link to="/scenario">Erstes Szenario erstellen</Link>
        </div>
      ) : (
        <div className="scenario-list">
          {scenarios.map((s) => (
            <Link key={s.id} to={`/scenario/${s.id}`} className="scenario-card">
              <div className="scenario-meta">
                <span className={`status status-${s.status}`}>{s.status}</span>
                <span>{s.events.length} Ereignisse</span>
                {s.validation != null && (
                  <span
                    className={`scenario-score ${s.validation.overall_valid ? 'valid' : 'invalid'}`}
                    title="Action Alignment Score"
                  >
                    {(s.validation.action_alignment_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              <p className="scenario-context">
                {s.threat_context.length > 120 ? `${s.threat_context.slice(0, 120)}…` : s.threat_context}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
