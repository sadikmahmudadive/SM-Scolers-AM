"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import AnimatedSection from "./AnimatedSection";
import { Check, Zap, Building2, GraduationCap } from "lucide-react";

const plans = [
  {
    name: "Starter",
    icon: GraduationCap,
    price: "49",
    period: "one-time",
    description: "Perfect for small schools and single-site deployments.",
    features: [
      "1 biometric device",
      "Up to 200 users",
      "Firebase real-time sync",
      "SMS notifications",
      "PDF reports",
      "Email support",
    ],
    cta: "Get Starter",
    popular: false,
    color: "from-slate-500 to-slate-400",
  },
  {
    name: "Professional",
    icon: Zap,
    price: "99",
    period: "one-time",
    description: "For growing institutions that need more capacity and control.",
    features: [
      "Up to 3 biometric devices",
      "Unlimited users",
      "Firebase real-time sync",
      "SMS notifications",
      "PDF reports",
      "Priority support",
      "Auto-reconnect monitoring",
      "Custom branding",
    ],
    cta: "Get Professional",
    popular: true,
    color: "from-blue-500 to-cyan-400",
  },
  {
    name: "Enterprise",
    icon: Building2,
    price: "249",
    period: "one-time",
    description: "Multi-site deployment with dedicated support and customization.",
    features: [
      "Unlimited devices",
      "Unlimited users",
      "Firebase real-time sync",
      "SMS notifications",
      "PDF reports",
      "Dedicated support",
      "Auto-reconnect monitoring",
      "Custom branding",
      "Multi-site management",
      "On-site installation help",
    ],
    cta: "Contact Sales",
    popular: false,
    color: "from-purple-500 to-pink-400",
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
            Simple, <span className="gradient-text">transparent</span> pricing
          </h2>
          <p className="text-slate-400 text-lg">
            One-time payment. No subscriptions. Free updates for life.
          </p>
        </AnimatedSection>

        <div className="grid md:grid-cols-3 gap-6 lg:gap-8 max-w-5xl mx-auto">
          {plans.map((plan, idx) => (
            <AnimatedSection key={plan.name} delay={idx * 0.12}>
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
                    Most Popular
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
                  <span className="text-4xl font-extrabold text-white">${plan.price}</span>
                  <span className="text-sm text-slate-500 ml-2">{plan.period}</span>
                </div>

                <p className="text-sm text-slate-400 mb-6">{plan.description}</p>

                <Link
                  href="/register"
                  className={`block text-center py-3 px-6 rounded-xl font-semibold text-sm transition-all duration-300 mb-6 ${
                    plan.popular
                      ? "btn-primary"
                      : "btn-secondary"
                  }`}
                >
                  {plan.cta}
                </Link>

                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3 text-sm text-slate-300">
                      <Check
                        size={16}
                        className={`mt-0.5 flex-shrink-0 ${
                          plan.popular ? "text-blue-400" : "text-slate-500"
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
