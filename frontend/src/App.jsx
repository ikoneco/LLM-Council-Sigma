import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [modelCatalog, setModelCatalog] = useState(null);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    const loadModels = async () => {
      try {
        const catalog = await api.getModels();
        setModelCatalog(catalog);
      } catch (error) {
        console.error('Failed to load models:', error);
      }
    };

    loadModels();
  }, []);

  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleStreamEvent = (eventType, event) => {
    switch (eventType) {
      case 'intent_draft_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            loading: { ...messages[messages.length - 1].loading, intent_draft: true },
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'intent_draft_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            intent_draft: event.data?.draft_intent || event.data?.draft || event.data,
            intent_display: event.data?.display || {},
            clarification_questions: event.data?.questions || [],
            awaiting_clarification: true,
            status: 'clarification_pending',
            loading: { ...messages[messages.length - 1].loading, intent_draft: false },
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'clarification_required':
        setIsLoading(false);
        break;

      case 'stage0_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, stage0: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'stage0_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            stage0: event.data,
            status: 'complete',
            loading: { ...messages[messages.length - 1].loading, stage0: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'brainstorm_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, brainstorm: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'brainstorm_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            experts: event.data.experts,
            brainstorm_content: event.data.brainstorm_content,
            loading: { ...messages[messages.length - 1].loading, brainstorm: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'contributions_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, contributions: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'expert_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            loading: { ...messages[messages.length - 1].loading, currentOrder: event.data.order }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'expert_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            contributions: [...(messages[messages.length - 1].contributions || []), event.data]
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'contributions_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            loading: { ...messages[messages.length - 1].loading, contributions: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'verification_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, verification: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'verification_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            metadata: { ...(messages[messages.length - 1].metadata || {}), verification_data: event.data },
            loading: { ...messages[messages.length - 1].loading, verification: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'planning_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, planning: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'planning_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            metadata: { ...(messages[messages.length - 1].metadata || {}), synthesis_plan: event.data },
            loading: { ...messages[messages.length - 1].loading, planning: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'editorial_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, editorial: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'editorial_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            metadata: { ...(messages[messages.length - 1].metadata || {}), editorial_guidelines: event.data },
            loading: { ...messages[messages.length - 1].loading, editorial: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'stage3_start':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = { ...messages[messages.length - 1], loading: { ...messages[messages.length - 1].loading, stage3: true } };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'stage3_complete':
        setCurrentConversation((prev) => {
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            stage3: event.data,
            loading: { ...messages[messages.length - 1].loading, stage3: false }
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        break;

      case 'title_complete':
        loadConversations();
        break;

      case 'complete':
        loadConversations();
        setCurrentConversation((prev) => {
          if (!prev || !prev.messages || prev.messages.length === 0) return prev;
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            loading: {
              ...(messages[messages.length - 1].loading || {}),
              intent_draft: false,
              stage0: false,
              brainstorm: false,
              contributions: false,
              verification: false,
              planning: false,
              editorial: false,
              stage3: false,
            },
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        setIsLoading(false);
        break;

      case 'error':
        console.error('Stream error:', event.message);
        setCurrentConversation((prev) => {
          if (!prev || !prev.messages || prev.messages.length === 0) return prev;
          const messages = [...prev.messages];
          const lastMsg = {
            ...messages[messages.length - 1],
            status: 'error',
            error_message: event.message,
            loading: {
              ...(messages[messages.length - 1].loading || {}),
              intent_draft: false,
              stage0: false,
              brainstorm: false,
              contributions: false,
              verification: false,
              planning: false,
              editorial: false,
              stage3: false,
            },
          };
          messages[messages.length - 1] = lastMsg;
          return { ...prev, messages };
        });
        setIsLoading(false);
        break;

      default:
        console.log('Unknown event type:', eventType);
    }
  };

  const handleSendMessage = async (content, modelSelection) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      const assistantMessage = {
        role: 'assistant',
        intent_draft: null,
        intent_display: null,
        clarification_questions: [],
        clarification_answers: null,
        awaiting_clarification: false,
        stage0: null,
        brainstorm_content: null,
        experts: null,
        contributions: [],
        stage3: null,
        metadata: modelSelection ? { model_selection: modelSelection } : {},
        loading: {
          intent_draft: false,
          stage0: false,
          brainstorm: false,
          contributions: false,
          currentOrder: 0,
          verification: false,
          planning: false,
          editorial: false,
          stage3: false,
        },
      };

      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      await api.sendMessageStream(currentConversationId, content, handleStreamEvent, modelSelection);
    } catch (error) {
      console.error('Failed to send message:', error);
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  const handleContinueMessage = async (clarificationPayload) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    setCurrentConversation((prev) => {
      const messages = [...prev.messages];
      const lastMsg = {
        ...messages[messages.length - 1],
        awaiting_clarification: false,
        status: 'clarification_submitted',
        clarification_answers: clarificationPayload,
      };
      messages[messages.length - 1] = lastMsg;
      return { ...prev, messages };
    });

    try {
      await api.continueMessageStream(currentConversationId, clarificationPayload, handleStreamEvent);
    } catch (error) {
      console.error('Failed to continue message:', error);
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        onContinueMessage={handleContinueMessage}
        onNewConversation={handleNewConversation}
        isLoading={isLoading}
        modelCatalog={modelCatalog}
      />
    </div>
  );
}

export default App;
