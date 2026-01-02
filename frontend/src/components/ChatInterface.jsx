import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Stage0 from './Stage0';
import ContributionsStage from './ContributionsStage';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
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
          conversation.messages.map((msg, index) => (
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

                  {/* Stage 0: Intent Analysis */}
                  {msg.loading?.stage0 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Analyzing intent...</span>
                    </div>
                  )}
                  {msg.stage0 && <Stage0 data={msg.stage0} experts={msg.experts} />}

                  {/* Brainstorm Stage */}
                  {(msg.loading?.brainstorm || msg.brainstorm_content) && (
                    <div className="stage brainstorm-stage">
                      <h3 className="stage-title">🧠 Expert Brainstorm</h3>
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
                  {(msg.loading?.contributions || (msg.contributions && msg.contributions.length > 0)) && (
                    <ContributionsStage
                      contributions={msg.contributions || []}
                      loading={msg.loading?.contributions}
                      currentOrder={msg.loading?.currentOrder || 0}
                    />
                  )}

                  {/* Verification */}
                  {(msg.loading?.verification || msg.metadata?.verification_data) && (
                    <div className="stage verification-stage">
                      <h3 className="stage-title">🔬 Factual Verification</h3>
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
                      <h3 className="stage-title">📋 Synthesis Planning</h3>
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
                      <h3 className="stage-title">✍️ Editorial Guidelines</h3>
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
          ))
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
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            className="message-input"
            placeholder="Ask your question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={2}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
