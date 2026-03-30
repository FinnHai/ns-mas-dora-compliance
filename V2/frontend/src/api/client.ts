// Backend-URL: V2 auf Port 8000, überschreibbar via VITE_API_URL (z.B. .env)
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface ScenarioEvent {
  order: number;
  description: string;
  tactic_id?: string;
  technique_id?: string;
  timestamp_offset_hours: number;
}

export interface ExecutionStepData {
  step: string;
  iteration: number;
  timestamp: string;
  detail: string;
  payload: Record<string, unknown>;
}

export interface ScenarioResponse {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  events: ScenarioEvent[];
  threat_context: string;
  audit_feedback: string[];
  error_message?: string;
  execution_trace?: ExecutionStepData[];
  validation?: ValidationResponse;
}

export interface AgentConfigData {
  max_audit_iterations: number;
  llm_temperature: number;
  min_events: number;
  max_events: number;
  kill_chain_order: string[];
  require_tactic_per_event: boolean;
  generator_system_prompt: string | null;
}

export interface ScenarioGenerateRequest {
  threat_context: string;
  duration_hours?: number;
  additional_context?: string;
  agent_config?: AgentConfigData;
}

export interface ValidationResult {
  order: number;
  is_valid: boolean;
  message: string;
  suggested_tactic_id?: string;
  suggested_technique_id?: string;
}

export interface ValidationResponse {
  overall_valid: boolean;
  action_alignment_score: number;
  results: ValidationResult[];
  sequence_valid?: boolean;
  sequence_message?: string;
  tactic_coverage?: number;
  technique_validity?: number;
  technique_mapping?: number;
}

export interface EvaluationCompareResponse {
  neuro: ScenarioResponse;
  baseline: ScenarioResponse;
  neuro_validation: ValidationResponse;
  baseline_validation: ValidationResponse;
}

export interface TacticInfo {
  id: string;
  name: string;
  short_name: string;
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export interface StreamEvent {
  type: 'log' | 'complete' | 'error';
  message?: string;
  result?: ScenarioResponse;
}

export const api = {
  getScenarios: () => fetchApi<{ scenarios: ScenarioResponse[] }>('/scenarios/'),
  getScenario: (id: string) => fetchApi<ScenarioResponse>(`/scenarios/${id}`),
  getAgentConfig: () => fetchApi<AgentConfigData>('/agent-config'),
  generateScenario: (req: ScenarioGenerateRequest) =>
    fetchApi<ScenarioResponse>('/scenarios/generate', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  generateScenarioStream: async function* (
    req: ScenarioGenerateRequest,
    baseline = false,
    includeValidation = true
  ): AsyncGenerator<StreamEvent> {
    const res = await fetch(
      `${API_BASE}/scenarios/generate/stream?baseline=${baseline}&include_validation=${includeValidation}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }
    );
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6)) as StreamEvent;
            if (data.type === 'complete' && data.result) {
              data.result = data.result as ScenarioResponse;
            }
            yield data;
          } catch {
            /* ignore parse errors */
          }
        }
      }
    }
    if (buffer.startsWith('data: ')) {
      try {
        const data = JSON.parse(buffer.slice(6)) as StreamEvent;
        yield data;
      } catch {
        /* ignore */
      }
    }
  },
  validateScenario: (events: { order: number; description: string; tactic_id?: string; technique_id?: string }[]) =>
    fetchApi<ValidationResponse>('/validation/', {
      method: 'POST',
      body: JSON.stringify({ events }),
    }),
  evaluateCompare: (req: ScenarioGenerateRequest) =>
    fetchApi<EvaluationCompareResponse>('/evaluation/compare', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
  getTactics: () => fetchApi<{ tactics: TacticInfo[] }>('/graph/tactics'),
  validatePath: (tacticIds: string[]) =>
    fetchApi<{ valid: boolean; message: string }>('/graph/validate-path', {
      method: 'POST',
      body: JSON.stringify({ tactic_ids: tacticIds }),
    }),

  // NS-MAS Pipeline (Planner → Generator → Auditor → Human Review → Synthesizer)
  nsMasRun: (userInput: { target_organization: string; threat_profile: string; scope_document?: string }) =>
    fetchApi<{ status: string; message?: string; interrupt?: unknown; state?: unknown; result?: unknown }>(
      '/ns-mas/run',
      {
        method: 'POST',
        body: JSON.stringify(userInput),
      }
    ),
  nsMasResume: (approved: boolean, threadId = 'default') =>
    fetchApi<{ status: string; result?: unknown }>(
      `/ns-mas/resume?approved=${approved}&thread_id=${encodeURIComponent(threadId)}`,
      { method: 'POST' }
    ),

  /** Generierte Szenarien (Archiv: evaluation/entwicklung_archiv/interview) */
  getGeneratedScenarios: () =>
    fetchApi<{ scenarios: GeneratedScenarioSummary[] }>('/evaluation/generated'),
  getGeneratedScenario: (id: string) =>
    fetchApi<GeneratedScenarioDetail>('/evaluation/generated/' + encodeURIComponent(id)),
};

export interface GeneratedScenarioSummary {
  id: string;
  label: string;
  mode: string;
  timestamp: string;
  elapsed_seconds?: number;
  validation_passed?: boolean;
  auditor_iterations?: number;
  has_ttp: boolean;
  has_narrative: boolean;
  has_validation: boolean;
}

export interface GeneratedScenarioDetail {
  id: string;
  metadata: Record<string, unknown>;
  ttp: TTPScenario | null;
  narrative: string;
  validation: Record<string, unknown> | null;
  sketch: Record<string, unknown> | null;
}

export interface TTPScenario {
  scenario_id?: string;
  target_organization?: string;
  threat_actor?: string;
  phases?: Array<{
    phase?: string;
    steps?: Array<{
      step_id?: number;
      technique_id?: string;
      technique_name?: string;
      tactic?: string;
      description?: string;
    }>;
    high_level_goals?: string[];
    target_assets?: string[];
  }>;
}
