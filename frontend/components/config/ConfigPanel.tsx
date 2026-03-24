'use client';

import { useCouncilStore } from '@/stores/councilStore';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Button } from '@/components/ui/Button';
import { Select } from '@/components/ui/Select';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { AgentRow } from './AgentRow';
import { PlusIcon } from '@heroicons/react/24/solid';
import { AVAILABLE_MODELS } from '@/types';

export function ConfigPanel() {
  const {
    config,
    updateConfig,
    addAgent,
    setViewMode,
    resetDiscussion,
    setWsStatus,
  } = useCouncilStore();

  const orchestratorOptions = AVAILABLE_MODELS.map((model) => ({
    value: model,
    label: model,
  }));

  const handleStartDiscussion = () => {
    if (!config.topic.trim() || config.agents.length < 2) return;

    resetDiscussion();
    updateConfig({ session_id: generateSessionId() });
    setViewMode('discussion');
    setWsStatus('connecting');
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-display-md font-bold gradient-text mb-2">
          Configure Your Council
        </h1>
        <p className="text-body-lg text-on-surface-variant">
          Assign personas to models and set discussion parameters
        </p>
      </div>

      {/* LiteLLM Proxy Settings */}
      <Card variant="elevated">
        <CardHeader>
          <CardTitle>LiteLLM Proxy</CardTitle>
          <CardDescription>Configure your proxy endpoint</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Proxy URL"
              value={config.litellm_proxy?.api_base || ''}
              onChange={(e) => updateConfig({
                litellm_proxy: {
                  ...config.litellm_proxy,
                  api_base: e.target.value,
                } as any,
              })}
              placeholder="http://localhost:4000"
            />
            <Input
              label="API Key"
              type="password"
              value={config.litellm_proxy?.api_key || ''}
              onChange={(e) => updateConfig({
                litellm_proxy: {
                  ...config.litellm_proxy,
                  api_key: e.target.value,
                } as any,
              })}
              placeholder="your-api-key"
            />
          </div>
        </CardContent>
      </Card>

      {/* Discussion Settings */}
      <Card variant="elevated">
        <CardHeader>
          <CardTitle>Discussion Settings</CardTitle>
          <CardDescription>Configure the topic and duration</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            label="Topic"
            value={config.topic}
            onChange={(e) => updateConfig({ topic: e.target.value })}
            placeholder="What should the council discuss?"
            rows={3}
          />

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-label-md text-on-surface-variant mb-1.5">
                Max Duration (minutes)
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min="1"
                  max="600"
                  value={config.max_duration_minutes}
                  onChange={(e) => updateConfig({ max_duration_minutes: parseInt(e.target.value) || 1 })}
                  className="w-24 px-3 py-2 bg-surface-container-highest text-on-surface rounded-lg border border-transparent focus:border-primary transition-colors"
                />
                <span className="text-label-md text-on-surface">min</span>
              </div>
              <input
                type="range"
                min="1"
                max="600"
                value={config.max_duration_minutes}
                onChange={(e) => updateConfig({ max_duration_minutes: parseInt(e.target.value) })}
                className="w-full accent-primary mt-2"
              />
              <div className="flex justify-between text-label-xs text-on-surface-variant mt-1">
                <span>1 min</span>
                <span>10 hours max</span>
              </div>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1.5">
                Max Turns
              </label>
              <input
                type="range"
                min="5"
                max="100"
                value={config.max_turns}
                onChange={(e) => updateConfig({ max_turns: parseInt(e.target.value) })}
                className="w-full accent-primary"
              />
              <span className="text-label-md text-on-surface">{config.max_turns}</span>
            </div>

            <div>
              <label className="block text-label-md text-on-surface-variant mb-1.5">
                Segment Threshold
              </label>
              <input
                type="range"
                min="5"
                max="50"
                step="5"
                value={config.context_compression_threshold}
                onChange={(e) => updateConfig({ context_compression_threshold: parseInt(e.target.value) })}
                className="w-full accent-primary"
              />
              <span className="text-label-md text-on-surface">{config.context_compression_threshold} msgs</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Agent Configuration */}
      <Card variant="elevated">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Council Members</CardTitle>
              <CardDescription>Assign personas to models</CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={addAgent}
              disabled={config.agents.length >= 10}
            >
              <PlusIcon className="w-4 h-4 mr-1" />
              Add Agent
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {config.agents.map((_, index) => (
              <AgentRow key={index} index={index} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Orchestrator Settings */}
      <Card variant="elevated">
        <CardHeader>
          <CardTitle>Orchestrator (Manager)</CardTitle>
          <CardDescription>Configure the discussion facilitator</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Orchestrator Model"
              value={config.orchestrator_model}
              onChange={(e) => updateConfig({ orchestrator_model: e.target.value })}
              options={orchestratorOptions}
            />
            <div>
              <label className="block text-label-md text-on-surface-variant mb-1.5">
                Interjection Frequency
              </label>
              <input
                type="range"
                min="1"
                max="10"
                value={config.orchestrator_frequency}
                onChange={(e) => updateConfig({ orchestrator_frequency: parseInt(e.target.value) })}
                className="w-full accent-primary"
              />
              <span className="text-label-md text-on-surface">Every {config.orchestrator_frequency} turns</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Start Button */}
      <div className="flex justify-center pt-4">
        <Button
          variant="primary"
          size="lg"
          onClick={handleStartDiscussion}
          disabled={!config.topic.trim() || config.agents.length < 2}
          className="min-w-[300px]"
        >
          Start Council Discussion
        </Button>
      </div>
    </div>
  );
}

function generateSessionId(): string {
  return new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14);
}
