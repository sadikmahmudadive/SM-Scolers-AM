"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight,
  Fingerprint,
  Wifi,
  BarChart3,
  Shield,
} from "lucide-react";

const floatingCards = [
  {
    icon: Fingerprint,
    label: "Biometric Scan",
    color: "from-blue-500 to-cyan-400",
    position: "top-[18%] right-[8%]",
    delay: 0.8,
  },
  {
    icon: Wifi,
    label: "Real-time Sync",
    color: "from-emerald-500 to-teal-400",
    position: "top-[55%] right-[4%]",
    delay: 1.1,
  },
  {
    icon: BarChart3,
    label: "Live Reports",
    color: "from-purple-500 to-pink-400",
    position: "bottom-[15%] right-[14%]",
    delay: 1.4,
  },
  {
    icon: Shield,
    label: "Secure Data",
    color: "from-amber-500 to-orange-400",
    position: "top-[40%] left-[2%]",
    delay: 1.0,
  },
];

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center overflow-hidden pt-16">
      {/* Background effects */}
      <div className="absolute inset-0 hero-grid opacity-40" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-blue-500/8 rounded-full blur-[120px]" />
      <div className="absolute bottom-0 left-1/4 w-[400px] h-[400px] bg-teal-500/5 rounded-full blur-[100px]" />

      {/* Animated orbs */}
      <motion.div
        animate={{ y: [0, -30, 0], x: [0, 15, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-[20%] left-[10%] w-3 h-3 bg-blue-400/30 rounded-full blur-sm"
      />
      <motion.div
        animate={{ y: [0, 20, 0], x: [0, -10, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        className="absolute top-[60%] right-[15%] w-2 h-2 bg-teal-400/30 rounded-full blur-sm"
      />
      <motion.div
        animate={{ y: [0, -15, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="absolute bottom-[30%] left-[20%] w-4 h-4 bg-purple-400/20 rounded-full blur-sm"
      />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left column — text */}
          <div className="max-w-xl">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass-light text-xs font-medium text-blue-300 mb-6"
            >
              <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse" />
              Free Version Available — Try It Now
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.3 }}
              className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight tracking-tight mb-6"
            >
              Biometric{" "}
              <span className="gradient-text">Attendance</span>
              <br />
              For Any Institution
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.45 }}
              className="text-lg text-slate-400 leading-relaxed mb-8"
            >
              Fingerprint tracking with real-time cloud sync, SMS alerts, PDF reports,
              and a powerful desktop dashboard. Try the free version or request a
              custom build with your institution&apos;s name and branding.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.6 }}
              className="flex flex-wrap gap-4"
            >
              <Link href="/download" className="btn-primary inline-flex items-center gap-2 text-base">
                Try Free Version
                <ArrowRight size={18} />
              </Link>
              <a href="#pricing" className="btn-secondary inline-flex items-center gap-2 text-base">
                Request Custom Build
              </a>
            </motion.div>

            {/* Stats strip */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.9 }}
              className="flex gap-8 mt-12"
            >
              {[
                { value: "500+", label: "Institutions" },
                { value: "99.9%", label: "Uptime" },
                { value: "< 1s", label: "Sync Speed" },
              ].map((stat) => (
                <div key={stat.label}>
                  <div className="text-2xl font-bold gradient-text">{stat.value}</div>
                  <div className="text-xs text-slate-500 mt-1">{stat.label}</div>
                </div>
              ))}
            </motion.div>
          </div>

          {/* Right column — floating cards */}
          <div className="relative hidden lg:block h-[520px]">
            {/* Central glow */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-72 h-72 rounded-full bg-blue-500/6 animate-pulse-ring" />
            </div>

            {/* Dashboard mockup */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.5 }}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 glass rounded-2xl p-5 glow-blue"
            >
              <div className="flex items-center gap-2 mb-4">
                <div className="w-3 h-3 rounded-full bg-red-500/70" />
                <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
                <div className="w-3 h-3 rounded-full bg-green-500/70" />
                <span className="text-[10px] text-slate-500 ml-2">AttendX Dashboard</span>
              </div>
              <div className="space-y-2.5">
                <div className="h-2.5 bg-white/5 rounded-full w-3/4" />
                <div className="h-2.5 bg-white/5 rounded-full w-1/2" />
                <div className="grid grid-cols-3 gap-2 mt-4">
                  {["Present", "Absent", "Late"].map((s, i) => (
                    <div key={s} className="glass-light rounded-lg p-3 text-center">
                      <div className={`text-lg font-bold ${i === 0 ? "text-emerald-400" : i === 1 ? "text-red-400" : "text-amber-400"}`}>
                        {i === 0 ? "142" : i === 1 ? "8" : "5"}
                      </div>
                      <div className="text-[10px] text-slate-500 mt-1">{s}</div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-1.5 mt-3">
                  {[65, 85, 45, 90, 70, 80, 95].map((h, i) => (
                    <motion.div
                      key={i}
                      initial={{ height: 0 }}
                      animate={{ height: `${h}%` }}
                      transition={{ duration: 0.6, delay: 1 + i * 0.08 }}
                      className="flex-1 bg-gradient-to-t from-blue-500/40 to-teal-400/40 rounded-sm"
                      style={{ maxHeight: 48 }}
                    />
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Floating feature cards */}
            {floatingCards.map((card) => (
              <motion.div
                key={card.label}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: card.delay }}
                className={`absolute ${card.position} animate-float-slow`}
              >
                <div className="glass rounded-xl px-4 py-3 flex items-center gap-3 shadow-lg shadow-black/20">
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}>
                    <card.icon size={16} className="text-white" />
                  </div>
                  <span className="text-xs font-medium text-slate-300 whitespace-nowrap">{card.label}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
