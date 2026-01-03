import { useEffect, useMemo, useState } from 'react';
import { HelpCircle, CheckCircle2 } from 'lucide-react';
import './IntentClarificationStage.css';

export default function IntentClarificationStage({
  display,
  draftIntent,
  questions,
  awaitingClarification,
  clarificationAnswers,
  onSubmit,
  disabled,
}) {
  const initialAnswers = useMemo(() => {
    const base = {};
    (questions || []).forEach((question) => {
      base[question.id] = { selectedOptions: [], otherText: '' };
    });
    return base;
  }, [questions]);

  const [answers, setAnswers] = useState(initialAnswers);
  const [freeText, setFreeText] = useState('');

  useEffect(() => {
    setAnswers(initialAnswers);
  }, [initialAnswers]);

  useEffect(() => {
    setFreeText('');
  }, [questions]);

  const handleToggleOption = (questionId, option) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        selectedOptions: prev[questionId]?.selectedOptions?.includes(option)
          ? prev[questionId].selectedOptions.filter((item) => item !== option)
          : [...(prev[questionId]?.selectedOptions || []), option],
        otherText: option === "Other / I'll type it" && prev[questionId]?.selectedOptions?.includes(option)
          ? ''
          : (prev[questionId]?.otherText || ''),
      },
    }));
  };

  const handleOtherText = (questionId, value) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        selectedOptions: prev[questionId]?.selectedOptions?.includes("Other / I'll type it")
          ? prev[questionId]?.selectedOptions || []
          : [...(prev[questionId]?.selectedOptions || []), "Other / I'll type it"],
        otherText: value,
      },
    }));
  };

  const hasAnyAnswer = (questions || []).some(
    (question) => (answers[question.id]?.selectedOptions || []).length > 0
  );
  const hasFreeText = freeText.trim().length > 0;

  const buildPayload = (skipOverride) => {
    const shouldSkip = skipOverride || (!hasAnyAnswer && !hasFreeText);
    return {
      skip: shouldSkip,
      answers: (questions || []).map((question) => ({
        question_id: question.id,
        selected_options: answers[question.id]?.selectedOptions || [],
        other_text: answers[question.id]?.selectedOptions?.includes("Other / I'll type it")
          ? (answers[question.id]?.otherText || '')
          : '',
      })),
      free_text: freeText,
    };
  };

  const unclearDisplay = Array.isArray(display?.unclear) ? display.unclear : [];

  const successCriteria = Array.isArray(draftIntent?.success_criteria)
    ? draftIntent.success_criteria
    : [];
  const latentHypotheses = Array.isArray(draftIntent?.latent_intent_hypotheses)
    ? draftIntent.latent_intent_hypotheses
    : [];
  const ambiguities = Array.isArray(draftIntent?.ambiguities)
    ? draftIntent.ambiguities
    : [];
  const assumptions = Array.isArray(draftIntent?.assumptions)
    ? draftIntent.assumptions
    : [];

  const limitList = (list, limit = 4) => {
    const trimmed = list.slice(0, limit);
    const remaining = list.length - trimmed.length;
    if (remaining > 0) {
      trimmed.push(`+${remaining} more`);
    }
    return trimmed;
  };

  const assumptionItems = limitList(
    assumptions.map((item) => {
      if (typeof item === 'string') {
        return `${item} (why it matters: it can change the scope or solution)`;
      }
      const assumptionText = item.assumption || '';
      const why = item.why_it_matters || (item.risk ? `risk level: ${item.risk}` : '');
      if (!why) {
        return `${assumptionText} (why it matters: it can change the scope or solution)`;
      }
      return `${assumptionText} (why it matters: ${why})`;
    }),
    3
  );

  const hypothesisItems = limitList(latentHypotheses, 3);

  const openItemsRaw = [...unclearDisplay, ...ambiguities];
  const openItems = limitList(
    Array.from(new Set(openItemsRaw.filter(Boolean))),
    4
  );
  const successItems = limitList(successCriteria, 4);

  const explicitConstraints = Array.isArray(draftIntent?.explicit_constraints)
    ? draftIntent.explicit_constraints
    : [];
  const primaryAskContext = [
    draftIntent?.audience ? `Audience: ${draftIntent.audience}` : '',
    explicitConstraints.length > 0 ? `Constraints: ${explicitConstraints.slice(0, 2).join('; ')}` : '',
  ].filter(Boolean);
  const primaryAskLine = draftIntent?.primary_intent
    ? `${draftIntent.primary_intent}${primaryAskContext.length ? ` (${primaryAskContext.join(' | ')})` : ''}`
    : 'Not specified yet';

  const impliedSuccessLine = successItems.length > 0
    ? successItems.join('; ')
    : 'Not specified yet';

  return (
    <div className="stage intent-clarification-stage">
      <h3 className="stage-title">
        <HelpCircle size={18} />
        Intent Understanding
      </h3>

      <div className="intent-section">
        <div className="intent-section-title">Explicit intent</div>
        <ul>
          <li><span className="intent-label">Primary ask:</span> {primaryAskLine}</li>
          <li><span className="intent-label">Implied success criteria:</span> {impliedSuccessLine}</li>
        </ul>
      </div>

      <div className="intent-section">
        <div className="intent-section-title">Likely latent intent</div>
        {hypothesisItems.length > 0 ? (
          <ul>
            {hypothesisItems.map((item, idx) => (
              <li key={`latent-${idx}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <div className="intent-empty">No strong latent intent inferred yet.</div>
        )}
      </div>

      <div className="intent-section">
        <div className="intent-section-title">Hidden assumptions (and why they matter)</div>
        {assumptionItems.length > 0 ? (
          <ul>
            {assumptionItems.map((item, idx) => (
              <li key={`assumption-${idx}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <div className="intent-empty">No major assumptions noted yet.</div>
        )}
      </div>

      <div className="intent-section">
        <div className="intent-section-title">Critical ambiguities / scope gaps</div>
        {openItems.length > 0 ? (
          <ul>
            {openItems.map((item, idx) => (
              <li key={`open-${idx}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <div className="intent-empty">No critical gaps flagged yet.</div>
        )}
      </div>

      {awaitingClarification ? (
        <div className="intent-questions">
          <div className="intent-questions-header">
            <div className="intent-section-title">Critical clarifying questions (optional)</div>
            <div className="intent-helper-text">
              Answer any that matter. You can also skip all questions to proceed.
            </div>
          </div>
          {(questions || []).map((question) => (
            <div key={question.id} className="intent-question">
              <div className="intent-question-text">{question.question}</div>
              <div className="intent-options">
                {(question.options || []).map((option) => (
                  <label key={option} className="intent-option">
                    <input
                      type="checkbox"
                      name={question.id}
                      value={option}
                      checked={answers[question.id]?.selectedOptions?.includes(option)}
                      onChange={() => handleToggleOption(question.id, option)}
                      disabled={disabled}
                    />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
              {answers[question.id]?.selectedOptions?.includes("Other / I'll type it") && (
                <input
                  className="intent-other-input"
                  type="text"
                  placeholder="Type your answer"
                  value={answers[question.id]?.otherText || ''}
                  onChange={(event) => handleOtherText(question.id, event.target.value)}
                  disabled={disabled}
                />
              )}
            </div>
          ))}

          <div className="intent-free-text">
            <label htmlFor="intent-free-text">
              Anything else that would help me get this right? (optional)
            </label>
            <textarea
              id="intent-free-text"
              rows={3}
              value={freeText}
              onChange={(event) => setFreeText(event.target.value)}
              disabled={disabled}
            />
          </div>

          <div className="intent-actions">
            <button
              type="button"
              className="intent-skip-button"
              onClick={() => onSubmit(buildPayload(true))}
              disabled={disabled}
            >
              Skip all questions
            </button>
            <button
              type="button"
              className="intent-continue-button"
              onClick={() => onSubmit(buildPayload(false))}
              disabled={disabled}
            >
              Continue
            </button>
          </div>
        </div>
      ) : (
        <div className="intent-submitted">
          <CheckCircle2 size={18} />
          <span>Clarifications submitted. Continuing with final intent analysis.</span>
        </div>
      )}

      {clarificationAnswers?.skip && (
        <div className="intent-skip-note">You chose to skip clarifications.</div>
      )}
    </div>
  );
}
