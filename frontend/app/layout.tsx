import "./globals.css";
import Sidebar from "@/components/sidebar";

export const metadata = {
  title: "Vetted — Read every resume as if it were the only one",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <div className="flex min-h-screen">
          <Sidebar />
          <main id="main-content" className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
