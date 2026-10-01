import Link from "next/link";

import { LogoMark } from "@/components/brand/logo";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-1 items-center justify-center p-6">
      <div className="w-full max-w-sm text-center">
        <span className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary">
          <LogoMark className="h-6 w-6" />
        </span>
        <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-sm text-neutral-500 dark:text-neutral-400">
          Nothing lives at this address. Check the link, or head back to a page that does.
        </p>
        <Link href="/" className={cn(buttonVariants({ size: "lg" }), "mt-6")}>
          Go home
        </Link>
      </div>
    </div>
  );
}
