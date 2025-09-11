"use client";

import { useState } from "react";
import api from "../../lib/api";
import { CheckIcon, ExclamationTriangleIcon, XMarkIcon } from "@heroicons/react/24/outline";

export default function CreateUserModal({ onClose, onUserCreated }) {
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    phone_number: "",
    user_type: "eo",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [createdUser, setCreatedUser] = useState(null);
  const [temporaryPassword, setTemporaryPassword] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await api.post("/admin/users/", formData);
      setCreatedUser(response.data.user);
      setTemporaryPassword(response.data.temporary_password);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create user");
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = () => {
    onUserCreated();
    onClose();
  };

  if (createdUser && temporaryPassword) {
    return (
      <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
        <div className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in p-8" style={{borderRadius: '5px', border: '1px solid rgb(191, 219, 254)'}}>
          <div className="text-center">
            <div className="flex items-center justify-center w-16 h-16 mx-auto bg-gradient-success mb-6" style={{borderRadius: '5px'}}>
              <CheckIcon className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-secondary-900 mb-3">
              User Created Successfully! 🎉
            </h3>
            <p className="text-secondary-600 mb-6">The new user account has been created and is ready to use.</p>

            <div className="bg-yellow-50 border border-yellow-200 p-4 mb-4" style={{borderRadius: '5px'}}>
              <div className="flex">
                <ExclamationTriangleIcon className="w-5 h-5 text-yellow-400 mt-0.5 mr-2" />
                <div>
                  <h4 className="text-sm font-medium text-yellow-800">
                    Important!
                  </h4>
                  <p className="text-sm text-yellow-700 mt-1">
                    Please save this temporary password and share it securely
                    with the user.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  User Email
                </label>
                <p className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 border" style={{borderRadius: '5px'}}>
                  {createdUser.email}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Invitation Status
                </label>
                <p className="mt-1 text-sm text-gray-900 bg-gray-50 p-2 border" style={{borderRadius: '5px'}}>
                  {temporaryPassword.includes("http") ? (
                    <>
                      ✅ Invitation sent successfully!<br />
                      <span className="text-xs text-gray-600 font-mono">{temporaryPassword}</span>
                    </>
                  ) : (
                    <>
                      ⚠️ User created but invitation email failed to send<br />
                      <span className="text-xs text-gray-600">Admin can resend invitation from user list</span>
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="mt-6">
              <button
                onClick={handleComplete}
                className="w-full bg-green-600 text-white py-2 px-4 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer transition-colors duration-200"
                style={{borderRadius: '5px'}}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in p-8" style={{borderRadius: '5px', border: '1px solid rgb(191, 219, 254)'}}>
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Create New User
            </h3>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 p-3 mb-4" style={{borderRadius: '5px'}}>
              <div className="text-red-700 text-sm">{error}</div>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label
                htmlFor="full_name"
                className="block text-sm font-medium text-gray-700"
              >
                Full Name *
              </label>
              <input
                type="text"
                id="full_name"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{borderRadius: '5px'}}
                placeholder="Enter full name"
              />
            </div>

            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-gray-700"
              >
                Email Address *
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{borderRadius: '5px'}}
                placeholder="user@example.com"
              />
            </div>

            <div>
              <label
                htmlFor="phone_number"
                className="block text-sm font-medium text-gray-700"
              >
                Phone Number *
              </label>
              <input
                type="tel"
                id="phone_number"
                name="phone_number"
                value={formData.phone_number}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{borderRadius: '5px'}}
                placeholder="+1234567890"
              />
              <p className="mt-1 text-xs text-gray-500">
                Must start with + and be at least 10 characters
              </p>
            </div>

            <div>
              <label
                htmlFor="user_type"
                className="block text-sm font-medium text-gray-700"
              >
                User Type *
              </label>
              <select
                id="user_type"
                name="user_type"
                value={formData.user_type}
                onChange={handleChange}
                required
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{borderRadius: '5px'}}
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
              className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 cursor-pointer transition-colors duration-200"
              style={{borderRadius: '5px'}}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-green-600 py-2 px-4 border border-transparent text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
              style={{borderRadius: '5px'}}
            >
              {loading ? "Creating..." : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
