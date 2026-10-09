"use client";

import { ImageOff } from "lucide-react";
import { useParams } from "next/navigation";
import { isValidElement, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children);
  return "";
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-");
}

function heading(Tag: "h1" | "h2" | "h3" | "h4", sizeClass: string) {
  return function Heading({ children }: { children?: ReactNode }) {
    return (
      <Tag id={slugify(textOf(children))} className={`scroll-mt-20 font-semibold first:mt-0 ${sizeClass}`}>
        {children}
      </Tag>
    );
  };
}

/**
 * Screenshots referenced by the guide aren't added yet (docs/BUGS.md-style note: authored ahead of
 * the images themselves). Rather than a browser's broken-image icon, a labeled placeholder shows
 * exactly which file to drop into public/docs/images to fill the spot.
 */
function MarkdownImage({ src, alt }: { src?: string; alt?: string }) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    return (
      <span className="my-4 flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-neutral-300 bg-neutral-50 px-4 py-10 text-center dark:border-neutral-700 dark:bg-neutral-900">
        <ImageOff className="h-5 w-5 text-neutral-400" aria-hidden="true" />
        <span className="text-xs text-neutral-500 dark:text-neutral-400">{alt || "Screenshot coming soon"}</span>
        {src && <code className="text-[0.65rem] text-neutral-400 dark:text-neutral-600">{src}</code>}
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={alt ?? ""}
      loading="lazy"
      onError={() => setBroken(true)}
      className="my-4 w-full rounded-lg border border-neutral-200 dark:border-neutral-800"
    />
  );
}

function buildComponents(role: string): Components {
  return {
  h1: heading("h1", "mt-8 text-2xl"),
  h2: heading("h2", "mt-8 text-xl"),
  h3: heading("h3", "mt-6 text-lg"),
  h4: heading("h4", "mt-4 text-base"),
  p: ({ children }) => <p className="mt-3 leading-relaxed first:mt-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mt-3 list-disc space-y-1.5 pl-6 first:mt-0">{children}</ul>,
  ol: ({ children }) => <ol className="mt-3 list-decimal space-y-1.5 pl-6 first:mt-0">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }) => {
    const external = /^https?:\/\//.test(href ?? "");
    // Cross-topic links are authored role-agnostic (e.g. "/docs/settings"); this is the one place
    // that knows which role's doc tree is actually being read, so it's the one place that can
    // correctly resolve them to "/{role}/docs/settings" rather than baking a role into every file.
    const resolved = !external && href?.startsWith("/docs/") ? `/${role}${href}` : href;
    return (
      <a
        href={resolved}
        target={external ? "_blank" : undefined}
        rel={external ? "noreferrer noopener" : undefined}
        className="font-medium underline underline-offset-2 hover:no-underline"
      >
        {children}
      </a>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="mt-3 border-l-2 border-neutral-300 pl-4 text-neutral-600 dark:border-neutral-700 dark:text-neutral-400">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "");
    return isBlock ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="rounded bg-black/[0.06] px-1.5 py-0.5 font-mono text-[0.85em] dark:bg-white/10">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mt-3 overflow-x-auto rounded-md bg-black/[0.06] p-4 font-mono text-xs leading-relaxed dark:bg-white/10">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full border-collapse text-left text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-neutral-200 bg-neutral-50 px-3 py-1.5 font-semibold dark:border-neutral-800 dark:bg-neutral-900">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-neutral-200 px-3 py-1.5 align-top dark:border-neutral-800">{children}</td>
  ),
  hr: () => <hr className="my-8 border-neutral-200 dark:border-neutral-800" />,
  img: ({ src, alt }) => <MarkdownImage src={typeof src === "string" ? src : undefined} alt={alt} />,
  };
}

export function DocsMarkdown({ content }: { content: string }) {
  const { role } = useParams<{ role: string }>();
  return (
    <article className="max-w-3xl text-sm text-neutral-700 dark:text-neutral-300">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={buildComponents(role)}>
        {content}
      </ReactMarkdown>
    </article>
  );
}
