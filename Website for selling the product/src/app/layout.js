import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/AuthContext";
import { Toaster } from "react-hot-toast";
import Navbar from "@/components/Navbar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata = {
  title: "AttendX - Smart Biometric Attendance System",
  description:
    "Biometric attendance management for schools, colleges, and institutions. Real-time sync, SMS alerts, PDF reports — try free or get a custom build for your organization.",
  keywords: [
    "attendance",
    "biometric",
    "fingerprint",
    "attendance management",
    "institution attendance",
    "school attendance system",
  ],
  openGraph: {
    title: "AttendX - Smart Biometric Attendance System",
    description:
      "Biometric attendance management for any institution. Try the free version or request a custom build.",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
        <body className="antialiased" suppressHydrationWarning>
        <AuthProvider>
          <Toaster
            position="top-right"
            toastOptions={{
              style: {
                background: "#1e293b",
                color: "#f0f4f8",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: "12px",
              },
              success: {
                iconTheme: { primary: "#00d4aa", secondary: "#0a0e1a" },
              },
              error: {
                iconTheme: { primary: "#ef4444", secondary: "#0a0e1a" },
              },
            }}
          />
          <Navbar />
          <main>{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
