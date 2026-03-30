/**
 * Statischer UI-Zustand für BA-Screenshots (S2: Bundesbank / Lazarus Group, 2 Auditor-Iterationen).
 * Aktivierung: /ns-mas?fixture=thesis-s2-hitl (nur im Vite-Dev-Server).
 * Technik-IDs und Pass-Muster entsprechen dem Evaluationslauf nsmas_s2_r1 (eval_comparison.json).
 */
import type { StateData } from './nsMasStateTypes';

export const nsMasThesisS2HitlFixture: StateData = {
  auditor_iterations: 2,
  ttp_scenario: {
    scenario_id: 'thesis-s2-screenshot',
    target_organization: 'Deutsche Bundesbank',
    threat_actor: 'Lazarus Group',
    phases: [
      {
        phase: 'in',
        high_level_goals: ['Initial Access'],
        steps: [
          {
            technique_id: 'T1566.001',
            tactic_id: 'initial-access',
            description:
              'Spearphishing mit bösartigem Anhang zur Kompromittierung von Arbeitsplätzen im Zulieferer-Netz.',
          },
        ],
      },
      {
        phase: 'through',
        high_level_goals: ['Execution', 'Lateral Movement'],
        steps: [
          {
            technique_id: 'T1047',
            tactic_id: 'execution',
            description: 'Ausführung von Payloads über Windows Management Instrumentation.',
          },
          {
            technique_id: 'T1570',
            tactic_id: 'lateral-movement',
            description: 'Übertragung von Tools zwischen Segmenten der Zielumgebung.',
          },
          {
            technique_id: 'T1091',
            tactic_id: 'lateral-movement',
            description: 'Weiterverbreitung über Wechselmedien / Replikation.',
          },
        ],
      },
      {
        phase: 'out',
        high_level_goals: ['Exfiltration'],
        steps: [
          {
            technique_id: 'T1020',
            tactic_id: 'exfiltration',
            description: 'Automatisierte Datenexfiltration aus kritischen Systemen.',
          },
          {
            technique_id: 'T1029',
            tactic_id: 'exfiltration',
            description: 'Zeitgesteuerte Übertragung sensibler Daten.',
          },
        ],
      },
    ],
  },
  validation_report: {
    passed: true,
    auditor_iterations: 2,
    steps: [
      {
        step_id: 1,
        technique_id: 'T1566.001',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
      {
        step_id: 2,
        technique_id: 'T1047',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
      {
        step_id: 3,
        technique_id: 'T1570',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
      {
        step_id: 4,
        technique_id: 'T1091',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
      {
        step_id: 5,
        technique_id: 'T1020',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
      {
        step_id: 6,
        technique_id: 'T1029',
        id_exists: true,
        tactic_match: true,
        path_reachable: true,
        phase_conform: true,
        cve_valid: true,
        eligibility_score: null,
      },
    ],
    correction_hints: [],
  },
};
