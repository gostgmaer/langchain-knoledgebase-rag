"use client";

import { type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

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

export function Sidebar({ items, homeHref }: { items: NavItem[]; homeHref: string }) {
  const pathname = usePathname();
  const groups = groupBySection(items);

  return (
    <nav className="flex h-full w-56 shrink-0 flex-col overflow-y-auto border-r border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-950">
      <Link href={homeHref} className="mb-4 px-2">
        <Logo />
      </Link>
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
  );
}
