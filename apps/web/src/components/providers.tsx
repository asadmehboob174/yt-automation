"use client";

import { NicheProvider } from "@/context/niche-context";
import { ThemeProvider } from "@/context/theme-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <NicheProvider>{children}</NicheProvider>
    </ThemeProvider>
  );
}
