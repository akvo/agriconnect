"use client";

import { useState, useEffect } from "react";
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import HeaderNav from "../HeaderNav";
import EditUserModal from "../users/EditUserModal";
import KnowledgeBaseList from "./KnowledgeBaseList";
import knowledgeBaseApi from "../../lib/knowledgeBaseApi";
import KnowledgeBaseModal from "./KnowledgeBaseModal";

export default function KnowledgeBasePage() {
  const { user, refreshUser, loading: authLoading } = useAuth();
  const [knowledgeBases, setKnowledgeBases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [error, setError] = useState("");
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showKnowledgeBaseModal, setShowKnowledgeBaseModal] = useState(false);

  const ITEMS_PER_PAGE = 10;
  const router = useRouter();

  const fetchKnowledgeBases = async (page = 1, search = null) => {
    try {
      setLoading(true);
      setError("");
      const response = await knowledgeBaseApi.getList(
        page,
        ITEMS_PER_PAGE,
        search
      );
      setKnowledgeBases(response.data || []);
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

  const handleEditKnowledgeBase = async (kb_id) => {
    router.push(`/knowledge-base/${kb_id}`);
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
            Please wait while we prepare your knowledge base management dashboard
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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Error Message */}
        {error && (
            <div
              className="bg-red-50 border border-red-200 p-4 mb-6"
              style={{ borderRadius: "5px" }}
            >
              <div className="text-red-700">{error}</div>
            </div>
          )}

        <div className="bg-white shadow-lg" style={{ borderRadius: "5px" }}>
          {/* Header with search and create button */}
          <div className="px-6 py-4 border-b border-gray-600">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-medium text-gray-900">
                  Knowledge Bases ({totalCount})
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  Manage Knowledge Base documents for AI-powered assistance
                </p>
              </div>
              <div className="mt-4 sm:mt-0">
                <button
                  onClick={() => setShowKnowledgeBaseModal(true)}
                  className="bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"
                  style={{ borderRadius: "5px" }}
                >
                  Create Knowledge Base
                </button>
              </div>
            </div>

            {/* Search */}
            <div className="mt-4">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search knowledge bases by title..."
                  // value={searchTerm}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 bg-gray-50 leading-5 placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-2 focus:ring-green-500 focus:bg-white cursor-text"
                  style={{ borderRadius: "5px" }}
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Knowledge Base List */}
        <KnowledgeBaseList
          knowledgeBases={filteredKnowledgeBases}
          loading={loading}
          onEditKnowledgeBase={handleEditKnowledgeBase}
          onDeleteKnowledgeBase={handleDeleteKnowledgeBase}
        />

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-gray-600">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Showing page {currentPage} of {totalPages}
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() =>
                      setCurrentPage((prev) => Math.max(prev - 1, 1))
                    }
                    disabled={currentPage === 1}
                    className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
                    style={{ borderRadius: "5px" }}
                  >
                    Previous
                  </button>
                  <button
                    onClick={() =>
                      setCurrentPage((prev) => Math.min(prev + 1, totalPages))
                    }
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
                    style={{ borderRadius: "5px" }}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
        )}

        {/* KnowledgeBaseModal */}
        {
          showKnowledgeBaseModal && (
          <KnowledgeBaseModal
            onClose={() => setShowKnowledgeBaseModal(false)}
            onKnowledgeBaseUpdated={() => {
              setShowKnowledgeBaseModal(false);
              fetchKnowledgeBases(currentPage, searchQuery || null);
            }}
          />
        )
        }

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
