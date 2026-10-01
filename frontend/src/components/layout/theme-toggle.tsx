"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

/**
 * A simple light/dark toggle, not a three-way light/dark/system menu — "system" is still what a
 * brand-new session gets (providers.tsx's `defaultTheme="system"`), this just lets anyone override
 * it in one click rather than needing to go find an OS setting.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // next-themes can't know the real theme until after mount (it reads localStorage/matchMedia
  // client-side only) — rendering a guess first and swapping post-mount would itself cause the
  // exact hydration mismatch suppressHydrationWarning on <html> is there to avoid for the class
  // itself; this just keeps the icon's own markup identical between server and first client render.
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    // The official next-themes pattern for exactly this problem — there's no external system to
    // subscribe to here, "has the client finished its first render" has no other signal.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  if (!mounted) {
    return <Button variant="ghost" size="icon" aria-label="Toggle theme" disabled className="opacity-0" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
