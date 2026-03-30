import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import { ValidationSummary } from '../components/ValidationSummary';
import { KGAuditorReport } from '../components/KGAuditorReport';
import { getTacticExplanation } from '../data/tacticExplanations';
import { nsMasThesisS2HitlFixture } from '../fixtures/nsMasThesisS2Fixture';
import type { StateData } from '../fixtures/nsMasStateTypes';

export function NSMasPipeline() {
  const [searchParams] = useSearchParams();
  const [targetOrg, setTargetOrg] = useState('');
  const [threatProfile, setThreatProfile] = useState('APT29');
  const [scopeDoc, setScopeDoc] = useState('');
  const [loading, setLoading] = useState(false);
  const [awaitingApproval, setAwaitingApproval] = useState(false);
  const [stateData, setStateData] = useState<StateData | null>(null);
  const [result, setResult] = useState<StateData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const f = searchParams.get('fixture');
    if (f === 'thesis-s2-hitl') {
      setStateData(nsMasThesisS2HitlFixture);
      setAwaitingApproval(true);
      setResult(null);
      setError(null);
      setLoading(false);
    }
  }, [searchParams]);

  const handleRun = async () => {
    if (!targetOrg.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setStateData(null);
    setAwaitingApproval(false);
    try {
      const res = await api.nsMasRun({
        target_organization: targetOrg,
        threat_profile: threatProfile,
        scope_document: scopeDoc || undefined,
      });
      const data = (res.state ?? res.interrupt ?? {}) as StateData;
      if (res.status === 'awaiting_approval') {
        setAwaitingApproval(true);
        setStateData(data);
      } else {
        setResult((res.result ?? data) as StateData);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approved: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.nsMasResume(approved);
      setAwaitingApproval(false);
      setResult((res.result ?? {}) as StateData);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const loadExample = () => {
    setTargetOrg('Atruvia AG');
    setThreatProfile('APT29');
    setScopeDoc(
      'Kompromittierung des Online-Banking-Systems über Spearphishing gegen Vorstandsmitglieder. Kritische Funktionen: SWIFT-Zahlungsverkehr, Kundendatenbank, Active Directory.'
    );
  };

  const loadThesisS2Eval = () => {
    setTargetOrg('Deutsche Bundesbank');
    setThreatProfile('Lazarus Group');
    setScopeDoc(
      'Supply-Chain-Angriff über kompromittierten IT-Dienstleister. Kritische Funktionen: Interbanken-Kommunikation, HSM-Schlüsselverwaltung, SWIFT-Gateway.'
    );
  };

  /** Demo für BA-Screenshots: Human-in-the-Loop im Artefakt */
  const loadHitlDemo = () => {
    setTargetOrg('Atruvia AG');
    setThreatProfile('APT41');
    setScopeDoc(
      'Spearphishing gegen Vorstandsmitglieder, anschließend Lateral Movement zu SWIFT- und Kundendaten-Systemen. Kritische Funktionen: Zahlungsverkehr, Active Directory.'
    );
  };

  const ttp = stateData?.ttp_scenario ?? result?.ttp_scenario;
  const validation = stateData?.validation_report ?? result?.validation_report;
  const report = result?.report;
  const allPhases = ttp?.phases ?? [];
  const allSteps = allPhases.flatMap((p, pi) =>
    (p.steps ?? []).map((s, si) => ({ ...s, phase: p.phase, phaseIndex: pi, order: si + 1 }))
  );

  const backendSteps = validation?.steps;
  const hasKGAuditorSteps = Array.isArray(backendSteps) && backendSteps.length > 0;
  const legacyGraphResults = validation?.results && validation.results.length > 0;
  const auditorIterations =
    stateData?.auditor_iterations ??
    validation?.auditor_iterations ??
    0;

  return (
    <div className="page">
      <h1>NS-MAS Pipeline</h1>
      <p className="subtitle">
        Scenario Planner → TTP Generator → KG Auditor → Human Review → Report Synthesizer
      </p>

      <form onSubmit={(e) => { e.preventDefault(); handleRun(); }} className="editor-form">
        <div className="form-group">
          <label htmlFor="target-org">Zielorganisation *</label>
          <div className="form-group-actions">
            <button type="button" className="btn btn-secondary" onClick={loadExample}>
              Beispiel laden
            </button>
            <button type="button" className="btn btn-secondary" onClick={loadThesisS2Eval} title="Evaluations-Szenario S2 (Kap. 4.4 / Kap. 5)">
              Eval S2 (Bundesbank / Lazarus)
            </button>
            <button type="button" className="btn btn-secondary" onClick={loadHitlDemo} title="Lädt Szenario für Human-in-the-Loop-Screenshots (BA)">
              Demo: Human-in-the-Loop
            </button>
          </div>
          <input
            id="target-org"
            type="text"
            value={targetOrg}
            onChange={(e) => setTargetOrg(e.target.value)}
            placeholder="z.B. Finanzinstitut XY"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="threat-profile">Bedrohungsprofil</label>
          <select
            id="threat-profile"
            value={threatProfile}
            onChange={(e) => setThreatProfile(e.target.value)}
          >
            <option value="APT29">APT29</option>
            <option value="Lazarus Group">Lazarus Group</option>
            <option value="FIN13">FIN13</option>
            <option value="APT41">APT41</option>
            <option value="FIN7">FIN7</option>
            <option value="Ransomware">Ransomware</option>
          </select>
          <span className="form-hint">Typischer Advanced Persistent Threat für Szenarien (Eval: APT29, Lazarus Group, FIN13, APT41)</span>
        </div>
        <div className="form-group">
          <label htmlFor="scope">Scope (optional)</label>
          <textarea
            id="scope"
            value={scopeDoc}
            onChange={(e) => setScopeDoc(e.target.value)}
            placeholder="Scope-Dokument oder Kontext (kritische Funktionen, Ziele)"
            rows={4}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Läuft…' : 'Pipeline starten'}
        </button>
      </form>

      {import.meta.env.DEV && (
        <p className="form-hint screenshot-dev-hint">
          Screenshot-Fixture (ohne Backend):{' '}
          <a href="/ns-mas?fixture=thesis-s2-hitl">/ns-mas?fixture=thesis-s2-hitl</a>
        </p>
      )}

      {error && (
        <div className="result-box status-failed">
          <h3>Fehler</h3>
          <p className="error">{error}</p>
        </div>
      )}

      {awaitingApproval && stateData && (
        <div className="result-box status-running">
          <div data-screenshot="hitl-review">
            <div className="hitl-badge">
              Human-in-the-Loop (DR5) – Freigabe erforderlich
            </div>
            <h3>Human Review erforderlich</h3>
            <p className="review-hint">
              Bitte prüfen Sie das generierte Szenario und geben Sie es frei oder lehnen Sie ab.
            </p>
          </div>

          {ttp && (
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
                <h4>TTP-Szenario ({allSteps.length} Schritte)</h4>
                <p className="events-explanation">
                  Generierte MITRE ATT&CK Schritte, validiert durch den KG Auditor.
                </p>
                {allPhases.map((phase, pi) => (
                  <div key={pi} className={pi > 0 ? 'phase-section' : ''}>
                    <div className="event-tactic">
                      Phase: {phase.phase ?? '—'}
                      {phase.high_level_goals?.length ? ` – ${phase.high_level_goals.join(', ')}` : ''}
                    </div>
                    {(phase.steps ?? []).map((s, si) => (
                      <div key={si} className="event">
                        <span className="event-order">{si + 1}</span>
                        <span className="event-tactic" title={getTacticExplanation(s.tactic_id)}>
                          {s.technique_id ?? s.tactic_id ?? '−'}
                        </span>
                        <span className="event-desc">{s.description ?? '—'}</span>
                        {s.tactic_id && getTacticExplanation(s.tactic_id) && (
                          <span className="event-explanation">{getTacticExplanation(s.tactic_id)}</span>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasKGAuditorSteps && validation && backendSteps && (
            <KGAuditorReport
              passed={validation.passed ?? false}
              steps={backendSteps}
              auditorIterations={auditorIterations}
              correctionHints={validation.correction_hints}
            />
          )}

          {validation && legacyGraphResults && !hasKGAuditorSteps && (
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

          <div className="actions button-row" data-screenshot="hitl-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleApprove(true)}
              disabled={loading}
            >
              Freigeben
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleApprove(false)}
              disabled={loading}
            >
              Ablehnen
            </button>
          </div>
        </div>
      )}

      {result && !awaitingApproval && (
        <div className="result-box status-completed">
          <h3>MSEL-Report</h3>
          {hasKGAuditorSteps && validation && backendSteps && (
            <KGAuditorReport
              passed={validation.passed ?? false}
              steps={backendSteps}
              auditorIterations={auditorIterations}
              correctionHints={validation.correction_hints}
            />
          )}
          {report?.narrative && (
            <div className="validation-result">
              <h4>Narrativ</h4>
              <p className="report-narrative">{report.narrative}</p>
            </div>
          )}
          {report?.msel && (
            <div className="validation-result phase-section">
              <h4>MSEL (Master Scenario Event List)</h4>
              <pre className="result-pre">{report.msel}</pre>
            </div>
          )}
          {report?.msel_json && !report?.msel && (
            <div className="validation-result phase-section">
              <h4>MSEL (JSON)</h4>
              <pre className="result-pre">{report.msel_json}</pre>
            </div>
          )}
          {ttp && !report?.msel && !report?.msel_json && (
            <div className="events">
              <h4>TTP-Szenario</h4>
              {allPhases.map((phase, pi) => (
                <div key={pi} className={pi > 0 ? 'phase-section' : ''}>
                  <div className="event-tactic">
                    {phase.phase}
                  </div>
                  {(phase.steps ?? []).map((s, si) => (
                    <div key={si} className="event">
                      <span className="event-order">{si + 1}</span>
                      <span className="event-tactic">{s.technique_id ?? '−'}</span>
                      <span className="event-desc">{s.description ?? '—'}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
          {!report?.msel && !report?.msel_json && !ttp && (
            <pre className="result-pre">{JSON.stringify(result, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  );
}
