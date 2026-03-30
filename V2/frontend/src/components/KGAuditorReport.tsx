/** Rendert den Validierungsbericht des KG Auditors (Backend-Schema: passed, steps[]). */

export type StepValidationRow = {
  step_id: number;
  technique_id: string;
  id_exists: boolean;
  tactic_match: boolean;
  path_reachable: boolean;
  phase_conform: boolean;
  cve_valid: boolean;
  eligibility_score?: number | null;
};

type BooleanCheckKey = 'id_exists' | 'tactic_match' | 'path_reachable' | 'phase_conform' | 'cve_valid';

export type KGAuditorReportProps = {
  passed: boolean;
  steps: StepValidationRow[];
  auditorIterations: number;
  correctionHints?: Array<{ step_id: number; technique_id: string; message: string }>;
};

const CHECKS: { key: BooleanCheckKey; label: string }[] = [
  { key: 'id_exists', label: 'Technik-ID im Graph' },
  { key: 'tactic_match', label: 'Taktik vs. Phase' },
  { key: 'path_reachable', label: 'Kill-Chain-Pfad' },
  { key: 'phase_conform', label: 'Phasenreihenfolge' },
  { key: 'cve_valid', label: 'CVE-Referenzen' },
];

function PassFail({ ok }: { ok: boolean }) {
  return (
    <span className={`kg-audit-pf ${ok ? 'pass' : 'fail'}`}>{ok ? 'Pass' : 'Fail'}</span>
  );
}

export function KGAuditorReport({
  passed,
  steps,
  auditorIterations,
  correctionHints = [],
}: KGAuditorReportProps) {
  return (
    <div className="kg-auditor-report" data-screenshot="kg-auditor">
      <h4>Validierungsbericht (KG Auditor)</h4>
      <p className="kg-auditor-meta">
        <span className={`badge ${passed ? 'valid' : 'invalid'}`}>
          {passed ? 'report_passed' : 'report_failed'}
        </span>
        <span className="kg-auditor-iter">
          Auditor-Iterationen (kumulativ): <strong>{auditorIterations}</strong>
        </span>
      </p>
      <div className="kg-auditor-table-wrap">
        <table className="kg-auditor-table">
          <thead>
            <tr>
              <th>Schritt</th>
              <th>Technik-ID</th>
              {CHECKS.map((c) => (
                <th key={c.key} title={c.label}>
                  {c.label}
                </th>
              ))}
              <th>Eligibility</th>
            </tr>
          </thead>
          <tbody>
            {steps.map((row) => (
              <tr key={row.step_id}>
                <td>{row.step_id}</td>
                <td className="kg-audit-tech">{row.technique_id}</td>
                {CHECKS.map((c) => {
                  const v = row[c.key];
                  const ok = typeof v === 'boolean' ? v : false;
                  return (
                    <td key={c.key} className="kg-audit-cell">
                      <PassFail ok={ok} />
                    </td>
                  );
                })}
                <td className="kg-audit-cell kg-audit-elig">
                  {row.eligibility_score != null ? String(row.eligibility_score) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {correctionHints.length > 0 && (
        <div className="kg-auditor-hints">
          <strong>Korrekturhinweise</strong>
          <ul>
            {correctionHints.map((h, i) => (
              <li key={i}>
                Schritt {h.step_id} ({h.technique_id}): {h.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
