"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AnimatedSection from "./AnimatedSection";
import { Quote, ChevronLeft, ChevronRight, Star } from "lucide-react";

const testimonials = [
  {
    name: "Amina Hassan",
    role: "School Administrator",
    org: "Greenfield Academy",
    text: "AttendX transformed how we track attendance. The biometric scanning is incredibly fast, and the real-time sync means I always have up-to-date data. We started with the free version and upgraded to a custom build with our school's name.",
    rating: 5,
  },
  {
    name: "John Mwangi",
    role: "IT Manager",
    org: "TechBridge Training Institute",
    text: "The auto-reconnect feature is a game-changer. Even when our network drops, the system catches up automatically. We requested a custom build and had it running within days.",
    rating: 5,
  },
  {
    name: "Fatima Ali",
    role: "Principal",
    org: "Sunrise Primary School",
    text: "Generating PDF reports used to take hours. Now I get detailed attendance reports in seconds. The free version convinced us, and our custom branded app looks amazing.",
    rating: 5,
  },
  {
    name: "David Ochieng",
    role: "Operations Director",
    org: "East Campus College",
    text: "We deployed AttendX across three campuses with a single custom build. The PIN-based download system made distribution to our IT team seamless.",
    rating: 5,
  },
];

export default function Testimonials() {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(0);

  const nextSlide = useCallback(() => {
    setDirection(1);
    setCurrent((prev) => (prev + 1) % testimonials.length);
  }, []);

  const prevSlide = () => {
    setDirection(-1);
    setCurrent((prev) => (prev - 1 + testimonials.length) % testimonials.length);
  };

  useEffect(() => {
    const timer = setInterval(nextSlide, 6000);
    return () => clearInterval(timer);
  }, [nextSlide]);

  const variants = {
    enter: (dir) => ({ x: dir > 0 ? 200 : -200, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir) => ({ x: dir > 0 ? -200 : 200, opacity: 0 }),
  };

  return (
    <section id="testimonials" className="relative py-24 lg:py-32">
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-teal-500/[0.02] to-transparent" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AnimatedSection className="text-center max-w-2xl mx-auto mb-16">
          <span className="inline-block text-xs font-semibold tracking-widest uppercase text-teal-400 mb-3">
            Testimonials
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold mb-4">
            Trusted by <span className="gradient-text">educators</span> everywhere
          </h2>
          <p className="text-slate-400 text-lg">
            See what our users say about AttendX.
          </p>
        </AnimatedSection>

        <div className="max-w-3xl mx-auto">
          <div className="relative glass rounded-2xl p-8 md:p-12 min-h-[280px] glow-accent overflow-hidden">
            <Quote
              size={48}
              className="absolute top-6 left-6 text-blue-500/10"
            />

            <AnimatePresence mode="wait" custom={direction}>
              <motion.div
                key={current}
                custom={direction}
                variants={variants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.4, ease: "easeInOut" }}
                className="relative z-10"
              >
                <div className="flex gap-1 mb-4">
                  {Array.from({ length: testimonials[current].rating }).map(
                    (_, i) => (
                      <Star
                        key={i}
                        size={16}
                        className="text-amber-400 fill-amber-400"
                      />
                    )
                  )}
                </div>

                <p className="text-lg md:text-xl text-slate-300 leading-relaxed mb-8 italic">
                  &ldquo;{testimonials[current].text}&rdquo;
                </p>

                <div>
                  <div className="font-semibold text-white">
                    {testimonials[current].name}
                  </div>
                  <div className="text-sm text-slate-500">
                    {testimonials[current].role} · {testimonials[current].org}
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          </div>

          {/* Controls */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <button
              onClick={prevSlide}
              className="w-10 h-10 rounded-full glass flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <ChevronLeft size={18} />
            </button>

            <div className="flex gap-2">
              {testimonials.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setDirection(idx > current ? 1 : -1);
                    setCurrent(idx);
                  }}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    idx === current
                      ? "w-8 bg-gradient-to-r from-blue-500 to-teal-400"
                      : "w-1.5 bg-slate-700 hover:bg-slate-600"
                  }`}
                />
              ))}
            </div>

            <button
              onClick={nextSlide}
              className="w-10 h-10 rounded-full glass flex items-center justify-center text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
