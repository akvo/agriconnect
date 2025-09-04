'use client';

import { useState } from 'react';
import api from '../../lib/api';

export default function EditUserModal({ user, onClose, onUserUpdated }) {
  const [formData, setFormData] = useState({
    full_name: user.full_name || '',
    phone_number: user.phone_number || '',
    user_type: user.user_type || 'eo'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showDetails, setShowDetails] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Only send changed fields
      const changedData = {};
      Object.keys(formData).forEach(key => {
        if (formData[key] !== user[key]) {
          changedData[key] = formData[key];
        }
      });

      if (Object.keys(changedData).length === 0) {
        onClose();
        return;
      }

      await api.put(`/admin/users/${user.id}`, changedData);
      onUserUpdated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update user');
    } finally {
      setLoading(false);
    }
  };

  const getUserTypeLabel = (userType) => {
    switch (userType) {
      case 'admin':
        return 'Administrator';
      case 'eo':
        return 'Extension Officer';
      default:
        return userType;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
      <div className="relative top-10 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            {showDetails ? 'User Details' : 'Edit User'}
          </h3>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setShowDetails(!showDetails)}
              className="text-sm text-indigo-600 hover:text-indigo-500"
            >
              {showDetails ? 'Edit' : 'View Details'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </div>

        {showDetails ? (
          <div className="space-y-4">
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">User ID</label>
                  <p className="mt-1 text-sm text-gray-900">#{user.id}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Status</label>
                  <span className={`mt-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user.is_active === 'true' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {user.is_active === 'true' ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Full Name</label>
                  <p className="mt-1 text-sm text-gray-900">{user.full_name}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Email</label>
                  <p className="mt-1 text-sm text-gray-900">{user.email}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Phone Number</label>
                  <p className="mt-1 text-sm text-gray-900">{user.phone_number}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">User Type</label>
                  <span className={`mt-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user.user_type === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
                  }`}>
                    {getUserTypeLabel(user.user_type)}
                  </span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Created At</label>
                  <p className="mt-1 text-sm text-gray-900">{formatDate(user.created_at)}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Updated At</label>
                  <p className="mt-1 text-sm text-gray-900">{formatDate(user.updated_at)}</p>
                </div>
              </div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="bg-gray-600 text-white py-2 px-4 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-4">
                <div className="text-red-700 text-sm">{error}</div>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
                  Full Name
                </label>
                <input
                  type="text"
                  id="full_name"
                  name="full_name"
                  value={formData.full_name}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
                  placeholder="Enter full name"
                />
              </div>

              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                  Email Address
                </label>
                <input
                  type="email"
                  id="email"
                  value={user.email}
                  disabled
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-50 cursor-not-allowed"
                />
                <p className="mt-1 text-xs text-gray-500">Email cannot be changed</p>
              </div>

              <div>
                <label htmlFor="phone_number" className="block text-sm font-medium text-gray-700">
                  Phone Number
                </label>
                <input
                  type="tel"
                  id="phone_number"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
                  placeholder="+1234567890"
                />
                <p className="mt-1 text-xs text-gray-500">Must start with + and be at least 10 characters</p>
              </div>

              <div>
                <label htmlFor="user_type" className="block text-sm font-medium text-gray-700">
                  User Type
                </label>
                <select
                  id="user_type"
                  name="user_type"
                  value={formData.user_type}
                  onChange={handleChange}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
                >
                  <option value="eo">Extension Officer</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            </div>

            <div className="mt-6 flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 bg-white py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-green-600 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Updating...' : 'Update User'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}