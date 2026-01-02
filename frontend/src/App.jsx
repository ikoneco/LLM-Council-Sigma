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
        stage0: null,
        brainstorm_content: null,
        experts: null,
        contributions: [],
        stage3: null,
        metadata: modelSelection ? { model_selection: modelSelection } : {},
        loading: {
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

      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
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
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      }, modelSelection);
    } catch (error) {
      console.error('Failed to send message:', error);
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
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
        onNewConversation={handleNewConversation}
        isLoading={isLoading}
        modelCatalog={modelCatalog}
      />
    </div>
  );
}

export default App;
