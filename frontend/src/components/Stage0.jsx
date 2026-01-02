import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage0.css';

export default function Stage0({ data, experts }) {
    if (!data) return null;

    const analysis = data.analysis;

    if (!analysis) return null;

    return (
        <div className="stage stage0">
            <h3 className="stage-title">🎯 Intent Analysis</h3>

            <div className="intent-analysis">
                <div className="analysis-content markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {analysis}
                    </ReactMarkdown>
                </div>
            </div>

            {experts && experts.length > 0 && (
                <div className="experts-section">
                    <h4 className="experts-heading">Expert Team ({experts.length} members)</h4>
                    <div className="experts-grid">
                        {experts.map((expert, index) => (
                            <div key={index} className={`expert-card order-${expert.order || index + 1}`}>
                                <div className="expert-order">{expert.order || index + 1}</div>
                                <div className="expert-details">
                                    <div className="expert-card-name">{expert.name}</div>
                                    <p className="expert-card-description">{expert.description}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
