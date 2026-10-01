"use client";

import { type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/utils";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Groups items under a small uppercase header, in first-seen order. Items with no
   * section (e.g. a short, ungrouped nav for a role with only a couple of pages) render
   * as one flat list, same as before sections existed. */
  section?: string;
}

function groupBySection(items: NavItem[]): Array<{ section: string | null; items: NavItem[] }> {
  const groups: Array<{ section: string | null; items: NavItem[] }> = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.section === (item.section ?? null)) {
      last.items.push(item);
    } else {
      groups.push({ section: item.section ?? null, items: [item] });
    }
  }
  return groups;
}

export function Sidebar({
  items,
  homeHref,
  open,
  onClose,
}: {
  items: NavItem[];
  homeHref: string;
  /** Mobile-drawer state (below the `lg` breakpoint — static and always visible at `lg` and up,
   * same as before this existed). Both optional so this component still works exactly as it did
   * for any caller that doesn't need the drawer behavior. */
  open?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const groups = groupBySection(items);

  // Closing on navigation (not just on backdrop click) is the behavior people actually expect from
  // a mobile nav drawer — picking a destination should always dismiss it, same as a native app.
  useEffect(() => {
    onClose?.();
    // Only pathname changing should trigger this, not onClose's own identity.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <>
      {/* Backdrop: mobile-drawer mode only (`lg:hidden`) — the static desktop sidebar never has
          one, so this stays invisible/inert there regardless of `open`. */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <nav
        className={cn(
          "flex h-full w-64 shrink-0 flex-col overflow-y-auto border-r border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950",
          // Below `lg`: an off-canvas drawer, fixed above everything, sliding in/out by
          // transform so the transition stays GPU-cheap. At `lg` and up: back to the original
          // static, always-visible column — `lg:translate-x-0` wins regardless of `open`.
          "fixed inset-y-0 left-0 z-40 w-72 -translate-x-full transition-transform duration-200 ease-out lg:static lg:z-auto lg:w-56 lg:translate-x-0",
          open && "translate-x-0",
        )}
      >
        <div className="mb-4 flex items-center justify-between px-2">
          <Link href={homeHref}>
            <Logo />
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="rounded-md p-1 text-neutral-400 hover:bg-neutral-100 hover:text-neutral-600 lg:hidden dark:hover:bg-neutral-900"
          >
            <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5" aria-hidden="true">
              <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="flex flex-col gap-3">
          {groups.map((group, i) => (
            <div key={group.section ?? i} className="flex flex-col gap-0.5">
              {group.section && (
                <p className="px-2.5 pt-1 pb-0.5 text-[0.6875rem] font-semibold tracking-wider text-neutral-400 uppercase dark:text-neutral-600">
                  {group.section}
                </p>
              )}
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(`${href}/`);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-primary text-primary-foreground"
                        : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-900",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </div>
      </nav>
    </>
  );
}
