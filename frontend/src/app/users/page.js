'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import api from '../../lib/api';
import UserList from '../../components/users/UserList';
import CreateUserModal from '../../components/users/CreateUserModal';
import EditUserModal from '../../components/users/EditUserModal';
import { useRouter } from 'next/navigation';

export default function UsersPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const pageSize = 10;

  // Redirect non-admins
  useEffect(() => {
    if (user && user.user_type !== 'admin') {
      router.push('/');
      return;
    }
  }, [user, router]);

  const fetchUsers = async () => {
    // Don't fetch if still loading auth or user is not admin
    if (authLoading || !user || user.user_type !== 'admin') {
      return;
    }

    try {
      setLoading(true);
      console.log('Fetching users...', { currentPage, pageSize, searchTerm });
      const response = await api.get(`/admin/users/?page=${currentPage}&size=${pageSize}${searchTerm ? `&search=${searchTerm}` : ""}`);
      console.log('Users response:', response.data);
      setUsers(response.data.users);
      setTotalUsers(response.data.total);
      setTotalPages(Math.ceil(response.data.total / pageSize));
      setError(null);
    } catch (err) {
      console.error('Error fetching users:', err);
      setError(err.response?.data?.detail || 'Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading && user?.user_type === 'admin') {
      fetchUsers();
    }
  }, [currentPage, searchTerm, user, authLoading]);

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
    if (!confirm('Are you sure you want to delete this user?')) {
      return;
    }

    try {
      await api.delete(`/admin/users/${userId}`);
      fetchUsers(); // Refresh the list
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user');
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

  // Don't render if not admin
  if (user && user.user_type !== 'admin') {
    return null;
  }

  if (authLoading || (loading && users.length === 0)) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-green-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading users...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <button
                onClick={() => router.push('/')}
                className="text-gray-500 hover:text-gray-700 mr-4"
              >
                ← Back to Dashboard
              </button>
              <h1 className="text-xl font-semibold text-gray-900">User Management</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">Welcome, {user?.full_name}</span>
              <button
                onClick={() => {}}
                className="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
            <div className="text-red-700">{error}</div>
          </div>
        )}

        <div className="bg-white rounded-lg shadow">
          {/* Header with search and create button */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-lg font-medium text-gray-900">Users ({totalUsers})</h2>
                <p className="mt-1 text-sm text-gray-600">Manage system users and their permissions</p>
              </div>
              <div className="mt-4 sm:mt-0">
                <button
                  onClick={handleCreateUser}
                  className="bg-green-600 text-white px-4 py-2 rounded-md text-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
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
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-green-500 focus:border-green-500"
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-gray-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                  </svg>
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
            <div className="px-6 py-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Showing page {currentPage} of {totalPages}
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                    disabled={currentPage === 1}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                    disabled={currentPage === totalPages}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
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
        />
      )}
    </div>
  );
}