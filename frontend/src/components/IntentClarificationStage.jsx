import { Children, isValidElement, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { HelpCircle, Target, Compass, Lightbulb, AlertTriangle, CheckCircle2 } from 'lucide-react';
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

  const toText = (value, options = {}) => {
    const { includeWhy = true, preferKeys } = options;
    if (value === null || value === undefined) return '';
    if (typeof value === 'string' || typeof value === 'number') return String(value).trim();
    if (typeof value === 'object') {
      const assumptionText = typeof value.assumption === 'string' ? value.assumption.trim() : '';
      const why = typeof value.why_it_matters === 'string' ? value.why_it_matters.trim() : '';
      if (includeWhy && assumptionText && why) {
        return `${assumptionText} (why it matters: ${why})`;
      }
      const directKeys = preferKeys || ['text', 'summary', 'title', 'label', 'description', 'reason', 'detail', 'value'];
      for (const key of directKeys) {
        const candidate = typeof value[key] === 'string' ? value[key].trim() : '';
        if (candidate) return candidate;
      }
      const parts = Object.entries(value)
        .map(([key, item]) => {
          if (typeof item === 'string' || typeof item === 'number') {
            return `${key}: ${String(item).trim()}`;
          }
          return '';
        })
        .filter(Boolean);
      if (parts.length > 0) return parts.join('; ');
    }
    return '';
  };

  const normalizeList = (items, options = {}) => {
    if (!Array.isArray(items)) return [];
    return items.map((item) => toText(item, options)).filter(Boolean);
  };

  const unclearDisplay = normalizeList(display?.unclear);
  const reconstructedAsk = typeof display?.reconstructed_ask === 'string' && display.reconstructed_ask.trim()
    ? display.reconstructed_ask.trim()
    : '';
  const deepRead = typeof display?.deep_read === 'string' && display.deep_read.trim()
    ? display.deep_read.trim()
    : '';
  const decisionFocus = typeof display?.decision_focus === 'string' && display.decision_focus.trim()
    ? display.decision_focus.trim()
    : '';
  const displayMarkdown = typeof display?.markdown === 'string' && display.markdown.trim()
    ? display.markdown.trim()
    : '';
  const cleanedMarkdown = useMemo(() => {
    if (!displayMarkdown) return '';
    const stripped = displayMarkdown.replace(/<[^>]+>/g, '').trim();
    return stripped || '';
  }, [displayMarkdown]);

  const latentHypotheses = normalizeList(draftIntent?.latent_intent_hypotheses);
  const ambiguities = normalizeList(draftIntent?.ambiguities);
  const assumptions = Array.isArray(draftIntent?.assumptions) ? draftIntent.assumptions : [];

  const assumptionDisplay = normalizeList(display?.assumptions, { preferKeys: ['assumption', 'text', 'summary', 'title', 'label', 'description'] });
  const assumptionItems = assumptionDisplay.length > 0
    ? assumptionDisplay
    : assumptions.map((item) => {
        const base = toText(item, {
          includeWhy: false,
          preferKeys: ['assumption', 'text', 'summary', 'title', 'label', 'description'],
        });
        if (!base) return '';
        if (typeof item === 'object' && item && typeof item.why_it_matters === 'string' && item.why_it_matters.trim()) {
          return `${base} (why it matters: ${item.why_it_matters.trim()})`;
        }
        return `${base} (why it matters: it can change the scope or solution)`;
      }).filter(Boolean);

  const understandingItems = normalizeList(display?.understanding);
  const fallbackUnderstanding = understandingItems.length > 0 ? understandingItems : latentHypotheses;

  const openItemsRaw = [...unclearDisplay, ...ambiguities];
  const openItems = Array.from(new Set(openItemsRaw.filter(Boolean)));
  const explicitConstraints = Array.isArray(draftIntent?.explicit_constraints)
    ? draftIntent.explicit_constraints
    : [];
  const primaryAskContext = [
    draftIntent?.audience ? `Audience: ${draftIntent.audience}` : '',
    explicitConstraints.length > 0 ? `Constraints: ${explicitConstraints.join('; ')}` : '',
  ].filter(Boolean);
  const primaryAskLine = draftIntent?.primary_intent
    ? `${draftIntent.primary_intent}${primaryAskContext.length ? ` (${primaryAskContext.join(' | ')})` : ''}`
    : 'Not specified yet';

  const intentMarkdown = useMemo(() => {
    if (cleanedMarkdown) {
      return cleanedMarkdown;
    }
    const toParagraph = (items) => {
      if (!items || items.length === 0) {
        return '';
      }
      return items
        .map((item) => (/[.!?]$/.test(item.trim()) ? item.trim() : `${item.trim()}.`))
        .join(' ');
    };

    const fallbackDeepReadParts = [
      toParagraph(fallbackUnderstanding),
      toParagraph(assumptionItems),
      toParagraph(openItems),
    ].filter(Boolean);
    const fallbackDeepRead = fallbackDeepReadParts.join('\n\n');
    const deepReadText = deepRead || fallbackDeepRead || primaryAskLine;
    const askText = reconstructedAsk || deepReadText.split('\n')[0].trim() || primaryAskLine;
    const ambiguityText = openItems.length > 0
      ? `Key uncertainties include ${openItems.join('; ')}.`
      : '';
    const decisionText = decisionFocus || ambiguityText || 'Confirm the most important tradeoff before proceeding.';

    return [
      '### Your Request, Refined',
      askText,
      '',
      '### Deep Intent Read',
      deepReadText,
      '',
      '### Ambiguities and Areas to Clarify',
      decisionText,
    ].join('\n');
  }, [cleanedMarkdown, reconstructedAsk, primaryAskLine, deepRead, decisionFocus, fallbackUnderstanding, assumptionItems, openItems]);

  const flattenText = (node) => {
    const parts = [];
    Children.forEach(node, (child) => {
      if (typeof child === 'string' || typeof child === 'number') {
        parts.push(String(child));
      } else if (isValidElement(child)) {
        parts.push(flattenText(child.props.children));
      }
    });
    return parts.join('');
  };

  const renderHeader = ({ children, level }) => {
    const cleanText = flattenText(children)
      .replace(/^\s*[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '')
      .replace(/^\s*#{1,6}\s*/, '')
      .trim();

    let Icon = Target;
    if (cleanText.includes('Your Request') || cleanText.includes('Reconstructed Ask')) Icon = Target;
    else if (cleanText.includes('Deep Intent') || cleanText.includes('Key Interpretation')) Icon = Compass;
    else if (cleanText.includes('Ambiguities') || cleanText.includes('Areas to Clarify') || cleanText.includes('Where We Might Be Off') || cleanText.includes('Critical Ambiguities')) Icon = AlertTriangle;
    else if (cleanText.includes('Assumptions')) Icon = Lightbulb;

    const Tag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3';

    return (
      <Tag className="markdown-header-with-icon" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', marginBottom: '6px' }}>
        <Icon size={18} style={{ color: 'var(--color-primary)' }} />
        {cleanText}
      </Tag>
    );
  };

  const renderSubHeader = ({ children }) => {
    const cleanText = flattenText(children)
      .replace(/^\s*[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '')
      .replace(/^\s*#{1,6}\s*/, '')
      .trim();
    return <h4 className="intent-subheader">{cleanText}</h4>;
  };

  const markdownComponents = {
    h1(props) {
      return renderHeader({ ...props, level: 1 });
    },
    h2(props) {
      return renderHeader({ ...props, level: 2 });
    },
    h3(props) {
      return renderHeader({ ...props, level: 3 });
    },
    h4(props) {
      return renderSubHeader(props);
    },
  };

  return (
    <div className="stage intent-clarification-stage">
      <h3 className="stage-title">
        <HelpCircle size={18} />
        Intent Understanding
      </h3>

      <div className="intent-analysis">
        <div className="analysis-content markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {intentMarkdown}
          </ReactMarkdown>
        </div>
      </div>

      {awaitingClarification ? (
        <div className="intent-questions">
          <div className="intent-questions-header">
            <div className="intent-section-title">Critical clarifying questions (optional)</div>
            <div className="intent-helper-text">
              Answer any that matter. You can also skip all questions to proceed.
            </div>
          </div>
          {(questions || []).length === 0 && (
            <div className="intent-empty">No clarification questions were generated for this request.</div>
          )}
          {(questions || []).map((question) => (
            <div key={question.id} className="intent-question">
              <div className="intent-question-text">{question.question}</div>
              <div className="intent-options">
                {(question.options || []).map((option) => (
                  <label key={`${question.id}-${option}`} className="intent-option">
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
