"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AnimatedSection from "./AnimatedSection";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "What biometric devices are supported?",
    a: "AttendX works with ZK Teco biometric fingerprint devices, including popular models like ZK4500, ZKTeco K40, and other ZK-compatible hardware. The system connects via TCP/IP over your local network.",
  },
  {
    q: "What's included in the free version?",
    a: "The free version includes all core features: biometric attendance capture, real-time cloud sync, SMS notifications, PDF reports, and the live dashboard. It supports 1 device and up to 100 members — perfect for evaluating the system.",
  },
  {
    q: "How do custom builds work?",
    a: "When you request a custom build, our team works with your institution to create a version branded with your name, logo, and any custom features you need. Once ready, the admin uploads it with a secure PIN. After payment, you use that PIN to download your custom app.",
  },
  {
    q: "What is the download PIN?",
    a: "The download PIN is a secure code assigned to your institution's custom build. After the admin uploads your custom app and you complete payment, you'll receive a PIN to access and download your branded installer.",
  },
  {
    q: "Do I need an internet connection?",
    a: "The app works offline for attendance capture and stores records locally. An internet connection is needed for cloud sync and SMS notifications. When connectivity returns, all pending records sync automatically.",
  },
  {
    q: "Can I use this for multiple locations?",
    a: "Yes! Custom builds support unlimited devices and locations. All data syncs to a single cloud project, giving you a unified view of attendance across all your sites.",
  },
  {
    q: "Is my data secure?",
    a: "Absolutely. All data is encrypted in transit using HTTPS/TLS. Firebase security rules restrict access to authorized users only. Local data is stored securely on your machine with no third-party access.",
  },
  {
    q: "What operating systems are supported?",
    a: "AttendX currently supports Windows 10 and Windows 11. The installer is a standard MSI package that handles the complete setup process.",
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null);

  return (
    <section id="faq" className="relative py-24 lg:py-32">
      <div className="relative max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center mb-16">
          <span className="inline-block text-xs font-semibold tracking-widest uppercase text-amber-400 mb-3">
            FAQ
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold mb-4">
            Frequently asked <span className="gradient-text">questions</span>
          </h2>
          <p className="text-slate-400 text-lg">
            Got questions? We have answers.
          </p>
        </AnimatedSection>

        <div className="space-y-3">
          {faqs.map((faq, idx) => (
            <AnimatedSection key={idx} delay={idx * 0.06}>
              <div className="glass rounded-xl overflow-hidden">
                <button
                  onClick={() => setOpenIndex(openIndex === idx ? null : idx)}
                  className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-white/[0.02] transition-colors"
                >
                  <span className="text-sm font-medium text-white pr-4">
                    {faq.q}
                  </span>
                  <ChevronDown
                    size={18}
                    className={`flex-shrink-0 text-slate-500 transition-transform duration-300 ${
                      openIndex === idx ? "rotate-180 text-blue-400" : ""
                    }`}
                  />
                </button>
                <AnimatePresence>
                  {openIndex === idx && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                    >
                      <div className="px-6 pb-4 text-sm text-slate-400 leading-relaxed">
                        {faq.a}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </AnimatedSection>
          ))}
        </div>
      </div>
    </section>
  );
}
