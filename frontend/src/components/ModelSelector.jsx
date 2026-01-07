import './ModelSelector.css';

const MODEL_LABELS = {
  'minimax/minimax-m2.1': 'minimax/m2.1',
  'deepseek/deepseek-v3.2': 'deepseek/v3.2',
  'qwen/qwen2.5-vl-72b-instruct': 'qwen/2.5-vl-72b',
  'z-ai/glm-4.7': 'z-ai/glm-4.7',
  'moonshotai/kimi-k2-0905': 'moonshot/kimi-k2',
  'qwen/qwen3-235b-a22b-2507': 'qwen/3-235b',
  'openai/gpt-5.2': 'openai/gpt-5.2',
  'google/gemini-3-flash-preview': 'gemini-3-flash',
  'xiaomi/mimo-v2-flash:free': 'xiaomi/mimo-v2-flash:free',
  'mistralai/devstral-2512:free': 'mistral/devstral-2512',
  'x-ai/grok-4.1-fast': 'x-ai/grok-4.1-fast',
};

function formatModelLabel(model) {
  return MODEL_LABELS[model] || model;
}

export default function ModelSelector({
  availableModels,
  chairmanModel,
  expertModels,
  minExpertModels,
  thinkingByModel,
  thinkingSupportedModels,
  reasoningEffortModels,
  reasoningMaxTokensModels,
  reasoningEffortLevels,
  reasoningMaxTokensMin,
  reasoningMaxTokensMax,
  defaultReasoningEffort,
  defaultReasoningMaxTokens,
  onChange,
  disabled,
}) {
  const selectedCount = expertModels.length;
  const isValid = selectedCount >= minExpertModels;
  const supportedSet = new Set(thinkingSupportedModels || []);
  const effortSet = new Set(reasoningEffortModels || []);
  const maxTokensSet = new Set(reasoningMaxTokensModels || []);
  const isThinkingSupported = (model) => (thinkingSupportedModels ? supportedSet.has(model) : true);
  const isThinkingEnabled = (model) => {
    const value = thinkingByModel?.[model];
    if (!value) return false;
    if (typeof value === 'object') {
      return value.enabled !== false;
    }
    return Boolean(value);
  };
  const isMaxTokensModel = (model) => maxTokensSet.has(model);
  const isEffortModel = (model) => {
    if (effortSet.size) {
      return effortSet.has(model);
    }
    return isThinkingSupported(model) && !isMaxTokensModel(model);
  };
  const getThinkingConfig = (model) => {
    const value = thinkingByModel?.[model];
    if (!value) return null;
    if (typeof value === 'object') return value;
    return { enabled: true };
  };
  const getDefaultConfig = (model) => {
    if (isMaxTokensModel(model)) {
      return { max_tokens: defaultReasoningMaxTokens || 2000 };
    }
    if (isEffortModel(model)) {
      return { effort: defaultReasoningEffort || 'medium' };
    }
    return {};
  };
  const selectedSupportedCount = [chairmanModel, ...expertModels]
    .filter((model, index, arr) => arr.indexOf(model) === index)
    .filter((model) => isThinkingSupported(model) && isThinkingEnabled(model)).length;

  const handleChairmanChange = (event) => {
    onChange({
      chairmanModel: event.target.value,
      expertModels,
      thinkingByModel,
    });
  };

  const toggleExpert = (model) => {
    const next = new Set(expertModels);
    if (next.has(model)) {
      next.delete(model);
    } else {
      next.add(model);
    }

    const ordered = availableModels.filter((item) => next.has(item));
    onChange({
      chairmanModel,
      expertModels: ordered,
      thinkingByModel,
    });
  };

  const handleThinkingToggle = (model, enabled) => {
    const next = { ...(thinkingByModel || {}) };
    if (enabled) {
      next[model] = getThinkingConfig(model) || getDefaultConfig(model) || true;
    } else {
      delete next[model];
    }
    onChange({
      chairmanModel,
      expertModels,
      thinkingByModel: next,
    });
  };

  const updateThinkingConfig = (model, updates) => {
    const next = { ...(thinkingByModel || {}) };
    const current = getThinkingConfig(model) || getDefaultConfig(model);
    next[model] = { ...current, ...updates, enabled: true };
    onChange({
      chairmanModel,
      expertModels,
      thinkingByModel: next,
    });
  };

  return (
    <div className="model-selector">
      <div className="model-selector-header">
        <span className="model-selector-title">Model Selection</span>
        <span className={`model-selector-count ${isValid ? 'ok' : 'error'}`}>
          {selectedCount} selected
        </span>
      </div>

      <div className="model-selector-body">
        <div className="model-selector-section">
          <label className="model-selector-label" htmlFor="chairman-select">
            Chairman model
          </label>
          <div className="model-selector-row">
            <select
              id="chairman-select"
              value={chairmanModel}
              onChange={handleChairmanChange}
              disabled={disabled}
            >
              <option value="" disabled>
                Select a chairman model
              </option>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {formatModelLabel(model)}
                </option>
              ))}
            </select>
            <label
              className={`switch ${disabled || !isThinkingSupported(chairmanModel) ? 'disabled' : ''}`}
              title={isThinkingSupported(chairmanModel) ? 'Enable reasoning for this model' : 'Thinking not supported'}
            >
              <input
                type="checkbox"
                checked={isThinkingEnabled(chairmanModel)}
                onChange={(event) => handleThinkingToggle(chairmanModel, event.target.checked)}
                disabled={disabled || !isThinkingSupported(chairmanModel)}
              />
              <span className="switch-track">
                <span className="switch-thumb" />
              </span>
              <span className="switch-label">Thinking</span>
            </label>
          </div>
          <div className="model-selector-support">
            {isThinkingSupported(chairmanModel)
              ? 'Thinking available for the selected chairman.'
              : 'Thinking not available for the selected chairman.'}
          </div>
          {isThinkingSupported(chairmanModel) && isThinkingEnabled(chairmanModel) && (
            <div className="model-option-settings">
              {isEffortModel(chairmanModel) && (
                <label className="model-option-setting">
                  <span>Effort</span>
                  <select
                    value={getThinkingConfig(chairmanModel)?.effort || defaultReasoningEffort || 'medium'}
                    onChange={(event) => updateThinkingConfig(chairmanModel, { effort: event.target.value })}
                    disabled={disabled}
                  >
                    {(reasoningEffortLevels || ['minimal', 'low', 'medium', 'high', 'xhigh']).map((level) => (
                      <option key={level} value={level}>
                        {level}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {isMaxTokensModel(chairmanModel) && (
                <label className="model-option-setting">
                  <span>Reasoning tokens</span>
                  <input
                    type="number"
                    value={getThinkingConfig(chairmanModel)?.max_tokens || defaultReasoningMaxTokens || 2000}
                    min={reasoningMaxTokensMin || 256}
                    max={reasoningMaxTokensMax || 8000}
                    step="256"
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      if (!Number.isNaN(value)) {
                        updateThinkingConfig(chairmanModel, { max_tokens: value });
                      }
                    }}
                    disabled={disabled}
                  />
                </label>
              )}
              <label className="model-option-setting checkbox">
                <input
                  type="checkbox"
                  checked={Boolean(getThinkingConfig(chairmanModel)?.exclude)}
                  onChange={(event) => updateThinkingConfig(chairmanModel, { exclude: event.target.checked })}
                  disabled={disabled}
                />
                <span>Hide reasoning tokens</span>
              </label>
            </div>
          )}
        </div>

        <div className="model-selector-section">
          <div className="model-selector-label-row">
            <div className="model-selector-label">Expert models</div>
            <div className="model-selector-meta">Select any number (models repeat if fewer than 6).</div>
          </div>
          <div className="model-options">
            {availableModels.map((model) => {
              const checked = expertModels.includes(model);
              const supported = isThinkingSupported(model);
              const toggleDisabled = disabled || !checked || !supported;
              return (
                <div
                  key={model}
                  className={`model-option ${checked ? 'selected' : ''}`}
                >
                  <label className="model-option-main">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleExpert(model)}
                      disabled={disabled}
                    />
                    <span className="model-option-name">{formatModelLabel(model)}</span>
                    <span className={`model-option-badge ${supported ? 'supported' : 'unsupported'}`}>
                      {supported ? 'Thinking' : 'No thinking'}
                    </span>
                  </label>
                  <div className="model-option-controls">
                    <label
                      className={`switch ${toggleDisabled ? 'disabled' : ''}`}
                      title={
                        !supported
                          ? 'Thinking not supported'
                          : checked
                            ? 'Enable reasoning for this model'
                            : 'Select model to enable thinking'
                      }
                    >
                      <input
                        type="checkbox"
                        checked={isThinkingEnabled(model)}
                        onChange={(event) => handleThinkingToggle(model, event.target.checked)}
                        disabled={toggleDisabled}
                      />
                      <span className="switch-track">
                        <span className="switch-thumb" />
                      </span>
                      <span className="switch-label">Thinking</span>
                    </label>
                  </div>
                  {checked && isThinkingSupported(model) && isThinkingEnabled(model) && (
                    <div className="model-option-settings">
                      {isEffortModel(model) && (
                        <label className="model-option-setting">
                          <span>Effort</span>
                          <select
                            value={getThinkingConfig(model)?.effort || defaultReasoningEffort || 'medium'}
                            onChange={(event) => updateThinkingConfig(model, { effort: event.target.value })}
                            disabled={disabled}
                          >
                            {(reasoningEffortLevels || ['minimal', 'low', 'medium', 'high', 'xhigh']).map((level) => (
                              <option key={level} value={level}>
                                {level}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      {isMaxTokensModel(model) && (
                        <label className="model-option-setting">
                          <span>Reasoning tokens</span>
                          <input
                            type="number"
                            value={getThinkingConfig(model)?.max_tokens || defaultReasoningMaxTokens || 2000}
                            min={reasoningMaxTokensMin || 256}
                            max={reasoningMaxTokensMax || 8000}
                            step="256"
                            onChange={(event) => {
                              const value = Number(event.target.value);
                              if (!Number.isNaN(value)) {
                                updateThinkingConfig(model, { max_tokens: value });
                              }
                            }}
                            disabled={disabled}
                          />
                        </label>
                      )}
                      <label className="model-option-setting checkbox">
                        <input
                          type="checkbox"
                          checked={Boolean(getThinkingConfig(model)?.exclude)}
                          onChange={(event) => updateThinkingConfig(model, { exclude: event.target.checked })}
                          disabled={disabled}
                        />
                        <span>Hide reasoning tokens</span>
                      </label>
                    </div>
                  )}
                </div>
            );
          })}
          </div>
          {!isValid && minExpertModels > 0 && (
            <div className="model-selector-hint error">
              Select at least {minExpertModels} expert {minExpertModels === 1 ? 'model' : 'models'} to proceed.
            </div>
          )}
        </div>
        <div className="model-selector-hint">
          Thinking toggles apply per model and only work on supported models.
        </div>
        {thinkingSupportedModels && (
          <div className="model-selector-hint">
            Thinking enabled for {selectedSupportedCount} selected model{selectedSupportedCount === 1 ? '' : 's'}.
          </div>
        )}
      </div>
    </div>
  );
}
