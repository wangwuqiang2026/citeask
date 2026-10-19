import { Children, memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { splitCitations } from "@/lib/citations";

interface MarkdownProps {
  content: string;
  citationLabel: string;
  activeCitation?: number | null;
  onCitation?: (index: number) => void;
}

function withCitations(
  children: ReactNode,
  props: MarkdownProps,
): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child !== "string") return child;

    const tokens = splitCitations(child);
    if (tokens.length === 1 && tokens[0].type === "text") return tokens[0].value;

    return tokens.map((token, index) =>
      token.type === "text" ? (
        <span key={`t-${index}`}>{token.value}</span>
      ) : (
        <button
          key={`c-${index}`}
          type="button"
          className="citation-chip"
          data-active={props.activeCitation === token.index}
          aria-label={`${props.citationLabel} ${token.index + 1}`}
          onClick={() => props.onCitation?.(token.index)}
        >
          {token.index + 1}
        </button>
      ),
    );
  });
}

/**
 * Markdown renderer of an answer. Citations (`【n】`) are turned into buttons at
 * the level of the text children, so tables and list structure stay intact and
 * the markdown source is never rewritten.
 */
export const Markdown = memo(function Markdown(props: MarkdownProps) {
  const render = (children: ReactNode) => withCitations(children, props);

  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: false, ignoreMissing: true }]]}
        components={{
          p: ({ children }) => <p>{render(children)}</p>,
          li: ({ children }) => <li>{render(children)}</li>,
          td: ({ children }) => <td>{render(children)}</td>,
          strong: ({ children }) => <strong>{render(children)}</strong>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {props.content}
      </ReactMarkdown>
    </div>
  );
});
