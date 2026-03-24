'use client';

import { useCouncilStore } from '@/stores/councilStore';
import { Select } from '@/components/ui/Select';
import { AVAILABLE_MODELS, PERSONA_COLORS } from '@/types';
import { getPersonaDisplayName, getPersonaOptions } from '@/lib/personas';
import { XMarkIcon } from '@heroicons/react/24/solid';

interface AgentRowProps {
  index: number;
}

export function AgentRow({ index }: AgentRowProps) {
  const { config, updateAgentConfig, removeAgent } = useCouncilStore();
  const agent = config.agents[index];

  const modelOptions = AVAILABLE_MODELS.map((model) => ({
    value: model,
    label: model,
  }));

  const personaOptions = getPersonaOptions();

  const color = PERSONA_COLORS[agent.persona] || PERSONA_COLORS.the_pragmatist;

  return (
    <div
      className="flex items-center gap-4 p-4 rounded-xl transition-all duration-200"
      style={{
        background: color.bg,
        borderLeft: `4px solid ${color.border}`,
      }}
    >
      <div className="flex-1">
        <label className="block text-label-sm text-on-surface-variant mb-1.5">
          Model
        </label>
        <Select
          value={agent.model}
          onChange={(e) => updateAgentConfig(index, { model: e.target.value })}
          options={modelOptions}
          className="bg-surface-container-highest/80"
        />
      </div>

      <div className="flex-1">
        <label className="block text-label-sm text-on-surface-variant mb-1.5">
          Persona
        </label>
        <Select
          value={agent.persona}
          onChange={(e) => {
            const persona = e.target.value;
            updateAgentConfig(index, {
              persona,
              name: `${getPersonaDisplayName(persona)} (${agent.model})`,
            });
          }}
          options={personaOptions}
          className="bg-surface-container-highest/80"
        />
      </div>

      <div className="flex items-end">
        <button
          onClick={() => removeAgent(index)}
          disabled={config.agents.length <= 2}
          className="p-2.5 rounded-lg text-on-surface-variant hover:text-error hover:bg-error/10 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          title="Remove agent"
        >
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
