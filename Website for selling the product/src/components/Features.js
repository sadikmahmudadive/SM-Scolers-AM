"use client";

import AnimatedSection from "./AnimatedSection";
import {
  Fingerprint,
  CloudUpload,
  MessageSquare,
  FileText,
  Users,
  Wifi,
  ShieldCheck,
  BarChart3,
} from "lucide-react";

const features = [
  {
    icon: Fingerprint,
    title: "Biometric Fingerprint",
    description:
      "Connect ZK Teco biometric devices for accurate, fraud-proof attendance capture with millisecond scan times.",
    color: "from-blue-500 to-cyan-400",
    glow: "shadow-blue-500/10",
  },
  {
    icon: CloudUpload,
    title: "Firebase Real-time Sync",
    description:
      "Attendance records sync instantly to Firebase Realtime Database. Works offline and catches up automatically.",
    color: "from-emerald-500 to-teal-400",
    glow: "shadow-emerald-500/10",
  },
  {
    icon: MessageSquare,
    title: "SMS Notifications",
    description:
      "Automated GSM-based SMS alerts notify stakeholders when members check in or out. Perfect for schools, offices, and training centers.",
    color: "from-purple-500 to-pink-400",
    glow: "shadow-purple-500/10",
  },
  {
    icon: FileText,
    title: "PDF Reports",
    description:
      "Generate beautiful, detailed attendance reports in PDF. Filter by date range, class, or individual.",
    color: "from-amber-500 to-orange-400",
    glow: "shadow-amber-500/10",
  },
  {
    icon: Users,
    title: "User Management",
    description:
      "Add, edit, and manage members and staff. Bulk enrolment via fingerprint with photo capture.",
    color: "from-rose-500 to-red-400",
    glow: "shadow-rose-500/10",
  },
  {
    icon: Wifi,
    title: "Auto-Reconnect",
    description:
      "Smart device monitoring with automatic reconnection. Never miss a record, even during network drops.",
    color: "from-indigo-500 to-blue-400",
    glow: "shadow-indigo-500/10",
  },
  {
    icon: ShieldCheck,
    title: "Secure & Reliable",
    description:
      "Data encrypted in transit, local backup, and Firebase security rules ensure your data stays safe.",
    color: "from-teal-500 to-emerald-400",
    glow: "shadow-teal-500/10",
  },
  {
    icon: BarChart3,
    title: "Live Dashboard",
    description:
      "Real-time attendance dashboard with present, absent, and late counts. Auto-refreshes with background sync.",
    color: "from-sky-500 to-blue-400",
    glow: "shadow-sky-500/10",
  },
];

export default function Features() {
  return (
    <section id="features" className="relative py-24 lg:py-32">
      {/* Background */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-blue-500/[0.02] to-transparent" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <AnimatedSection className="text-center max-w-2xl mx-auto mb-16">
          <span className="inline-block text-xs font-semibold tracking-widest uppercase text-blue-400 mb-3">
            Features
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold mb-4">
            Everything you need for{" "}
            <span className="gradient-text">attendance management</span>
          </h2>
          <p className="text-slate-400 text-lg">
            A complete suite of tools designed to make tracking and reporting
            attendance effortless and reliable.
          </p>
        </AnimatedSection>

        {/* Grid */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {features.map((feature, idx) => (
            <AnimatedSection
              key={feature.title}
              delay={idx * 0.08}
              className="group"
            >
              <div
                className={`relative h-full glass rounded-2xl p-6 transition-all duration-300 hover:bg-white/[0.04] hover:-translate-y-1 ${feature.glow} hover:shadow-lg cursor-default`}
              >
                <div
                  className={`w-11 h-11 rounded-xl bg-gradient-to-br ${feature.color} flex items-center justify-center mb-4 shadow-lg group-hover:scale-110 transition-transform duration-300`}
                >
                  <feature.icon size={20} className="text-white" />
                </div>
                <h3 className="text-base font-semibold text-white mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </div>
    </section>
  );
}
