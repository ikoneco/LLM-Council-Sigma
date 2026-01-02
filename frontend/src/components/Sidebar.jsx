import React from 'react';
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
      // 1. Trigger the API call and wait for it
      await onDeleteConversation(id);
      // Item will be removed from state by onEvent
    } catch (error) {
      console.error("Deletion failed:", error);
      setDeletingId(null);
    }
  };

  // Reset confirmation if clicking elsewhere
  React.useEffect(() => {
    const handleClickOutside = () => setConfirmingId(null);
    window.addEventListener('click', handleClickOutside);
    return () => window.removeEventListener('click', handleClickOutside);
  }, []);

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
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
                    onClick={(e) => executeDelete(conv.id)}
                  >
                    Delete
                  </button>
                ) : (
                  <button
                    className="delete-conv-btn"
                    onClick={(e) => handleDeleteQuery(e, conv.id)}
                    title="Delete Conversation"
                  >
                    ×
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
