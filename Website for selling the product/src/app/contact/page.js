"use client";

import { useState } from "react";
import { addDoc, collection, serverTimestamp } from "firebase/firestore";
import { db } from "@/lib/firebase";
import toast from "react-hot-toast";
import AnimatedSection from "@/components/AnimatedSection";
import Footer from "@/components/Footer";

export default function ContactPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !message.trim()) {
      toast.error("Please fill all fields");
      return;
    }
    setSubmitting(true);
    try {
      await addDoc(collection(db, "requests"), {
        name: name.trim(),
        email: email.trim(),
        message: message.trim(),
        createdAt: serverTimestamp(),
      });
      toast.success("Request submitted — we'll be in touch soon!");
      setName("");
      setEmail("");
      setMessage("");
    } catch (err) {
      console.error(err);
      toast.error("Failed to send request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="min-h-screen pt-24 pb-16">
        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <AnimatedSection>
            <h1 className="text-3xl font-extrabold text-white mb-4">
              Request a Custom Build
            </h1>
            <p className="text-slate-400 mb-8">
              Fill out the form below and our team will contact you to discuss
              your institution's requirements.
            </p>
          </AnimatedSection>

          <AnimatedSection delay={0.1}>
            <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Institution / Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input-dark w-full px-4"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input-dark w-full px-4"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">
                  Message / Requirements
                </label>
                <textarea
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="input-dark w-full px-4 resize-none"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="btn-primary px-6 py-3 disabled:opacity-50"
              >
                {submitting ? "Sending…" : "Submit Request"}
              </button>
            </form>
          </AnimatedSection>
        </div>
      </div>
      <Footer />
    </>
  );
}
