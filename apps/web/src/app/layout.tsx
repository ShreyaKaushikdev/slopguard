import "./styles.css";

export const metadata = {
  title: "SlopGuard",
  description: "The Internet's Quality Layer",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

