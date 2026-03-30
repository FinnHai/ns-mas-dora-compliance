/** Geteilter State-Typ für NS-MAS UI und Thesis-Fixtures. */

export type BackendValidationReport = {
  passed?: boolean;
  auditor_iterations?: number;
  steps?: Array<{
    step_id: number;
    technique_id: string;
    id_exists: boolean;
    tactic_match: boolean;
    path_reachable: boolean;
    phase_conform: boolean;
    cve_valid: boolean;
    eligibility_score?: number | null;
  }>;
  correction_hints?: Array<{
    step_id: number;
    technique_id: string;
    message: string;
    suggested_technique_id?: string | null;
  }>;
  /** Legacy: Graph-Validierung (/validation/) */
  overall_valid?: boolean;
  action_alignment_score?: number;
  results?: Array<{ order: number; is_valid: boolean; message: string }>;
  tactic_coverage?: number;
  technique_validity?: number;
  technique_mapping?: number;
  sequence_valid?: boolean;
  sequence_message?: string;
};

export type StateData = {
  attack_sketch?: { phases?: Array<{ phase?: string; high_level_goals?: string[]; target_assets?: string[] }> };
  ttp_scenario?: {
    scenario_id?: string;
    target_organization?: string;
    threat_actor?: string;
    phases?: Array<{
      phase?: string;
      steps?: Array<{ technique_id?: string; description?: string; tactic_id?: string }>;
      high_level_goals?: string[];
      target_assets?: string[];
    }>;
  };
  validation_report?: BackendValidationReport;
  report?: { msel?: string; narrative?: string; msel_json?: string };
  auditor_iterations?: number;
};
