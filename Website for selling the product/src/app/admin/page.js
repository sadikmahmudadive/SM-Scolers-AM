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
  addDoc,
  deleteDoc,
  doc,
  serverTimestamp,
} from "firebase/firestore";
import { db } from "@/lib/firebase";
import toast from "react-hot-toast";
import Footer from "@/components/Footer";
import {
  Trash2,
  Users,
  Download,
  Loader2,
  X,
  Gift,
  Building2,
  KeyRound,
  Copy,
  Eye,
  EyeOff,
  Link2,
  Plus,
} from "lucide-react";

function generatePIN() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let pin = "";
  const arr = new Uint32Array(6);
  crypto.getRandomValues(arr);
  for (let i = 0; i < 6; i++) {
    pin += chars[arr[i] % chars.length];
  }
  return pin;
}

export default function AdminPage() {
  const { user, profile, loading: authLoading } = useAuth();
  const router = useRouter();

  const [releases, setReleases] = useState([]);
  const [users, setUsers] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [visiblePins, setVisiblePins] = useState({});

  // Upload form state
  const [uploadType, setUploadType] = useState("free"); // "free" | "custom"
  const [version, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [fileSize, setFileSize] = useState("");
  const [institutionName, setInstitutionName] = useState("");
  const [pin, setPin] = useState("");

  useEffect(() => {
    if (!authLoading && (!user || profile?.role !== "admin")) {
      router.push("/");
    }
  }, [user, profile, authLoading, router]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [relSnap, userSnap, reqSnap] = await Promise.all([
          getDocs(query(collection(db, "releases"), orderBy("createdAt", "desc"))),
          getDocs(collection(db, "users")),
          getDocs(collection(db, "requests")),
        ]);
        setReleases(relSnap.docs.map((d) => ({ id: d.id, ...d.data() })));
        setUsers(userSnap.docs.map((d) => ({ id: d.id, ...d.data() })));
        setRequests(reqSnap.docs.map((d) => ({ id: d.id, ...d.data() })));
      } catch {
        toast.error("Failed to load data");
      } finally {
        setLoading(false);
      }
    };
    if (user && profile?.role === "admin") fetchData();
  }, [user, profile]);

  const freeReleases = releases.filter((r) => r.type === "free" || !r.type);
  const customReleases = releases.filter((r) => r.type === "custom");
  const totalDownloads = releases.reduce(
    (sum, r) => sum + (r.downloads || 0),
    0
  );

  const openUploadModal = (type) => {
    setUploadType(type);
    setVersion("");
    setNotes("");
    setDownloadUrl("");
    setFileSize("");
    setInstitutionName("");
    setPin(type === "custom" ? generatePIN() : "");
    setShowUploadModal(true);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!downloadUrl.trim() || !version.trim()) return;
    if (uploadType === "custom" && !institutionName.trim()) {
      toast.error("Institution name is required for custom builds");
      return;
    }

    setUploading(true);
    try {
      const releaseDoc = {
        version: version.trim(),
        notes,
        type: uploadType,
        downloadUrl: downloadUrl.trim(),
        fileSize: fileSize.trim() || "—",
        downloads: 0,
        createdAt: serverTimestamp(),
      };

      if (uploadType === "custom") {
        releaseDoc.institutionName = institutionName.trim();
        releaseDoc.pin = pin;
      }

      await addDoc(collection(db, "releases"), releaseDoc);

      toast.success(
        uploadType === "custom"
          ? `Custom build added! PIN: ${pin}`
          : "Free release added!"
      );
      setShowUploadModal(false);

      // Refresh releases
      const snap = await getDocs(
        query(collection(db, "releases"), orderBy("createdAt", "desc"))
      );
      setReleases(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
    } catch (err) {
      toast.error(err.message || "Failed to add release.");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (release) => {
    const label =
      release.type === "custom"
        ? `custom build for ${release.institutionName || release.version}`
        : `free release ${release.version}`;
    if (!confirm(`Delete ${label}?`)) return;
    try {
      await deleteDoc(doc(db, "releases", release.id));
      setReleases((prev) => prev.filter((r) => r.id !== release.id));
      toast.success("Release deleted");
    } catch {
      toast.error("Failed to delete release");
    }
  };

  const copyPin = (pinValue) => {
    navigator.clipboard.writeText(pinValue);
    toast.success("PIN copied!");
  };

  const togglePinVisibility = (id) => {
    setVisiblePins((prev) => ({ ...prev, [id]: !prev[id] }));
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
                Manage free releases, custom builds, and users.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => openUploadModal("free")}
                className="btn-primary inline-flex items-center gap-2 !py-2.5"
              >
                <Gift size={16} /> Free Release
              </button>
              <button
                onClick={() => openUploadModal("custom")}
                className="inline-flex items-center gap-2 !py-2.5 px-5 rounded-xl font-medium text-sm border border-blue-500/30 text-blue-400 hover:bg-blue-500/10 transition-colors"
              >
                <Building2 size={16} /> Custom Build
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="grid sm:grid-cols-4 gap-5 mb-10">
            {[
              {
                icon: Gift,
                label: "Free Releases",
                value: freeReleases.length,
                color: "from-emerald-500 to-teal-400",
              },
              {
                icon: Building2,
                label: "Custom Builds",
                value: customReleases.length,
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
                color: "from-orange-500 to-amber-400",
              },
            ].map((stat) => (
              <div key={stat.label} className="glass rounded-2xl p-6">
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className={`w-10 h-10 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center flex-shrink-0`}
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

          {/* Free Releases table */}
          <div className="glass rounded-2xl overflow-hidden mb-10">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <Gift size={16} className="text-emerald-400 flex-shrink-0" />
              <h2 className="font-semibold text-white">Free Releases</h2>
            </div>
            {freeReleases.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                No free releases yet. Click &ldquo;Free Release&rdquo; to upload one.
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
                    {freeReleases.map((release) => (
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

          {/* Custom Builds table */}
          <div className="glass rounded-2xl overflow-hidden mb-10">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <Building2 size={16} className="text-blue-400 flex-shrink-0" />
              <h2 className="font-semibold text-white">Custom Builds</h2>
            </div>
            {customReleases.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                No custom builds yet. Click &ldquo;Custom Build&rdquo; to upload one.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="px-6 py-3 font-medium">Institution</th>
                      <th className="px-6 py-3 font-medium">Version</th>
                      <th className="px-6 py-3 font-medium">PIN</th>
                      <th className="px-6 py-3 font-medium">Date</th>
                      <th className="px-6 py-3 font-medium">Size</th>
                      <th className="px-6 py-3 font-medium">Downloads</th>
                      <th className="px-6 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customReleases.map((release) => (
                      <tr
                        key={release.id}
                        className="border-t border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-4 font-medium text-white">
                          {release.institutionName || "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {release.version}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <code className="text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded text-xs font-mono">
                              {visiblePins[release.id]
                                ? release.pin
                                : "••••••"}
                            </code>
                            <button
                              onClick={() => togglePinVisibility(release.id)}
                              className="text-slate-500 hover:text-slate-300 p-1"
                            >
                              {visiblePins[release.id] ? (
                                <EyeOff size={13} />
                              ) : (
                                <Eye size={13} />
                              )}
                            </button>
                            <button
                              onClick={() => copyPin(release.pin)}
                              className="text-slate-500 hover:text-slate-300 p-1"
                            >
                              <Copy size={13} />
                            </button>
                          </div>
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
          <div className="glass rounded-2xl overflow-hidden mb-10">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <Users size={16} className="text-purple-400 flex-shrink-0" />
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

          {/* Requests table */}
          <div className="glass rounded-2xl overflow-hidden mb-10">
            <div className="px-6 py-4 border-b border-white/5 flex items-center gap-2">
              <Mail size={16} className="text-teal-400 flex-shrink-0" />
              <h2 className="font-semibold text-white">Build Requests</h2>
            </div>
            {requests.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                No custom build requests yet.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-slate-500 text-left">
                      <th className="px-6 py-3 font-medium">Institution / Name</th>
                      <th className="px-6 py-3 font-medium">Email</th>
                      <th className="px-6 py-3 font-medium">Message</th>
                      <th className="px-6 py-3 font-medium">Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((r) => (
                      <tr
                        key={r.id}
                        className="border-t border-white/5 hover:bg-white/[0.02]"
                      >
                        <td className="px-6 py-4 text-white">
                          {r.name || "—"}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {r.email}
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          <div className="max-w-xs truncate">{r.message}</div>
                        </td>
                        <td className="px-6 py-4 text-slate-400">
                          {r.createdAt?.toDate
                            ? r.createdAt.toDate().toLocaleDateString()
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

            <h2 className="text-xl font-bold text-white mb-1 flex items-center gap-2">
              {uploadType === "custom" ? (
                <>
                  <Building2 size={20} className="text-blue-400" /> Add
                  Custom Build
                </>
              ) : (
                <>
                  <Gift size={20} className="text-emerald-400" /> Add Free
                  Release
                </>
              )}
            </h2>
            <p className="text-sm text-slate-400 mb-6">
              {uploadType === "custom"
                ? "Add a branded build for a specific institution."
                : "Add the free version installer for all users."}
            </p>

            <form onSubmit={handleUpload} className="space-y-4">
              {/* Type toggle */}
              <div className="flex gap-2 p-1 rounded-xl bg-white/5">
                {["free", "custom"].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => {
                      setUploadType(t);
                      if (t === "custom" && !pin) setPin(generatePIN());
                    }}
                    className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors ${
                      uploadType === t
                        ? "bg-white/10 text-white"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {t === "free" ? "Free Release" : "Custom Build"}
                  </button>
                ))}
              </div>

              {/* Custom-only fields */}
              {uploadType === "custom" && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">
                      Institution Name
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Delhi Public School"
                      value={institutionName}
                      onChange={(e) => setInstitutionName(e.target.value)}
                      className="input-dark px-4"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">
                      Download PIN
                    </label>
                    <div className="flex gap-2">
                      <div className="relative flex-1">
                        <KeyRound
                          size={15}
                          className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                        />
                        <input
                          type="text"
                          value={pin}
                          readOnly
                          className="input-dark pl-10 font-mono tracking-widest"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => setPin(generatePIN())}
                        className="px-3 py-2 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 text-xs font-medium transition-colors"
                      >
                        Regenerate
                      </button>
                      <button
                        type="button"
                        onClick={() => copyPin(pin)}
                        className="px-3 py-2 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                      >
                        <Copy size={14} />
                      </button>
                    </div>
                    <p className="text-xs text-slate-500 mt-1.5">
                      Share this PIN with the institution after payment.
                    </p>
                  </div>
                </>
              )}

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
                  className="input-dark px-4"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Download URL
                </label>
                <div className="relative">
                  <Link2
                    size={15}
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 flex-shrink-0"
                  />
                  <input
                    type="url"
                    required
                    placeholder="https://github.com/.../releases/download/..."
                    value={downloadUrl}
                    onChange={(e) => setDownloadUrl(e.target.value)}
                    className="input-dark pl-10 pr-4"
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1.5">
                  Upload the .msi/.exe to GitHub Releases and paste the link here.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  File Size <span className="text-slate-600">(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g. 45.2 MB"
                  value={fileSize}
                  onChange={(e) => setFileSize(e.target.value)}
                  className="input-dark px-4"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Release Notes
                </label>
                <textarea
                  rows={3}
                  placeholder="What's included in this build..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="input-dark px-4 resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={uploading || !downloadUrl.trim()}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:pointer-events-none"
              >
                {uploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Plus size={16} />
                    {uploadType === "custom"
                      ? "Add Custom Build"
                      : "Add Free Release"}
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
