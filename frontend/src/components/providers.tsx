"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, type ReactNode } from "react";
import { Toaster } from "sonner";

import { SessionProvider } from "@/lib/session";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 10_000,
          },
        },
      }),
  );

  return (
    // attribute="class" matches globals.css's `@custom-variant dark (&:where(.dark, .dark *))` —
    // every existing `dark:` utility across the whole app already responds to this class, no
    // per-component changes needed. defaultTheme="system" + enableSystem keeps today's OS-driven
    // behavior as the default; this only adds an explicit override on top of it. The explicit
    // `value` map (rather than next-themes' default of toggling only `.dark`) makes it always set
    // one of `.light`/`.dark`, never neither — globals.css's CSS variables rely on `.light` being
    // genuinely present to know "explicitly light," not just "not dark yet."
    //
    // Known, dev-only console noise from this exact combination (React 19 + Next.js 16.2+ +
    // next-themes): "Encountered a script tag while rendering React component." next-themes
    // injects a real inline <script> before hydration — the only way to set the right theme with
    // zero flash-of-wrong-theme — and React's dev-mode validation flags that as suspicious even
    // though it's correct and intentional (upstream: pacocoursey/next-themes#385, #387; confirmed
    // live here that dark mode itself works correctly — toggles, persists across navigation, no
    // real flash). React strips this validation in production builds, so it's dev-console-only.
    // Not patched around: the fix is either forking next-themes' internals or switching libraries
    // entirely, disproportionate to a warning with no functional impact.
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem value={{ light: "light", dark: "dark" }}>
      <QueryClientProvider client={queryClient}>
        <SessionProvider>
          {children}
          <Toaster position="top-right" richColors closeButton />
        </SessionProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
