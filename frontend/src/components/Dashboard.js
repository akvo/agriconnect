"use client";

import { useAuth } from "../contexts/AuthContext";

export default function Dashboard() {
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
  };

  const getUserTypeLabel = (userType) => {
    switch (userType) {
      case "admin":
        return "Administrator";
      case "eo":
        return "Extension Officer";
      default:
        return userType;
    }
  };

  const getUserTypeBadgeColor = (userType) => {
    switch (userType) {
      case "admin":
        return "bg-purple-100 text-purple-800";
      case "eo":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                AgriConnect Dashboard
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-700">
                Welcome, {user?.full_name}
              </span>
              <button
                onClick={handleLogout}
                className="bg-red-600 text-white px-4 py-2 rounded-md text-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* User Info Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            User Information
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Full Name
              </label>
              <p className="mt-1 text-sm text-gray-900">{user?.full_name}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <p className="mt-1 text-sm text-gray-900">{user?.email}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Phone Number
              </label>
              <p className="mt-1 text-sm text-gray-900">{user?.phone_number}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                User Type
              </label>
              <div className="mt-1">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getUserTypeBadgeColor(user?.user_type)}`}
                >
                  {getUserTypeLabel(user?.user_type)}
                </span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Account Status
              </label>
              <div className="mt-1">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    user?.is_active === "true"
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {user?.is_active === "true" ? "Active" : "Inactive"}
                </span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                User ID
              </label>
              <p className="mt-1 text-sm text-gray-900">#{user?.id}</p>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="bg-green-50 border border-green-200 rounded-lg p-4 text-left hover:bg-green-100 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2">
              <div className="text-green-600 font-medium">Profile Settings</div>
              <div className="text-sm text-gray-600 mt-1">
                Update your personal information
              </div>
            </button>

            {user?.user_type === "admin" && (
              <a
                href="/users"
                className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-left hover:bg-purple-100 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 block"
              >
                <div className="text-purple-600 font-medium">
                  User Management
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  Manage system users
                </div>
              </a>
            )}

            <button className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
              <div className="text-blue-600 font-medium">Reports</div>
              <div className="text-sm text-gray-600 mt-1">
                View activity reports
              </div>
            </button>
          </div>
        </div>

        {/* Welcome Message based on user type */}
        <div className="mt-8 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Welcome to AgriConnect, {user?.full_name}!
          </h3>
          <p className="text-gray-700">
            {user?.user_type === "admin"
              ? "As an administrator, you have full access to manage the system, users, and oversee all agricultural extension activities."
              : "As an extension officer, you can connect with farmers, provide agricultural guidance, and help improve farming practices in your area."}
          </p>
        </div>
      </main>
    </div>
  );
}
