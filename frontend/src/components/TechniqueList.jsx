import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function TechniqueList({ techniques }) {
  if (!techniques?.length) return <p>No techniques yet.</p>;

  return (
    <ol className="technique-list">
      {techniques.map((t) => (
        <li key={t.id}>
          <div className="technique-title">{t.title}</div>
          <div className="technique-description">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.description}</ReactMarkdown>
          </div>
        </li>
      ))}
    </ol>
  );
}
