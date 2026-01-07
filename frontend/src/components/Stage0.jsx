import { Children, isValidElement } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Target, Compass, Lightbulb, CheckCircle2 } from 'lucide-react';
import './Stage0.css';

export default function Stage0({ data, experts }) {
    if (!data) return null;

    const analysis = typeof data.analysis === 'string'
        ? data.analysis
        : (data.analysis ? JSON.stringify(data.analysis, null, 2) : '');

    if (!analysis) return null;

    const flattenText = (node) => {
        const parts = [];
        Children.forEach(node, (child) => {
            if (typeof child === 'string' || typeof child === 'number') {
                parts.push(String(child));
            } else if (isValidElement(child)) {
                parts.push(flattenText(child.props.children));
            }
        });
        return parts.join('');
    };

    const renderHeader = ({ children, level }) => {
        const cleanText = flattenText(children)
            .replace(/^\s*[\p{Emoji}\u2000-\u3300\uF000-\uFFFF]+\s*/u, '')
            .replace(/^\s*#{1,6}\s*/, '')
            .trim();

        let Icon = Target;
        if (cleanText.includes('Core Intent')) Icon = Target;
        else if (cleanText.includes('Critical Dimensions')) Icon = Compass;
        else if (cleanText.includes('Assumptions')) Icon = Lightbulb;
        else if (cleanText.includes('Success Criteria')) Icon = CheckCircle2;
        else if (cleanText.includes('Final Intent Summary')) Icon = Target;
        else if (cleanText.includes('Intent Packet')) Icon = Compass;

        const Tag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3';

        return (
            <Tag className="markdown-header-with-icon" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '12px', marginBottom: '6px' }}>
                <Icon size={18} style={{ color: 'var(--color-primary)' }} />
                {cleanText}
            </Tag>
        );
    };

    const markdownComponents = {
        h1(props) {
            return renderHeader({ ...props, level: 1 });
        },
        h2(props) {
            return renderHeader({ ...props, level: 2 });
        },
        h3(props) {
            return renderHeader({ ...props, level: 3 });
        },
        table({ children }) {
            return (
                <div className="table-wrapper">
                    <table>{children}</table>
                </div>
            );
        },
    };

    return (
        <div className="stage stage0">
            <h3 className="stage-title">
                <Target size={18} />
                Intent Brief
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
