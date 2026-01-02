import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ClipboardList, PenTool, BrainCircuit, CheckCircle2, Target, Ruler, Mic, MessageCircle, AlertTriangle, Gem, Hash, Compass, Sparkles, Gavel, SlidersHorizontal } from 'lucide-react';
import Stage0 from './Stage0';
import ContributionsStage from './ContributionsStage';
import Stage3 from './Stage3';
import ModelSelector from './ModelSelector';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  onNewConversation,
  isLoading,
  modelCatalog,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const [chairmanModel, setChairmanModel] = useState('');
  const [expertModels, setExpertModels] = useState([]);
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
  ];

  const availableModels = modelCatalog?.available_models || fallbackAvailableModels;
  const minExpertModels = modelCatalog?.min_expert_models || 6;
  const defaultChairman = modelCatalog?.default_chairman_model || 'minimax/minimax-m2.1';
  const defaultExperts = modelCatalog?.default_expert_models || fallbackAvailableModels.slice(0, 6);

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
      setSelectionLocked(true);
      return;
    }

    setSelectionLocked(false);
    if (hasEditedSelection) return;

    setChairmanModel(defaultChairman);
    setExpertModels(defaultExperts);
  }, [conversation, defaultChairman, defaultExperts, hasEditedSelection]);

  const isSelectionValid = expertModels.length >= minExpertModels && chairmanModel;
  const modelSelectionPayload = isSelectionValid
    ? { chairman_model: chairmanModel, expert_models: expertModels }
    : null;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

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

  const markdownComponents = {
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
      const text = String(children);
      // Strip leading emojis or symbols (non-alphanumeric start)
      const cleanText = text.replace(/^[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '').trim();

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
                        </div>
                      </div>
                    )}

                    {/* Stage 0: Intent Analysis */}
                    {msg.loading?.stage0 && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Analyzing intent...</span>
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
                                {msg.brainstorm_content}
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
                                {msg.metadata.verification_data}
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
                              {msg.metadata.synthesis_plan}
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
                              {msg.metadata.editorial_guidelines}
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
          {!selectionLocked && (
            <ModelSelector
              availableModels={availableModels}
              chairmanModel={chairmanModel}
              expertModels={expertModels}
              minExpertModels={minExpertModels}
              onChange={({ chairmanModel: nextChairman, expertModels: nextExperts }) => {
                setHasEditedSelection(true);
                setChairmanModel(nextChairman);
                setExpertModels(nextExperts);
              }}
              disabled={isLoading}
            />
          )}
          <form className="input-form" onSubmit={handleSubmit}>
            <button
              type="button"
              className="new-topic-button"
              onClick={onNewConversation}
              disabled={isLoading}
              title="Start a new thread"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </button>
            <textarea
              className="message-input"
              placeholder="Ask a question..."
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
