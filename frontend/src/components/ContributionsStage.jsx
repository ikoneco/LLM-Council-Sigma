import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
                        <div className="entry-header">
                            <div className="order-badge">Expert {entry.order}</div>
                            <div className="expert-name">{entry.expert?.name || 'Expert'}</div>
                        </div>

                        {entry.expert?.description && (
                            <div className="expert-mandate">{entry.expert.description}</div>
                        )}

                        <div className="entry-contribution markdown-content">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {entry.contribution}
                            </ReactMarkdown>
                        </div>

                        {index < contributions.length - 1 && (
                            <div className="contribution-connector">
                                <span className="connector-arrow">↓</span>
                                <span className="connector-text">builds upon</span>
                            </div>
                        )}
                    </div>
                ))}

                {loading && currentOrder > contributions.length && (
                    <div className="contribution-entry loading">
                        <div className="entry-header">
                            <div className="order-badge pending">Expert {currentOrder}</div>
                        </div>
                        <div className="stage-loading">
                            <div className="spinner"></div>
                            <span>Expert {currentOrder} is contributing...</span>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
