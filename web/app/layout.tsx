import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tejedora — from photo to pattern",
  description:
    "Upload a photo of any knitted or crocheted piece and get a calculated, verified pattern.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // El idioma real lo fija I18nProvider (web/lib/i18n.ts) en el cliente.
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
