import { useState, useEffect, useRef, Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ClipboardList, PenTool, BrainCircuit, CheckCircle2, Target, Ruler, Mic, MessageCircle, AlertTriangle, Gem, Hash, Compass, Sparkles, Gavel, SlidersHorizontal } from 'lucide-react';
import Stage0 from './Stage0';
import ContributionsStage from './ContributionsStage';
import Stage3 from './Stage3';
import ModelSelector from './ModelSelector';
import IntentClarificationStage from './IntentClarificationStage';
import { normalizeMarkdownTables } from '../utils/markdown';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  onContinueMessage,
  onNewConversation,
  isLoading,
  modelCatalog,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const [chairmanModel, setChairmanModel] = useState('');
  const [expertModels, setExpertModels] = useState([]);
  const [thinkingByModel, setThinkingByModel] = useState({});
  const [selectionLocked, setSelectionLocked] = useState(false);
  const [hasEditedSelection, setHasEditedSelection] = useState(false);

  const fallbackAvailableModels = [
    'minimax/minimax-m2.1',
    'deepseek/deepseek-v3.2',
    'qwen/qwen2.5-vl-72b-instruct',
    'z-ai/glm-4.7',
    'moonshotai/kimi-k2-0905',
    'qwen/qwen3-235b-a22b-2507',
    'openai/gpt-5.2',
    'google/gemini-3-flash-preview',
    'xiaomi/mimo-v2-flash:free',
    'mistralai/devstral-2512:free',
  ];

  const availableModels = modelCatalog?.available_models || fallbackAvailableModels;
  const minExpertModels = modelCatalog?.min_expert_models || 1;
  useEffect(() => {
    if (!conversation) return;
    setHasEditedSelection(false);
  }, [conversation?.id]);

  useEffect(() => {
    if (!conversation) return;

    const selectionFromConversation = [...conversation.messages]
      .reverse()
      .find((msg) => msg?.metadata?.model_selection)?.metadata?.model_selection;

    if (selectionFromConversation) {
      setChairmanModel(selectionFromConversation.chairman_model);
      setExpertModels(selectionFromConversation.expert_models);
      if (selectionFromConversation.thinking_by_model) {
        setThinkingByModel(selectionFromConversation.thinking_by_model);
      } else if (selectionFromConversation.thinking_enabled) {
        const selectedModels = [
          selectionFromConversation.chairman_model,
          ...(selectionFromConversation.expert_models || []),
        ];
        const next = {};
        selectedModels.forEach((model) => {
          next[model] = true;
        });
        setThinkingByModel(next);
      } else {
        setThinkingByModel({});
      }
      setSelectionLocked(true);
      return;
    }

    setSelectionLocked(false);
    if (hasEditedSelection) return;

    setChairmanModel('');
    setExpertModels([]);
    setThinkingByModel({});
  }, [conversation, hasEditedSelection]);

  const isSelectionValid = expertModels.length >= minExpertModels && chairmanModel;
  const modelSelectionPayload = isSelectionValid
    ? { chairman_model: chairmanModel, expert_models: expertModels, thinking_by_model: thinkingByModel }
    : null;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading && isSelectionValid) {
      onSendMessage(input, modelSelectionPayload);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const hasChairmanOutput = conversation?.messages?.some((msg) => msg?.stage3?.response);
  const inputPlaceholder = hasChairmanOutput
    ? 'Add instructions to evolve the Chairman output...'
    : 'Ask a question...';

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

  const normalizeHeadingText = (children) => (
    flattenText(children)
      .replace(/^\s*[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '')
      .replace(/^\s*#{1,6}\s*/, '')
      .trim()
  );

  const markdownComponents = {
    h1({ children }) {
      return <h1>{normalizeHeadingText(children)}</h1>;
    },
    h2({ children }) {
      return <h2>{normalizeHeadingText(children)}</h2>;
    },
    code({ inline, className, children, ...props }) {
      return inline ? (
        <code className="inline-code" {...props}>{children}</code>
      ) : (
        <pre className="code-block">
          <code className={className} {...props}>{children}</code>
        </pre>
      );
    },
    table({ children }) {
      return (
        <div className="table-wrapper">
          <table>{children}</table>
        </div>
      );
    },
    blockquote({ children }) {
      return <blockquote className="styled-blockquote">{children}</blockquote>;
    },
    a({ href, children }) {
      return <a href={href} target="_blank" rel="noopener noreferrer" className="styled-link">{children}</a>;
    },
    h3({ children }) {
      // Strip leading emojis or symbols and accidental markdown markers
      const cleanText = normalizeHeadingText(children);

      let Icon = Sparkles;
      if (cleanText.includes('Audience')) Icon = Target;
      else if (cleanText.includes('Style')) Icon = PenTool;
      else if (cleanText.includes('Formatting')) Icon = Ruler;
      else if (cleanText.includes('Voice')) Icon = Mic;
      else if (cleanText.includes('Tone')) Icon = MessageCircle;
      else if (cleanText.includes('Anti-Patterns')) Icon = AlertTriangle;
      else if (cleanText.includes('Quality')) Icon = Gem;
      else if (cleanText.includes('Intent')) Icon = Target;
      else if (cleanText.includes('Dimensions')) Icon = Compass;
      else if (cleanText.includes('Claim')) Icon = CheckCircle2;
      else if (cleanText.includes('Verdict')) Icon = Gavel;

      return (
        <h3 className="markdown-header-with-icon" style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', lineHeight: '1.4' }}>
          <Icon size={20} className="header-icon" style={{ marginTop: '3px', flexShrink: 0 }} />
          <span>{cleanText}</span>
        </h3>
      );
    }
  };

  const normalizeBrainstormContent = (content) => {
    if (!content) return '';
    const text = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
    return text
      .replace(/^##\s+Expert Brainstorm Results\s*/i, '')
      .replace(/\n-{3,}\n/g, '\n\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  };

  const formatModelLabel = (model) => {
    const labelMap = {
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
    };

    return labelMap[model] || model;
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => {
            const expertList = msg.experts
              || (Array.isArray(msg.stage0?.first_expert) ? msg.stage0.first_expert : null);
            const contributionList = msg.contributions || msg.debate || [];
            const awaitingClarification = msg.awaiting_clarification ?? (msg.status === 'clarification_pending');
            const clarificationAnswers = msg.clarification_answers || msg.metadata?.clarification_answers;
            const intentDisplay = msg.intent_display ?? msg.intent_draft?.display;
            const draftIntent = msg.intent_draft?.draft_intent || msg.intent_draft;
            const showClarificationStage = Boolean(
              msg.intent_draft
              || msg.intent_display
              || (msg.clarification_questions && msg.clarification_questions.length > 0)
              || msg.status?.startsWith('clarification')
            );

            return (
              <div key={index} className="message-group">
                {msg.role === 'user' ? (
                  <div className="user-message">
                    <div className="message-label">You</div>
                    <div className="message-content">
                      <div className="markdown-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="assistant-message">
                    <div className="message-label">LLM Council</div>

                    {msg.metadata?.model_selection && (
                      <div className="stage model-selection-stage">
                        <h3 className="stage-title">
                          <SlidersHorizontal size={18} />
                          Model Selection
                        </h3>
                        <div className="model-selection-summary">
                          {(() => {
                            const thinkingMap = msg.metadata.model_selection.thinking_by_model || {};
                            const thinkingModels = Object.keys(thinkingMap).filter((model) => thinkingMap[model]);
                            return (
                              <>
                                <div className="model-selection-group">
                                  <div className="model-selection-label">Chairman</div>
                                  <div className="model-selection-pill">
                                    {formatModelLabel(msg.metadata.model_selection.chairman_model)}
                                  </div>
                                </div>
                                <div className="model-selection-group">
                                  <div className="model-selection-label">Experts</div>
                                  <div className="model-selection-pills">
                                    {msg.metadata.model_selection.expert_models.map((model) => (
                                      <span key={model} className="model-selection-pill">
                                        {formatModelLabel(model)}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                                <div className="model-selection-group">
                                  <div className="model-selection-label">Thinking</div>
                                  {thinkingModels.length ? (
                                    <div className="model-selection-pills">
                                      {thinkingModels.map((model) => (
                                        <span key={model} className="model-selection-pill">
                                          {formatModelLabel(model)}
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    <div className="model-selection-pill">Off</div>
                                  )}
                                </div>
                              </>
                            );
                          })()}
                        </div>
                      </div>
                    )}

                    {msg.loading?.intent_draft && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Drafting intent understanding...</span>
                      </div>
                    )}

                    {showClarificationStage && (
                      <IntentClarificationStage
                        display={intentDisplay}
                        draftIntent={draftIntent}
                        questions={msg.clarification_questions}
                        awaitingClarification={awaitingClarification}
                        clarificationAnswers={clarificationAnswers}
                        onSubmit={onContinueMessage}
                        disabled={isLoading}
                      />
                    )}

                    {/* Stage 0: Intent Analysis */}
                    {msg.loading?.stage0 && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Preparing intent brief...</span>
                      </div>
                    )}
                    {msg.stage0 && <Stage0 data={msg.stage0} experts={expertList} />}

                    {/* Brainstorm Stage */}
                    {(msg.loading?.brainstorm || msg.brainstorm_content) && (
                      <div className="stage brainstorm-stage">
                        <h3 className="stage-title">
                          <BrainCircuit size={18} />
                          Expert Brainstorm
                        </h3>
                        {msg.loading?.brainstorm ? (
                          <div className="stage-loading">
                            <div className="spinner"></div>
                            <span>All models brainstorming expert team...</span>
                          </div>
                        ) : (
                            <div className="brainstorm-report">
                              <div className="report-content markdown-content">
                                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                                {normalizeBrainstormContent(msg.brainstorm_content)}
                                </ReactMarkdown>
                              </div>
                            </div>
                        )}
                      </div>
                    )}

                    {/* Expert Contributions */}
                    {(msg.loading?.contributions || contributionList.length > 0) && (
                      <ContributionsStage
                        contributions={contributionList}
                        loading={msg.loading?.contributions}
                        currentOrder={msg.loading?.currentOrder || 0}
                      />
                    )}

                    {/* Verification */}
                    {(msg.loading?.verification || msg.metadata?.verification_data) && (
                      <div className="stage verification-stage">
                        <h3 className="stage-title">
                          <CheckCircle2 size={18} />
                          Factual Verification
                        </h3>
                        {msg.loading?.verification ? (
                          <div className="stage-loading">
                            <div className="spinner"></div>
                            <span>Verifying expert contributions...</span>
                          </div>
                        ) : (
                          <div className="verification-report">
                            <div className="report-content markdown-content">
                              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                                {normalizeMarkdownTables(msg.metadata.verification_data)}
                              </ReactMarkdown>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                  {/* Synthesis Planning */}
                  {(msg.loading?.planning || msg.metadata?.synthesis_plan) && (
                    <div className="stage planning-stage">
                      <h3 className="stage-title">
                        <ClipboardList size={18} />
                        Synthesis Planning
                      </h3>
                      {msg.loading?.planning ? (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Creating chairman's synthesis plan...</span>
                        </div>
                      ) : (
                        <div className="planning-report">
                          <div className="report-content markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                              {normalizeMarkdownTables(msg.metadata.synthesis_plan, { unwrapFence: true })}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Editorial Guidelines */}
                  {(msg.loading?.editorial || msg.metadata?.editorial_guidelines) && (
                    <div className="stage editorial-stage">
                      <h3 className="stage-title">
                        <PenTool size={18} />
                        Editorial Guidelines
                      </h3>
                      {msg.loading?.editorial ? (
                        <div className="stage-loading">
                          <div className="spinner"></div>
                          <span>Defining writing style and tone...</span>
                        </div>
                      ) : (
                        <div className="editorial-report">
                          <div className="report-content markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                              {normalizeMarkdownTables(msg.metadata.editorial_guidelines)}
                            </ReactMarkdown>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Stage 3: Final Synthesis */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Chairman synthesizing final artifact...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
                )}
              </div>
            );
          })
        )}

        {isLoading && conversation.messages[conversation.messages.length - 1]?.role === 'user' && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <div className="input-stack">
          <div className="thread-controls">
            <div className="thread-status">
              <span className="thread-status-label">
                {selectionLocked ? 'Continuing this thread' : 'New thread'}
              </span>
              <span className="thread-status-sub">
                {selectionLocked
                  ? 'Uses prior Chairman outputs as context.'
                  : 'Select models and start a fresh cycle.'}
              </span>
            </div>
            <button
              type="button"
              className="thread-new-button"
              onClick={onNewConversation}
              disabled={isLoading}
            >
              Start new thread
            </button>
          </div>
          {!selectionLocked && (
            <ModelSelector
              availableModels={availableModels}
              chairmanModel={chairmanModel}
              expertModels={expertModels}
              minExpertModels={minExpertModels}
              thinkingByModel={thinkingByModel}
              thinkingSupportedModels={modelCatalog?.thinking_supported_models}
              onChange={({ chairmanModel: nextChairman, expertModels: nextExperts, thinkingByModel: nextThinking }) => {
                setHasEditedSelection(true);
                setChairmanModel(nextChairman);
                setExpertModels(nextExperts);
                if (nextThinking && typeof nextThinking === 'object') {
                  setThinkingByModel(nextThinking);
                }
              }}
              disabled={isLoading}
            />
          )}
          <form className="input-form" onSubmit={handleSubmit}>
            <textarea
              className="message-input"
              placeholder={inputPlaceholder}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
            />
            <button
              type="submit"
              className="send-button"
              disabled={!input.trim() || isLoading || !isSelectionValid}
              title="Send message"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
