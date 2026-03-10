"use client";

import Link from "next/link";
import AnimatedSection from "./AnimatedSection";
import { ArrowRight } from "lucide-react";

export default function CTA() {
  return (
    <section className="relative py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection>
          <div className="relative rounded-3xl overflow-hidden">
            {/* Gradient background */}
            <div className="absolute inset-0 bg-gradient-to-br from-[#0078d7] via-[#005a9e] to-[#00d4aa] opacity-90" />
            <div className="absolute inset-0 hero-grid opacity-10" />
            <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full blur-[100px] -translate-y-1/2 translate-x-1/3" />

            <div className="relative px-8 py-16 md:px-16 md:py-20 text-center">
              <h2 className="text-3xl md:text-4xl lg:text-5xl font-extrabold text-white mb-6 leading-tight">
                Ready to simplify your
                <br />
                attendance management?
              </h2>
              <p className="text-lg text-blue-100/80 max-w-xl mx-auto mb-8">
                Try the free version or get a custom build with your institution&apos;s
                branding. Set up in minutes.
              </p>
              <div className="flex flex-wrap gap-4 justify-center">
                <Link
                  href="/download"
                  className="inline-flex items-center gap-2 bg-white text-[#005a9e] font-semibold px-8 py-3.5 rounded-xl hover:bg-white/90 transition-all hover:-translate-y-0.5 shadow-lg shadow-black/20"
                >
                  Try Free Version
                  <ArrowRight size={18} />
                </Link>
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 bg-white/10 text-white font-semibold px-8 py-3.5 rounded-xl border border-white/20 hover:bg-white/20 transition-all hover:-translate-y-0.5"
                >
                  Request Custom Build
                </Link>
              </div>
            </div>
          </div>
        </AnimatedSection>
      </div>
    </section>
  );
}
