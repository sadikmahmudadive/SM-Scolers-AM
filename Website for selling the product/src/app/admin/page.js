"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/AuthContext";
import {
  collection,
  query,
  orderBy,
  getDocs,
  addDoc,
  deleteDoc,
  doc,
  serverTimestamp,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import { uploadToCloudinary } from "@/lib/cloudinary";
import toast from "react-hot-toast";
import Footer from "@/components/Footer";
import {
  Upload,
  Trash2,
  Plus,
  Package,
  Users,
  Download,
  BarChart3,
  Loader2,
  X,
  FileText,
} from "lucide-react";

export default function AdminPage() {
  const { user, profile, loading: authLoading } = useAuth();
  const router = useRouter();
  const fileInputRef = useRef(null);

  const [releases, setReleases] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Upload form state
  const [version, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (!authLoading && (!user || profile?.role !== "admin")) {
      router.push("/");
    }
  }, [user, profile, authLoading, router]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [relSnap, userSnap] = await Promise.all([
          getDocs(query(collection(db, "releases"), orderBy("createdAt", "desc"))),
          getDocs(collection(db, "users")),
        ]);
        setReleases(relSnap.docs.map((d) => ({ id: d.id, ...d.data() })));
        setUsers(userSnap.docs.map((d) => ({ id: d.id, ...d.data() })));
      } catch {
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    if (user && profile?.role === "admin") fetchData();
  }, [user, profile]);

  const totalDownloads = releases.reduce(
    (sum, r) => sum + (r.downloads || 0),
    0
  );

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !version) return;

    setUploading(true);
    try {
      // Upload to Cloudinary
      const result = await uploadToCloudinary(file, "releases");

      // Build a human-readable file size
      const sizeBytes = file.size;
      let fileSize;
      if (sizeBytes > 1024 * 1024) {
        fileSize = `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
      } else {
        fileSize = `${(sizeBytes / 1024).toFixed(0)} KB`;
      }

      // Create Firestore doc
      await addDoc(collection(db, "releases"), {
        version,
        notes,
        downloadUrl: result.secure_url,
        cloudinaryId: result.public_id,
        fileSize,
        downloads: 0,
        createdAt: serverTimestamp(),
      });

      toast.success("Release uploaded successfully!");
      setShowUploadModal(false);
      setVersion("");
      setNotes("");
      setFile(null);

      // Refresh releases
      const snap = await getDocs(
        query(collection(db, "releases"), orderBy("createdAt", "desc"))
      );
      setReleases(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
    } catch {
      toast.error("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (release) => {
    if (!confirm(`Delete release ${release.version}?`)) return;
    try {
      await deleteDoc(doc(db, "releases", release.id));
      setReleases((prev) => prev.filter((r) => r.id !== release.id));
      toast.success("Release deleted");
    } catch {
      toast.error("Failed to delete release");
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  if (profile?.role !== "admin") return null;

  return (
    <>
      <div className="min-h-screen pt-24 pb-16">
        <div className="fixed inset-0 hero-grid opacity-10 pointer-events-none" />

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10">
            <div>
              <h1 className="text-3xl font-extrabold text-white mb-1">
                Admin <span className="gradient-text">Dashboard</span>
              </h1>
              <p className="text-slate-400">
                Manage releases, users, and downloads.
              </p>
            </div>
            <button
              onClick={() => setShowUploadModal(true)}
              className="btn-primary inline-flex items-center gap-2 !py-2.5"
            >
              <Plus size={16} /> New Release
            </button>
          </div>

          {/* Stats */}
          <div className="grid sm:grid-cols-3 gap-5 mb-10">
            {[
              {
                icon: Package,
                label: "Releases",
                value: releases.length,
                color: "from-blue-500 to-cyan-400",
              },
              {
                icon: Users,
                label: "Users",
                value: users.length,
                color: "from-purple-500 to-pink-400",
              },
              {
                icon: Download,
                label: "Total Downloads",
                value: totalDownloads,
                color: "from-emerald-500 to-teal-400",
              },
            ].map((stat) => (
              <div key={stat.label} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center`}
                  >
                    <stat.icon size={18} className="text-white" />
                  </div>
                  <span className="text-sm text-slate-400">{stat.label}</span>
                </div>
                <div className="text-3xl font-extrabold text-white">
                  {stat.value}
                </div>
              </div>
            ))}
          </div>

          {/* Releases table */}
          <div className="glass rounded-2xl overflow-hidden mb-10">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <BarChart3 size={16} className="text-blue-400" />
              <h2 className="font-semibold text-white">Releases</h2>
            </div>
            {releases.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                No releases yet. Click &ldquo;New Release&rdquo; to upload one.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="px-6 py-3 font-medium">Version</th>
                      <th className="px-6 py-3 font-medium">Date</th>
                      <th className="px-6 py-3 font-medium">Size</th>
                      <th className="px-6 py-3 font-medium">Downloads</th>
                      <th className="px-6 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {releases.map((release) => (
                      <tr
                        key={release.id}
                        className="border-t border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-4 font-medium text-white">
                          {release.version}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {release.createdAt?.toDate
                            ? release.createdAt.toDate().toLocaleDateString()
                            : "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {release.fileSize || "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {release.downloads || 0}
                        </td>
                        <td className="px-6 py-4">
                          <button
                            onClick={() => handleDelete(release)}
                            className="text-red-400 hover:text-red-300 transition-colors p-1.5 rounded-lg hover:bg-red-500/10"
                          >
                            <Trash2 size={15} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Users table */}
          <div className="glass rounded-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <Users size={16} className="text-purple-400" />
              <h2 className="font-semibold text-white">Users</h2>
            </div>
            {users.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                No registered users yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="px-6 py-3 font-medium">Name</th>
                      <th className="px-6 py-3 font-medium">Email</th>
                      <th className="px-6 py-3 font-medium">Role</th>
                      <th className="px-6 py-3 font-medium">Joined</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr
                        key={u.id}
                        className="border-t border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-4 text-white">
                          {u.name || "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {u.email}
                        </td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              u.role === "admin"
                                ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                : "bg-slate-500/10 text-slate-400 border border-slate-500/20"
                            }`}
                          >
                            {u.role}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {u.createdAt?.toDate
                            ? u.createdAt.toDate().toLocaleDateString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => !uploading && setShowUploadModal(false)}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative glass rounded-2xl p-8 w-full max-w-md glow-blue"
          >
            <button
              onClick={() => !uploading && setShowUploadModal(false)}
              className="absolute top-4 right-4 text-slate-500 hover:text-white"
            >
              <X size={18} />
            </button>

            <h2 className="text-xl font-bold text-white mb-1">
              Upload New Release
            </h2>
            <p className="text-sm text-slate-400 mb-6">
              Upload the MSI installer to Cloudinary.
            </p>

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Version
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. v13.0"
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  className="input-dark"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Release Notes
                </label>
                <textarea
                  rows={3}
                  placeholder="What's new in this version..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="input-dark resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Installer File
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  required
                  accept=".msi,.exe"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full py-8 rounded-xl border-2 border-dashed border-white/10 hover:border-blue-500/30 transition-colors flex flex-col items-center gap-2 text-slate-400 hover:text-slate-300"
                >
                  {file ? (
                    <>
                      <FileText size={24} className="text-blue-400" />
                      <span className="text-sm font-medium text-white">
                        {file.name}
                      </span>
                      <span className="text-xs text-slate-500">
                        {(file.size / (1024 * 1024)).toFixed(1)} MB
                      </span>
                    </>
                  ) : (
                    <>
                      <Upload size={24} />
                      <span className="text-sm">Click to select installer</span>
                      <span className="text-xs text-slate-500">.msi or .exe</span>
                    </>
                  )}
                </button>
              </div>

              <button
                type="submit"
                disabled={uploading || !file}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:pointer-events-none"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Upload Release
                  </>
                )}
              </button>
            </form>
          </motion.div>
        </div>
      )}

      <Footer />
    </>
  );
}
