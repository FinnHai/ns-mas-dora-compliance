import { useEffect, useState } from 'react';
import type { AgentConfigData } from '../api/client';

interface AgentConfigPanelProps {
  config: AgentConfigData | null;
  onChange: (config: AgentConfigData) => void;
}

export function AgentConfigPanel({ config, onChange }: AgentConfigPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [local, setLocal] = useState<AgentConfigData>({
    max_audit_iterations: 5,
    llm_temperature: 0.3,
    min_events: 5,
    max_events: 10,
    kill_chain_order: [
      'initial-access', 'execution', 'persistence', 'privilege-escalation',
      'defense-evasion', 'credential-access', 'discovery', 'lateral-movement',
      'collection', 'command-and-control', 'exfiltration', 'impact',
    ],
    require_tactic_per_event: true,
    generator_system_prompt: null,
  });

  useEffect(() => {
    if (config) {
      setLocal(config);
      onChange(config);
    } else {
      onChange(local);
    }
  }, [config]);

  const update = (next: AgentConfigData) => {
    setLocal(next);
    onChange(next);
  };

  const killChainStr = local.kill_chain_order.join('\n');

  return (
    <div className="agent-config-panel">
      <button
        type="button"
        className="config-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 'Erweiterte Einstellungen ausblenden' : 'Erweiterte Einstellungen'}
        <span className="config-toggle-icon">{expanded ? '−' : '+'}</span>
      </button>
      {expanded && (
        <div className="config-form">
          <div className="form-row">
            <div className="form-group">
              <label>Max. Audit-Iterationen</label>
              <input
                type="number"
                min={1}
                max={20}
                value={local.max_audit_iterations}
                onChange={(e) =>
                  update({ ...local, max_audit_iterations: Number(e.target.value) })
                }
              />
            </div>
            <div className="form-group">
              <label>LLM-Temperatur (0–1)</label>
              <input
                type="number"
                min={0}
                max={1}
                step={0.1}
                value={local.llm_temperature}
                onChange={(e) =>
                  update({ ...local, llm_temperature: parseFloat(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Min. Ereignisse</label>
              <input
                type="number"
                min={1}
                max={50}
                value={local.min_events}
                onChange={(e) =>
                  update({ ...local, min_events: Number(e.target.value) })
                }
              />
            </div>
            <div className="form-group">
              <label>Max. Ereignisse</label>
              <input
                type="number"
                min={1}
                max={50}
                value={local.max_events}
                onChange={(e) =>
                  update({ ...local, max_events: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={local.require_tactic_per_event}
                onChange={(e) =>
                  update({ ...local, require_tactic_per_event: e.target.checked })
                }
              />
              Jedes Ereignis muss Taktik haben
            </label>
          </div>
          <div className="form-group">
            <label>Kill-Chain-Reihenfolge (eine Taktik pro Zeile)</label>
            <textarea
              rows={5}
              value={killChainStr}
                onChange={(e) =>
                  update({
                    ...local,
                    kill_chain_order: e.target.value
                      .split('\n')
                      .map((s) => s.trim().toLowerCase().replace(/\s+/g, '-'))
                      .filter(Boolean),
                  })
                }
              placeholder={'initial-access\nexecution\npersistence\n...'}
            />
          </div>
          <div className="form-group">
            <label>System-Prompt (optional, überschreibt Standard)</label>
            <textarea
              rows={4}
              value={local.generator_system_prompt ?? ''}
                onChange={(e) =>
                  update({
                    ...local,
                    generator_system_prompt: e.target.value || null,
                  })
                }
              placeholder="Leer = Standard-Prompt"
            />
          </div>
          <p className="config-hint">Einstellungen werden automatisch übernommen.</p>
        </div>
      )}
    </div>
  );
}
