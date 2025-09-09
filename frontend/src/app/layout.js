import { Figtree } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../contexts/AuthContext";

const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata = {
  title: "AgriConnect - Agricultural Extension Platform",
  description: "Connect farmers with agricultural extension officers",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={`${figtree.variable} antialiased bg-gradient-brand min-h-screen`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
