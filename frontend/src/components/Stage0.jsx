import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Target, Compass, Lightbulb, CheckCircle2 } from 'lucide-react';
import './Stage0.css';

export default function Stage0({ data, experts }) {
    if (!data) return null;

    const analysis = data.analysis;

    if (!analysis) return null;

    const markdownComponents = {
        h3({ children }) {
            const text = String(children);
            const cleanText = text.replace(/^[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '').trim();

            let Icon = Target;
            if (cleanText.includes('Core Intent')) Icon = Target;
            else if (cleanText.includes('Critical Dimensions')) Icon = Compass;
            else if (cleanText.includes('Assumptions')) Icon = Lightbulb;
            else if (cleanText.includes('Success Criteria')) Icon = CheckCircle2;

            return (
                <h3 className="markdown-header-with-icon" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '16px', marginBottom: '8px' }}>
                    <Icon size={18} style={{ color: 'var(--color-primary)' }} />
                    {cleanText}
                </h3>
            );
        }
    };

    return (
        <div className="stage stage0">
            <h3 className="stage-title">
                <Target size={18} />
                Intent Analysis
            </h3>

            <div className="intent-analysis">
                <div className="analysis-content markdown-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
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
