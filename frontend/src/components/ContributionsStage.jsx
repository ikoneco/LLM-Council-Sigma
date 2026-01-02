import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User } from 'lucide-react';
import './ContributionsStage.css';

export default function ContributionsStage({ contributions, loading, currentOrder }) {
    if (!contributions || contributions.length === 0) {
        if (loading) {
            return (
                <div className="contributions-stage">
                    <h3 className="stage-title">👥 Expert Contributions</h3>
                    <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Experts are building the artifact...</span>
                    </div>
                </div>
            );
        }
        return null;
    }

    return (
        <div className="contributions-stage">
            <h3 className="stage-title">👥 Expert Contributions ({contributions.length} experts)</h3>

            <div className="contributions-timeline">
                {contributions.map((entry, index) => (
                    <div key={index} className={`contribution-entry order-${entry.order}`}>
                        {/* Timeline Badge */}
                        <div className="order-badge">{entry.order}</div>

                        {/* Content Card */}
                        <div className="expert-content-card">
                            <div className="entry-header">
                                <Bot size={20} className="mr-2 text-primary" color="var(--color-primary)" style={{ marginRight: '8px' }} />
                                <span className="expert-name">{entry.expert?.name || 'Expert'}</span>
                            </div>

                            {entry.expert?.description && (
                                <div className="expert-mandate">{entry.expert.description}</div>
                            )}

                            <div className="entry-contribution markdown-content">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {entry.contribution}
                                </ReactMarkdown>
                            </div>
                        </div>
                    </div>
                ))}

                {loading && currentOrder > contributions.length && (
                    <div className="contribution-entry loading">
                        <div className="order-badge pending">{currentOrder}</div>
                        <div className="expert-content-card">
                            <div className="stage-loading">
                                <div className="spinner"></div>
                                <span>Expert {currentOrder} is contributing...</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
