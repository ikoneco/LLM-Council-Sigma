import React from 'react';
import { LayoutGrid, Plus, MessageSquare, Trash2 } from 'lucide-react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
}) {
  const [confirmingId, setConfirmingId] = React.useState(null);
  const [deletingId, setDeletingId] = React.useState(null);

  const handleDeleteQuery = (e, id) => {
    e.stopPropagation();
    if (confirmingId === id) {
      executeDelete(id);
    } else {
      setConfirmingId(id);
    }
  };

  const executeDelete = async (id) => {
    setDeletingId(id);
    setConfirmingId(null);

    try {
      await onDeleteConversation(id);
    } catch (error) {
      console.error("Deletion failed:", error);
      setDeletingId(null);
    }
  };

  React.useEffect(() => {
    const handleClickOutside = () => setConfirmingId(null);
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, []);

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="app-branding">
          <LayoutGrid size={24} color="var(--color-primary)" />
          <h1>LLM Council</h1>
        </div>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          <Plus size={18} />
          <span>New Chat</span>
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item 
                ${conv.id === currentConversationId ? 'active' : ''} 
                ${confirmingId === conv.id ? 'confirming' : ''}
                ${deletingId === conv.id ? 'deleting' : ''}
              `}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-icon">
                <MessageSquare size={18} />
              </div>
              <div className="conversation-content">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>

              <div className="sidebar-action-area" onClick={(e) => e.stopPropagation()}>
                {confirmingId === conv.id ? (
                  <button
                    className="confirm-delete-btn"
                    onClick={() => executeDelete(conv.id)}
                    title="Confirm Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                ) : (
                  <button
                    className="delete-conv-btn"
                    onClick={(e) => handleDeleteQuery(e, conv.id)}
                    title="Delete Conversation"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
