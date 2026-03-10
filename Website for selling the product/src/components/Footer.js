"use client";

import Link from "next/link";
import { Mail, MapPin, Phone } from "lucide-react";

const footerLinks = {
  Product: [
    { label: "Features", href: "#features" },
    { label: "Pricing", href: "#pricing" },
    { label: "Download", href: "/download" },
    { label: "Changelog", href: "#" },
  ],
  Support: [
    { label: "Documentation", href: "#" },
    { label: "FAQ", href: "#faq" },
    { label: "Contact", href: "mailto:support@smscolers.com" },
    { label: "Status", href: "#" },
  ],
  Legal: [
    { label: "Privacy Policy", href: "#" },
    { label: "Terms of Service", href: "#" },
    { label: "License", href: "#" },
  ],
};

export default function Footer() {
  return (
    <footer className="relative border-t border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid md:grid-cols-2 lg:grid-cols-5 gap-12">
          {/* Brand */}
          <div className="lg:col-span-2">
            <Link href="/" className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-[#0078d7] to-[#00d4aa] flex items-center justify-center font-bold text-sm text-white">
                SM
              </div>
              <span className="text-lg font-bold text-white tracking-tight">
                SM <span className="gradient-text">Scolers</span>
              </span>
            </Link>
            <p className="text-sm text-slate-500 leading-relaxed mb-6 max-w-xs">
              Smart attendance management system with biometric fingerprint
              tracking, real-time sync, and automated notifications.
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <Mail size={14} className="text-slate-600" />
                support@smscolers.com
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <Phone size={14} className="text-slate-600" />
                +254 700 000 000
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <MapPin size={14} className="text-slate-600" />
                Nairobi, Kenya
              </div>
            </div>
          </div>

          {/* Link columns */}
          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h4 className="text-sm font-semibold text-white mb-4">{title}</h4>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.label}>
                    <Link
                      href={link.href}
                      className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="section-divider mt-12 mb-8" />

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-600">
          <span>&copy; {new Date().getFullYear()} SM Scolers. All rights reserved.</span>
          <span>Built with Next.js & Firebase</span>
        </div>
      </div>
    </footer>
  );
}
