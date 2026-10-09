/**
 * The usability guide's table of contents: one topic = one page, fetched from
 * /docs/topics/<slug>.md (frontend/public/docs/topics/) and rendered by DocsArticleView.
 * `section` groups topics on the index page the same way NAV_BY_ROLE groups the sidebar
 * (frontend/src/app/[role]/layout.tsx), so the two stay recognizable as the same product map.
 */
export interface DocsTopic {
  slug: string;
  title: string;
  description: string;
  section: "Overview" | "Knowledge" | "Build" | "Operations" | "Administration" | "Help";
  /** Shown as a small badge on the topic card when the feature isn't available to every role. */
  roleNote?: string;
}

export const DOCS_TOPICS: DocsTopic[] = [
  { slug: "getting-started", title: "Getting started", description: "Signing in, roles, and finding your way around.", section: "Overview" },
  { slug: "chat", title: "Chat", description: "Ask questions, read citations, leave feedback.", section: "Overview" },
  { slug: "dashboard", title: "Dashboard", description: "A quick health check for your workspace.", section: "Overview", roleNote: "Tenant Admin and Admin" },

  { slug: "knowledge-bases", title: "Knowledge Bases", description: "Named collections of documents that retrieval is scoped around.", section: "Knowledge" },
  { slug: "knowledge-sources", title: "Knowledge Sources", description: "Connect websites, Confluence, SharePoint, Teams, Slack and more.", section: "Knowledge" },
  { slug: "permissions", title: "Permissions and identity mappings", description: "Mirror a connected source's own access rules inside Meridian.", section: "Knowledge" },
  { slug: "documents", title: "Documents", description: "Upload files directly for ingestion.", section: "Knowledge" },
  { slug: "search", title: "Search", description: "The same retrieval chat uses, without a chat-composed answer.", section: "Knowledge" },

  { slug: "agents", title: "Agents", description: "Reusable assistant configurations — prompt, model, parameters.", section: "Build" },
  { slug: "embeddable-widget", title: "Embeddable chat widget", description: "Put Meridian chat on an external website.", section: "Build" },
  { slug: "model-profiles", title: "Model Profiles", description: "Configured LLM/embedding connections, shared platform-wide.", section: "Build", roleNote: "Tenant Admin and Admin" },
  { slug: "prompts", title: "Prompts", description: "Versioned system-prompt templates.", section: "Build" },
  { slug: "tools", title: "Tools", description: "Built-in tools, and custom webhook tools.", section: "Build" },

  { slug: "retrieval", title: "Retrieval Log and Retrieval Settings", description: "See what retrieval found, and tune how it behaves.", section: "Operations" },
  { slug: "operations", title: "Analytics, Usage, Observability and Feedback", description: "How the workspace is actually performing.", section: "Operations", roleNote: "Tenant Admin and Admin" },
  { slug: "upload-jobs", title: "Upload Jobs", description: "Real-time progress for every document upload.", section: "Operations" },

  { slug: "team", title: "Team", description: "Members and pending invitations.", section: "Administration" },
  { slug: "api-keys", title: "API Keys", description: "Call the platform's API outside a browser session.", section: "Administration" },
  { slug: "settings", title: "Settings", description: "Your profile, password, and connected sign-in providers.", section: "Administration" },
  { slug: "tenants", title: "Tenants", description: "Every organization on the platform.", section: "Administration", roleNote: "Admin only" },
  { slug: "feature-flags", title: "Feature Flags", description: "Dynamic toggles, no redeploy needed.", section: "Administration", roleNote: "Admin only" },
  { slug: "platform-settings", title: "Platform Settings", description: "Operational knobs, platform-wide.", section: "Administration", roleNote: "Admin only" },

  { slug: "troubleshooting", title: "Troubleshooting and FAQ", description: "Common issues, and how to resolve them.", section: "Help" },
];

export const DOCS_SECTIONS: DocsTopic["section"][] = ["Overview", "Knowledge", "Build", "Operations", "Administration", "Help"];

export function findDocsTopic(slug: string): DocsTopic | undefined {
  return DOCS_TOPICS.find((t) => t.slug === slug);
}
