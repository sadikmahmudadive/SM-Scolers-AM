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
    { label: "Contact", href: "/contact" },
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
                AX
              </div>
              <span className="text-lg font-bold text-white tracking-tight">
                Attend<span className="gradient-text">X</span>
              </span>
            </Link>
            <p className="text-sm text-slate-500 leading-relaxed mb-6 max-w-xs">
              Biometric attendance management for schools, colleges, and
              institutions. Try free or get a custom build for your organization.
            </p>
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <Mail size={14} className="text-slate-600 flex-shrink-0" />
                siradive137@gmail.com
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <Phone size={14} className="text-slate-600 flex-shrink-0" />
                +8801835120307
              </div>
              <div className="flex items-center gap-3 text-sm text-slate-500">
                <MapPin size={14} className="text-slate-600 flex-shrink-0" />
                Mirpur-1, Dhaka, Bangladesh
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
          <span>&copy; {new Date().getFullYear()} AttendX. All rights reserved.</span>
          <span>Built with Next.js & Firebase</span>
        </div>
      </div>
    </footer>
  );
}
