"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/AuthContext";
import {
  collection,
  query,
  orderBy,
  getDocs,
  doc,
  updateDoc,
  increment,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
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
} from "lucide-react";

export default function DownloadPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [releases, setReleases] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    const fetchReleases = async () => {
      try {
        const q = query(
          collection(db, "releases"),
          orderBy("createdAt", "desc")
        );
        const snap = await getDocs(q);
        setReleases(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
      } catch {
        // Firestore may not have the collection yet
      } finally {
        setLoading(false);
      }
    };
    if (user) fetchReleases();
  }, [user]);

  const handleDownload = async (release) => {
    // Track download count
    try {
      await updateDoc(doc(db, "releases", release.id), {
        downloads: increment(1),
      });
    } catch {
      // non-critical
    }
    window.open(release.downloadUrl, "_blank");
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
              Download <span className="gradient-text">SM Scolers</span>
            </h1>
            <p className="text-slate-400 text-lg">
              Get the latest version of the attendance management system.
            </p>
          </AnimatedSection>

          {/* System requirements */}
          <AnimatedSection delay={0.1} className="mb-10">
            <div className="glass rounded-2xl p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Monitor size={18} className="text-blue-400" />
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

          {/* Releases */}
          <AnimatedSection delay={0.2}>
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Download size={18} className="text-emerald-400" />
              Available Releases
            </h2>

            {loading ? (
              <div className="glass rounded-2xl p-12 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
              </div>
            ) : releases.length === 0 ? (
              <div className="glass rounded-2xl p-12 text-center">
                <Download size={40} className="mx-auto text-slate-600 mb-4" />
                <p className="text-slate-400 mb-2">No releases available yet</p>
                <p className="text-sm text-slate-500">
                  Check back soon — the admin will upload the latest installer.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {releases.map((release, idx) => (
                  <motion.div
                    key={release.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`glass rounded-2xl p-6 ${
                      idx === 0 ? "glow-blue border border-blue-500/15" : ""
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
                              Latest
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-slate-500">
                          <span className="flex items-center gap-1.5">
                            <Calendar size={13} />
                            {release.createdAt?.toDate
                              ? release.createdAt.toDate().toLocaleDateString()
                              : "—"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <HardDrive size={13} />
                            {release.fileSize || "—"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <Download size={13} />
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
                        Download
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </AnimatedSection>
        </div>
      </div>
      <Footer />
    </>
  );
}
