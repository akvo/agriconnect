"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../contexts/AuthContext";
import api from "../../lib/api";
import UserList from "../../components/users/UserList";
import CreateUserModal from "../../components/users/CreateUserModal";
import EditUserModal from "../../components/users/EditUserModal";
import HeaderNav from "../../components/HeaderNav";
import { useRouter } from "next/navigation";
import { MagnifyingGlassIcon, ArrowPathIcon } from "@heroicons/react/24/outline";

export default function UsersPage() {
  const { user, loading: authLoading, refreshUser } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const pageSize = 10;

  // Redirect non-admins
  useEffect(() => {
    if (user && user.user_type !== "admin") {
      router.push("/");
      return;
    }
  }, [user, router]);

  const fetchUsers = useCallback(async () => {
    // Don't fetch if still loading auth or user is not admin
    if (authLoading || !user || user.user_type !== "admin") {
      return;
    }

    try {
      setLoading(true);
      const response = await api.get(
        `/admin/users/?page=${currentPage}&size=${pageSize}${searchTerm ? `&search=${searchTerm}` : ""}`
      );
      setUsers(response.data.users);
      setTotalUsers(response.data.total);
      setTotalPages(Math.ceil(response.data.total / pageSize));
      setError(null);
    } catch (err) {
      console.error("Error fetching users:", err);
      setError(err.response?.data?.detail || "Failed to fetch users");
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, currentPage, pageSize, searchTerm]);

  useEffect(() => {
    if (!authLoading && user?.user_type === "admin") {
      fetchUsers();
    }
  }, [fetchUsers, user, authLoading]);

  const handleSearch = (term) => {
    setSearchTerm(term);
    setCurrentPage(1);
  };

  const handleCreateUser = () => {
    setShowCreateModal(true);
  };

  const handleEditUser = (user) => {
    setSelectedUser(user);
    setShowEditModal(true);
  };

  const handleDeleteUser = async (userId) => {
    if (!confirm("Are you sure you want to delete this user?")) {
      return;
    }

    try {
      await api.delete(`/admin/users/${userId}`);
      fetchUsers(); // Refresh the list
    } catch (err) {
      alert(err.response?.data?.detail || "Failed to delete user");
    }
  };

  const handleUserCreated = () => {
    setShowCreateModal(false);
    fetchUsers();
  };

  const handleUserUpdated = () => {
    setShowEditModal(false);
    setSelectedUser(null);
    fetchUsers();
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

  // Don't render if not admin
  if (user && user.user_type !== "admin") {
    return null;
  }

  if (authLoading || (loading && users.length === 0)) {
    return (
      <div className="min-h-screen bg-gradient-brand flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
            <div className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse" style={{borderRadius: '5px'}}></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">Loading users...</p>
          <p className="text-secondary-500 text-sm mt-2">Please wait while we fetch the user data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav 
        breadcrumbs={[
          { label: "Dashboard", path: "/" },
          { label: "User Management" }
        ]}
        onProfileClick={handleProfileClick}
      />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 p-4 mb-6" style={{borderRadius: '5px'}}>
            <div className="text-red-700">{error}</div>
          </div>
        )}

        <div className="bg-white shadow-lg" style={{borderRadius: '5px'}}>
          {/* Header with search and create button */}
          <div className="px-6 py-4 border-b border-gray-600">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-medium text-gray-900">
                  Users ({totalUsers})
                </h2>
                <p className="mt-1 text-sm text-gray-600">
                  Manage system users and their permissions
                </p>
              </div>
              <div className="mt-4 sm:mt-0">
                <button
                  onClick={handleCreateUser}
                  className="bg-green-600 text-white px-4 py-2 text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"                  style={{borderRadius: '5px'}}
                >
                  Create User
                </button>
              </div>
            </div>

            {/* Search */}
            <div className="mt-4">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search users by name, email, or phone..."
                  value={searchTerm}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 bg-gray-50 leading-5 placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-2 focus:ring-green-500 focus:bg-white cursor-text"                  style={{borderRadius: '5px'}}
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>
          </div>

          {/* User List */}
          <UserList
            users={users}
            loading={loading}
            onEditUser={handleEditUser}
            onDeleteUser={handleDeleteUser}
            currentUser={user}
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
                    style={{borderRadius: '5px'}}
                  >
                    Previous
                  </button>
                  <button
                    onClick={() =>
                      setCurrentPage((prev) => Math.min(prev + 1, totalPages))
                    }
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
                    style={{borderRadius: '5px'}}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Modals */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onUserCreated={handleUserCreated}
        />
      )}

      {showEditModal && selectedUser && (
        <EditUserModal
          user={selectedUser}
          onClose={() => {
            setShowEditModal(false);
            setSelectedUser(null);
          }}
          onUserUpdated={handleUserUpdated}
          isSelfUpdate={selectedUser.id === user.id}
        />
      )}

      {/* Profile Modal */}
      {showProfileModal && (
        <EditUserModal
          user={user}
          onClose={() => setShowProfileModal(false)}
          onUserUpdated={handleProfileUpdate}
          isSelfUpdate={true}
        />
      )}
    </div>
  );
}
