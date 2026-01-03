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
};

function formatModelLabel(model) {
  return MODEL_LABELS[model] || model;
}

export default function ModelSelector({
  availableModels,
  chairmanModel,
  expertModels,
  minExpertModels,
  onChange,
  disabled,
}) {
  const selectedCount = expertModels.length;
  const isValid = selectedCount >= minExpertModels;

  const handleChairmanChange = (event) => {
    onChange({
      chairmanModel: event.target.value,
      expertModels,
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
          <select
            id="chairman-select"
            value={chairmanModel}
            onChange={handleChairmanChange}
            disabled={disabled}
          >
            {availableModels.map((model) => (
              <option key={model} value={model}>
                {formatModelLabel(model)}
              </option>
            ))}
          </select>
        </div>

        <div className="model-selector-section">
          <div className="model-selector-label">
            Expert models (select any number)
          </div>
          <div className="model-options">
            {availableModels.map((model) => {
              const checked = expertModels.includes(model);
              return (
                <label
                  key={model}
                  className={`model-option ${checked ? 'selected' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleExpert(model)}
                    disabled={disabled}
                  />
                  <span className="model-option-name">{formatModelLabel(model)}</span>
                </label>
              );
            })}
          </div>
          {!isValid && minExpertModels > 0 && (
            <div className="model-selector-hint">
              Select at least {minExpertModels} expert {minExpertModels === 1 ? 'model' : 'models'} to proceed.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
