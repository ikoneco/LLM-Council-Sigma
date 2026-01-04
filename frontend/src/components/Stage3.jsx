import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Trophy } from 'lucide-react';
import { normalizeMarkdownTables } from '../utils/markdown';
import './Stage3.css';

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const markdownComponents = {
    table({ children }) {
      return (
        <div className="table-wrapper">
          <table>{children}</table>
        </div>
      );
    },
  };

  return (
    <div className="stage stage3">
      <h3 className="stage-title">
        <Trophy size={18} />
        Final Council Answer
      </h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {normalizeMarkdownTables(finalResponse.response)}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
