import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ValidationResponse } from '../api/client';

export function ValidationView() {
  const { id } = useParams();
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const loadAndValidate = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setValidation(null);
    try {
      const s = await api.getScenario(id);
      if (s.events.length > 0) {
        if (s.validation) {
          setValidation(s.validation);
        } else {
          const v = await api.validateScenario(
            s.events.map((e) => ({
              order: e.order,
              description: e.description,
              tactic_id: e.tactic_id,
              technique_id: e.technique_id,
            }))
          );
          setValidation(v);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (id) {
      loadAndValidate();
    } else {
      setValidation(null);
    }
  }, [id, loadAndValidate]);

  return (
    <div className="page">
      <h1>Validierung</h1>
      <p className="subtitle">MITRE ATT&CK Action Alignment</p>

      {id && (
        <>
          <button onClick={loadAndValidate} className="btn btn-primary" disabled={loading}>
            {loading ? 'Lade…' : 'Erneut validieren'}
          </button>

          {validation && (
            <div className="validation-result">
              <div className="validation-summary">
                <span className={`badge ${validation.overall_valid ? 'valid' : 'invalid'}`}>
                  {validation.overall_valid ? 'Gültig' : 'Ungültig'}
                </span>
                <span>Action Alignment: {(validation.action_alignment_score * 100).toFixed(0)}%</span>
              </div>
              <p className="validation-explanation">
                Die Validierung prüft gegen den MITRE ATT&CK Reasoning Graph. Gültig ab 50%.
              </p>
              <div className="validation-breakdown">
                <span title="Anteil Events mit gültiger Taktik">Taktik: {((validation.tactic_coverage ?? 0) * 100).toFixed(0)}%</span>
                <span title="Anteil Techniken im Graph">Technik: {((validation.technique_validity ?? 0) * 100).toFixed(0)}%</span>
                <span title="Technik-Taktik-Mapping">Mapping: {((validation.technique_mapping ?? 0) * 100).toFixed(0)}%</span>
                {validation.sequence_valid === false && validation.sequence_message && (
                  <span className="sequence-warn">Sequenz: {validation.sequence_message}</span>
                )}
              </div>
              <div className="validation-details">
                {validation.results.map((r) => (
                  <div key={r.order} className={`validation-item ${r.is_valid ? 'valid' : 'invalid'}`}>
                    <span className="order">{r.order}</span>
                    <span className="message">{r.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!id && <p>Kein Szenario ausgewählt.</p>}
    </div>
  );
}
