import type { ValidationResponse } from '../api/client';

interface ValidationSummaryProps {
  validation: ValidationResponse;
  compact?: boolean;
}

export function ValidationSummary({ validation, compact = false }: ValidationSummaryProps) {
  return (
    <div className="validation-result">
      <div className="validation-summary">
        <span className={`badge ${validation.overall_valid ? 'valid' : 'invalid'}`}>
          {validation.overall_valid ? 'Gültig' : 'Ungültig'}
        </span>
        <span>Action Alignment: {(validation.action_alignment_score * 100).toFixed(0)}%</span>
      </div>
      {!compact && (
        <>
          <p className="validation-explanation">
            Die Validierung prüft gegen den MITRE ATT&CK Reasoning Graph. Gültig ab 50%.
          </p>
          <div className="validation-breakdown">
            <span title="Anteil Events mit gültiger Taktik">
              Taktik: {((validation.tactic_coverage ?? 0) * 100).toFixed(0)}%
            </span>
            <span title="Anteil Techniken im Graph">
              Technik: {((validation.technique_validity ?? 0) * 100).toFixed(0)}%
            </span>
            <span title="Technik-Taktik-Mapping">
              Mapping: {((validation.technique_mapping ?? 0) * 100).toFixed(0)}%
            </span>
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
        </>
      )}
    </div>
  );
}
