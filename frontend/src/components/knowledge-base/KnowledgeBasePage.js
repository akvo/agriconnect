"use client";

import { useState, useEffect } from "react";
import {
  PlusIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";
import { useAuth } from "../../contexts/AuthContext";
import HeaderNav from "../HeaderNav";
import EditUserModal from "../users/EditUserModal";
import KnowledgeBaseList from "./KnowledgeBaseList";
import KnowledgeBaseUploadModal from "./KnowledgeBaseUploadModal";
import knowledgeBaseApi from "../../lib/knowledgeBaseApi";

export default function KnowledgeBasePage() {
  const { user, refreshUser, loading: authLoading } = useAuth();
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [error, setError] = useState("");
  const [showProfileModal, setShowProfileModal] = useState(false);

  const ITEMS_PER_PAGE = 10;

  const fetchKnowledgeBases = async (page = 1, search = null) => {
    try {
      setLoading(true);
      setError("");
      const response = await knowledgeBaseApi.getList(
        page,
        ITEMS_PER_PAGE,
        search
      );

      setKnowledgeBases(response.knowledge_bases || []);
      setTotalCount(response.total || 0);
      setCurrentPage(page);
    } catch (err) {
      console.error("Error fetching knowledge bases:", err);
      setError("Failed to load knowledge bases. Please try again.");
      setKnowledgeBases([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch if user is authenticated and auth is not loading
    console.log(
      "KB Page: Auth state - user:",
      !!user,
      "authLoading:",
      authLoading
    );
    if (user && !authLoading) {
      console.log("KB Page: Fetching knowledge bases");
      fetchKnowledgeBases(1, null);
    }
  }, [user, authLoading]);

  const handleUpload = async (formData) => {
    setUploading(true);
    try {
      await knowledgeBaseApi.create(formData);
      // Refresh the list after successful upload
      await fetchKnowledgeBases(1, searchQuery || null);
      setUploadModalOpen(false);
    } catch (err) {
      throw err; // Re-throw to be handled by the modal
    } finally {
      setUploading(false);
    }
  };

  const handleViewKnowledgeBase = (kb) => {
    // TODO: Implement view modal or navigate to detail page
    console.log("View KB:", kb);
  };

  const handleEditKnowledgeBase = async (kb) => {
    // TODO: Implement edit modal
    console.log("Edit KB:", kb);
  };

  const handleDeleteKnowledgeBase = async (kb) => {
    if (
      window.confirm(
        `Are you sure you want to delete "${kb.title}"? This action cannot be undone.`
      )
    ) {
      try {
        await knowledgeBaseApi.delete(kb.id);
        await fetchKnowledgeBases(currentPage, searchQuery || null);
      } catch (err) {
        console.error("Error deleting knowledge base:", err);
        alert("Failed to delete knowledge base. Please try again.");
      }
    }
  };

  const handleSearch = (e) => {
    const newSearchQuery = e.target.value;
    setSearchQuery(newSearchQuery);

    // Debounce the search - reset to page 1 and search
    setCurrentPage(1);
    fetchKnowledgeBases(1, newSearchQuery || null);
  };

  const handleRefresh = () => {
    fetchKnowledgeBases(currentPage, searchQuery || null);
  };

  const handleProfileClick = () => {
    setShowProfileModal(true);
  };

  const handleProfileUpdate = () => {
    setShowProfileModal(false);
    if (refreshUser) {
      refreshUser();
    }
  };

  // Server-side search is now handled, so we use knowledgeBases directly
  const filteredKnowledgeBases = knowledgeBases;

  const totalPages = Math.ceil(totalCount / ITEMS_PER_PAGE);

  // Show loading while auth is being checked
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-brand flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
            <div
              className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse"
              style={{ borderRadius: "5px" }}
            ></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">
            Loading Knowledge Base...
          </p>
          <p className="text-secondary-500 text-sm mt-2">
            Please wait while we prepare your document library
          </p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!user) {
    if (typeof window !== "undefined") {
      window.location.href = "/";
    }
    return null;
  }

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav
        breadcrumbs={[
          { label: "Dashboard", path: "/" },
          { label: "Knowledge Base Management" },
        ]}
        onProfileClick={handleProfileClick}
      />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="sm:flex sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-secondary-900">
              Knowledge Base
            </h1>
            <p className="mt-2 text-sm text-secondary-600">
              Manage your document library for AI-powered assistance
            </p>
          </div>
          <div className="mt-4 sm:mt-0">
            <button
              onClick={() => setUploadModalOpen(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <PlusIcon className="-ml-1 mr-2 h-5 w-5" />
              Upload Document
            </button>
          </div>
        </div>

        {/* Search and Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-3 sm:space-y-0 sm:space-x-4">
          <div className="flex-1 max-w-lg">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={handleSearch}
                placeholder="Search documents..."
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              <ArrowPathIcon
                className={`-ml-1 mr-2 h-5 w-5 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div
            className="bg-red-50 border border-red-200 p-4"
            style={{ borderRadius: "5px" }}
          >
            <div className="text-red-700">{error}</div>
          </div>
        )}

        {/* Knowledge Base List */}
        <div className="bg-white shadow-lg" style={{ borderRadius: "5px" }}>
          <KnowledgeBaseList
            knowledgeBases={filteredKnowledgeBases}
            loading={loading}
            onViewKnowledgeBase={handleViewKnowledgeBase}
            onEditKnowledgeBase={handleEditKnowledgeBase}
            onDeleteKnowledgeBase={handleDeleteKnowledgeBase}
          />
        </div>

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div
            className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6 shadow-lg"
            style={{ borderRadius: "5px" }}
          >
            <div className="flex-1 flex justify-between sm:hidden">
              <button
                onClick={() =>
                  fetchKnowledgeBases(currentPage - 1, searchQuery || null)
                }
                disabled={currentPage <= 1}
                className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() =>
                  fetchKnowledgeBases(currentPage + 1, searchQuery || null)
                }
                disabled={currentPage >= totalPages}
                className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
            <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
              <div>
                <p className="text-sm text-gray-700">
                  Showing{" "}
                  <span className="font-medium">
                    {(currentPage - 1) * ITEMS_PER_PAGE + 1}
                  </span>{" "}
                  to{" "}
                  <span className="font-medium">
                    {Math.min(currentPage * ITEMS_PER_PAGE, totalCount)}
                  </span>{" "}
                  of <span className="font-medium">{totalCount}</span> documents
                </p>
              </div>
              <div>
                <nav
                  className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"
                  aria-label="Pagination"
                >
                  <button
                    onClick={() =>
                      fetchKnowledgeBases(currentPage - 1, searchQuery || null)
                    }
                    disabled={currentPage <= 1}
                    className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  {/* Page numbers */}
                  {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                    let pageNum;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (currentPage <= 3) {
                      pageNum = i + 1;
                    } else if (currentPage >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = currentPage - 2 + i;
                    }

                    return (
                      <button
                        key={pageNum}
                        onClick={() =>
                          fetchKnowledgeBases(pageNum, searchQuery || null)
                        }
                        className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                          pageNum === currentPage
                            ? "z-10 bg-blue-50 border-blue-500 text-blue-600"
                            : "bg-white border-gray-300 text-gray-500 hover:bg-gray-50"
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                  <button
                    onClick={() =>
                      fetchKnowledgeBases(currentPage + 1, searchQuery || null)
                    }
                    disabled={currentPage >= totalPages}
                    className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </nav>
              </div>
            </div>
          </div>
        )}

        {/* Upload Modal */}
        <KnowledgeBaseUploadModal
          isOpen={uploadModalOpen}
          onClose={() => setUploadModalOpen(false)}
          onUpload={handleUpload}
          uploading={uploading}
        />

        {/* Profile Modal */}
        {showProfileModal && (
          <EditUserModal
            user={user}
            onClose={() => setShowProfileModal(false)}
            onUserUpdated={handleProfileUpdate}
            isSelfUpdate={true}
          />
        )}
      </main>
    </div>
  );
}
