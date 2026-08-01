import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import Providers from "./providers";
import PwaRegister from "@/components/PwaRegister";
import NativeShell from "@/components/native/NativeShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TrueBrief | Noise-Free News Intelligence",
  description: "Get only the delta. Stop reading the same news twice.",
  manifest: "/manifest.json",
  icons: {
    icon: "/icon-192.png",
    apple: "/apple-touch-icon.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "TrueBrief",
  },
};

export const viewport: Viewport = {
  themeColor: "#4B52E2",
  initialScale: 1,
  width: "device-width",
  // Lets the layout paint under the notch / gesture bar; the safe-area insets
  // in globals.css then reclaim that space where it actually matters.
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html
        lang="en"
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
        suppressHydrationWarning
      >
        <body className="h-full bg-[var(--color-background-primary)] text-[var(--color-text-primary)]">
          <PwaRegister />
          <NativeShell />
          <Providers>
            {children}
          </Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
