import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tejedora — de la foto al patrón",
  description:
    "Subí una foto de una prenda tejida y obtené un patrón calculado y verificado.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
