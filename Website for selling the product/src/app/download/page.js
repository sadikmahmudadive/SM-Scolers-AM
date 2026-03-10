"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/AuthContext";
import {
  collection,
  query,
  where,
  orderBy,
  getDocs,
  doc,
  updateDoc,
  increment,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import toast from "react-hot-toast";
import AnimatedSection from "@/components/AnimatedSection";
import Footer from "@/components/Footer";
import {
  Download,
  Monitor,
  Calendar,
  HardDrive,
  Shield,
  FileText,
  Loader2,
  Lock,
  Gift,
  Building2,
  KeyRound,
} from "lucide-react";

export default function DownloadPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [freeReleases, setFreeReleases] = useState([]);
  const [customRelease, setCustomRelease] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pin, setPin] = useState("");
  const [pinLoading, setPinLoading] = useState(false);
  const [pinError, setPinError] = useState("");

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchFreeReleases = async () => {
      try {
        // fetch all free releases; removing orderBy avoids requiring a composite index
        const q = query(
          collection(db, "releases"),
          where("type", "==", "free")
        );
        const snap = await getDocs(q);
        setFreeReleases(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
      } catch (err) {
        // collection may not exist yet or query failed (missing index etc.)
        console.error("fetchFreeReleases error", err);
      } finally {
        setLoading(false);
      }
    };
    if (user) fetchFreeReleases();
  }, [user]);

  const handleDownload = async (release) => {
    try {
      await updateDoc(doc(db, "releases", release.id), {
        downloads: increment(1),
      });
    } catch {
      // non-critical
    }
    window.open(release.downloadUrl, "_blank");
  };

  const handlePinSubmit = async (e) => {
    e.preventDefault();
    if (!pin.trim()) return;
    setPinLoading(true);
    setPinError("");
    setCustomRelease(null);

    try {
      const q = query(
        collection(db, "releases"),
        where("type", "==", "custom"),
        where("pin", "==", pin.trim())
      );
      const snap = await getDocs(q);

      if (snap.empty) {
        setPinError("Invalid PIN. Please check and try again.");
        toast.error("Invalid PIN");
      } else {
        const release = { id: snap.docs[0].id, ...snap.docs[0].data() };
        setCustomRelease(release);
        toast.success(`Found: ${release.institutionName || release.version}`);
      }
    } catch {
      setPinError("Something went wrong. Please try again.");
    } finally {
      setPinLoading(false);
    }
  };

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  return (
    <>
      <div className="min-h-screen pt-24 pb-16">
        <div className="fixed inset-0 hero-grid opacity-15 pointer-events-none" />
        <div className="fixed top-1/4 right-1/4 w-[500px] h-[400px] bg-blue-500/5 rounded-full blur-[120px] pointer-events-none" />

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <AnimatedSection className="mb-12">
            <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-3">
              Download <span className="gradient-text">AttendX</span>
            </h1>
            <p className="text-slate-400 text-lg">
              Get the free version or download your custom institutional build.
            </p>
          </AnimatedSection>

          {/* System requirements */}
          <AnimatedSection delay={0.1} className="mb-10">
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Monitor size={18} className="text-blue-400 flex-shrink-0" />
                System Requirements
              </h2>
              <div className="grid sm:grid-cols-2 gap-4 text-sm text-slate-400">
                <div className="flex items-start gap-3">
                  <Shield size={16} className="text-slate-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-slate-300 font-medium">OS:</span> Windows 10
                    / 11 (64-bit)
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <HardDrive size={16} className="text-slate-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-slate-300 font-medium">Disk:</span> 100 MB
                    free space
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <FileText size={16} className="text-slate-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-slate-300 font-medium">Hardware:</span> ZK
                    Teco Biometric Device
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <FileText size={16} className="text-slate-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-slate-300 font-medium">Optional:</span> GSM
                    Modem for SMS
                  </div>
                </div>
              </div>
            </div>
          </AnimatedSection>

          {/* ===== FREE VERSION ===== */}
          <AnimatedSection delay={0.2} className="mb-12">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Gift size={18} className="text-emerald-400 flex-shrink-0" />
              Free Version
            </h2>

            {loading ? (
              <div className="glass rounded-2xl p-12 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
              </div>
            ) : freeReleases.length === 0 ? (
              <div className="glass rounded-2xl p-12 text-center">
                <Download size={40} className="mx-auto text-slate-600 mb-4" />
                <p className="text-slate-400 mb-2">No free release available yet</p>
                <p className="text-sm text-slate-500">
                  Check back soon — the free version will be uploaded shortly.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {freeReleases.map((release, idx) => (
                  <motion.div
                    key={release.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`glass rounded-2xl p-6 ${
                      idx === 0 ? "glow-accent border border-emerald-500/15" : ""
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-3 mb-1">
                          <h3 className="text-lg font-bold text-white">
                            {release.version}
                          </h3>
                          {idx === 0 && (
                            <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-xs font-medium border border-emerald-500/20">
                              Latest Free
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-500">
                          <span className="flex items-center gap-1.5">
                            <Calendar size={13} className="flex-shrink-0" />
                            {release.createdAt?.toDate
                              ? release.createdAt.toDate().toLocaleDateString()
                              : "—"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <HardDrive size={13} className="flex-shrink-0" />
                            {release.fileSize || "—"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <Download size={13} className="flex-shrink-0" />
                            {release.downloads || 0} downloads
                          </span>
                        </div>
                        {release.notes && (
                          <p className="text-sm text-slate-400 mt-2">
                            {release.notes}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => handleDownload(release)}
                        className="btn-primary flex items-center gap-2 whitespace-nowrap !py-2.5 !px-6"
                      >
                        <Download size={16} />
                        Download Free
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </AnimatedSection>

          {/* ===== CUSTOM BUILD — PIN ENTRY ===== */}
          <AnimatedSection delay={0.3}>
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Building2 size={18} className="text-blue-400 flex-shrink-0" />
              Custom Institutional Build
            </h2>

            <div className="glass rounded-2xl p-6 glow-blue border border-blue-500/10">
              <div className="flex items-start gap-3 mb-6">
                <Lock size={18} className="text-blue-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm text-slate-300 font-medium mb-1">
                    Enter your institution&apos;s PIN
                  </p>
                  <p className="text-xs text-slate-500">
                    If your institution has requested a custom build, enter the
                    PIN provided after payment to download your branded app.
                  </p>
                </div>
              </div>

              <form onSubmit={handlePinSubmit} className="flex gap-3 mb-4">
                <div className="relative flex-1">
                  <KeyRound
                    size={16}
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"
                  />
                  <input
                    type="text"
                    placeholder="Enter your PIN"
                    value={pin}
                    onChange={(e) => {
                      setPin(e.target.value);
                      setPinError("");
                    }}
                    className="input-dark pl-11"
                  />
                </div>
                <button
                  type="submit"
                  disabled={pinLoading || !pin.trim()}
                  className="btn-primary flex items-center gap-2 !py-3 !px-6 disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap"
                >
                  {pinLoading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <>
                      <Lock size={16} /> Verify
                    </>
                  )}
                </button>
              </form>

              {pinError && (
                <p className="text-sm text-red-400 mb-4">{pinError}</p>
              )}

              {/* Custom release result */}
              {customRelease && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-light rounded-xl p-5 mt-4"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-lg font-bold text-white">
                          {customRelease.institutionName || customRelease.version}
                        </h3>
                        <span className="px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-xs font-medium border border-blue-500/20">
                          Custom Build
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-slate-500">
                        <span className="flex items-center gap-1.5">
                          <Calendar size={13} className="flex-shrink-0" />
                          {customRelease.createdAt?.toDate
                            ? customRelease.createdAt.toDate().toLocaleDateString()
                            : "—"}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <HardDrive size={13} className="flex-shrink-0" />
                          {customRelease.fileSize || "—"}
                        </span>
                      </div>
                      {customRelease.notes && (
                        <p className="text-sm text-slate-400 mt-2">
                          {customRelease.notes}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDownload(customRelease)}
                      className="btn-primary flex items-center gap-2 whitespace-nowrap !py-2.5 !px-6"
                    >
                      <Download size={16} />
                      Download
                    </button>
                  </div>
                </motion.div>
              )}
            </div>
          </AnimatedSection>
        </div>
      </div>
      <Footer />
    </>
  );
}
