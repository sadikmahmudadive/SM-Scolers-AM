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
  title: "SM Scolers - Smart Attendance Management System",
  description:
    "Biometric attendance tracking with real-time Firebase sync, SMS notifications, and comprehensive reporting. Manage your workforce effortlessly.",
  keywords: [
    "attendance",
    "biometric",
    "fingerprint",
    "attendance management",
    "employee tracking",
    "workforce management",
  ],
  openGraph: {
    title: "SM Scolers - Smart Attendance Management System",
    description:
      "Biometric attendance tracking with real-time Firebase sync, SMS notifications, and comprehensive reporting.",
    type: "website",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">
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
