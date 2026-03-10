"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import AnimatedSection from "./AnimatedSection";
import { Check, Gift, Building2, ArrowRight } from "lucide-react";

const plans = [
  {
    name: "Free",
    icon: Gift,
    price: "0",
    period: "forever",
    description:
      "Explore all core features with the free version. Perfect for evaluating the system before committing.",
    features: [
      "1 biometric device",
      "Up to 100 members",
      "Real-time cloud sync",
      "SMS notifications",
      "PDF reports",
      "Live dashboard",
      "Community support",
    ],
    cta: "Download Free",
    href: "/download",
    popular: false,
    color: "from-emerald-500 to-teal-400",
  },
  {
    name: "Custom Build",
    icon: Building2,
    price: "Custom",
    period: "per institution",
    description:
      "Get a fully branded version with your institution's name, logo, and custom features. Delivered via secure PIN.",
    features: [
      "Unlimited devices",
      "Unlimited members",
      "Custom app name & branding",
      "Custom features on request",
      "Real-time cloud sync",
      "SMS notifications",
      "PDF reports",
      "Dedicated support",
      "PIN-protected download",
      "Priority updates",
    ],
    cta: "Request Custom Build",
    href: "/register",
    popular: true,
    color: "from-blue-500 to-cyan-400",
  },
];

export default function Pricing() {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  return (
    <section id="pricing" className="relative py-24 lg:py-32">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-purple-500/[0.02] to-transparent" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center max-w-2xl mx-auto mb-16">
          <span className="inline-block text-xs font-semibold tracking-widest uppercase text-purple-400 mb-3">
            Pricing
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold mb-4">
            Try free, then go{" "}
            <span className="gradient-text">custom</span>
          </h2>
          <p className="text-slate-400 text-lg">
            Download the free version to explore features. When you&apos;re ready,
            request a custom build tailored to your institution.
          </p>
        </AnimatedSection>

        {/* How it works */}
        <AnimatedSection delay={0.1} className="mb-16">
          <div className="glass rounded-2xl p-8 max-w-3xl mx-auto">
            <h3 className="text-lg font-semibold text-white mb-6 text-center">
              How Custom Builds Work
            </h3>
            <div className="grid sm:grid-cols-4 gap-6 text-center">
              {[
                { step: "1", label: "Try the free version and explore features" },
                { step: "2", label: "Request a custom build with your requirements" },
                { step: "3", label: "Admin builds and uploads your custom app with a PIN" },
                { step: "4", label: "Download your branded app using the PIN after payment" },
              ].map((item) => (
                <div key={item.step} className="flex flex-col items-center gap-2">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-teal-400 flex items-center justify-center text-sm font-bold text-white">
                    {item.step}
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {item.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </AnimatedSection>

        <div className="grid md:grid-cols-2 gap-6 lg:gap-8 max-w-4xl mx-auto">
          {plans.map((plan, idx) => (
            <AnimatedSection key={plan.name} delay={0.2 + idx * 0.12}>
              <motion.div
                onHoverStart={() => setHoveredIndex(idx)}
                onHoverEnd={() => setHoveredIndex(null)}
                className={`relative h-full rounded-2xl p-7 transition-all duration-300 ${
                  plan.popular
                    ? "glass glow-blue border border-blue-500/20"
                    : "glass hover:bg-white/[0.03]"
                } ${hoveredIndex === idx ? "-translate-y-2" : ""}`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 text-xs font-semibold text-white shadow-lg shadow-blue-500/30">
                    Recommended
                  </div>
                )}

                <div className="flex items-center gap-3 mb-4">
                  <div
                    className={`w-10 h-10 rounded-xl bg-gradient-to-br ${plan.color} flex items-center justify-center`}
                  >
                    <plan.icon size={18} className="text-white" />
                  </div>
                  <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                </div>

                <div className="mb-4">
                  {plan.price === "Custom" ? (
                    <span className="text-3xl font-extrabold gradient-text">Custom</span>
                  ) : (
                    <>
                      <span className="text-4xl font-extrabold text-white">${plan.price}</span>
                      <span className="text-sm text-slate-500 ml-2">{plan.period}</span>
                    </>
                  )}
                </div>

                <p className="text-sm text-slate-400 mb-6">{plan.description}</p>

                <Link
                  href={plan.href}
                  className={`block text-center py-3 px-6 rounded-xl font-semibold text-sm transition-all duration-300 mb-6 ${
                    plan.popular ? "btn-primary" : "btn-secondary"
                  }`}
                >
                  {plan.cta}
                </Link>

                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li
                      key={feature}
                      className="flex items-start gap-3 text-sm text-slate-300"
                    >
                      <Check
                        size={16}
                        className={`mt-0.5 flex-shrink-0 ${
                          plan.popular ? "text-blue-400" : "text-emerald-400"
                        }`}
                      />
                      {feature}
                    </li>
                  ))}
                </ul>
              </motion.div>
            </AnimatedSection>
          ))}
        </div>
      </div>
    </section>
  );
}
