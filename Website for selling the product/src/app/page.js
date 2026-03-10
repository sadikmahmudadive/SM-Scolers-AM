import Hero from "@/components/Hero";
import Features from "@/components/Features";
import Pricing from "@/components/Pricing";
import Testimonials from "@/components/Testimonials";
import FAQ from "@/components/FAQ";
import CTA from "@/components/CTA";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <>
      <Hero />
      <div className="section-divider" />
      <Features />
      <div className="section-divider" />
      <Pricing />
      <div className="section-divider" />
      <Testimonials />
      <div className="section-divider" />
      <FAQ />
      <CTA />
      <Footer />
    </>
  );
}
