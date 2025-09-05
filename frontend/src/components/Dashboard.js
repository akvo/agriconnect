"use client";

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import HeaderNav from "./HeaderNav";
import EditUserModal from "./users/EditUserModal";

export default function Dashboard() {
  const { user, refreshUser } = useAuth();
  const [showProfileModal, setShowProfileModal] = useState(false);

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

  const handleProfileClick = () => {
    setShowProfileModal(true);
  };

  const handleProfileUpdate = () => {
    setShowProfileModal(false);
    if (refreshUser) {
      refreshUser();
    }
  };

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav title="Dashboard" onProfileClick={handleProfileClick} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* User Info Card */}
        <div className="bg-white/80 backdrop-blur-md rounded-2xl shadow-brand border border-white/20 p-8 mb-8 animate-fade-in">
          <div className="flex items-center mb-6">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-primary shadow-lg mr-4">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-secondary-900">
                Profile Information
              </h2>
              <p className="text-secondary-600">Your account details and settings</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                Full Name
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                </svg>
                <p className="text-secondary-900 font-medium">{user?.full_name}</p>
              </div>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                Email Address
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"></path>
                </svg>
                <p className="text-secondary-900 font-medium">{user?.email}</p>
              </div>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                Phone Number
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                </svg>
                <p className="text-secondary-900 font-medium">{user?.phone_number}</p>
              </div>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                User Type
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5-7a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h4"></path>
                </svg>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold ${getUserTypeBadgeColor(user?.user_type)}`}
                >
                  {getUserTypeLabel(user?.user_type)}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                Account Status
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold ${
                    user?.is_active === "true"
                      ? "bg-primary-100 text-primary-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {user?.is_active === "true" ? "Active" : "Inactive"}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-secondary-700">
                User ID
              </label>
              <div className="flex items-center p-3 bg-secondary-50 rounded-xl border border-secondary-100">
                <svg className="w-5 h-5 text-secondary-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"></path>
                </svg>
                <p className="text-secondary-900 font-medium">#{user?.id}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white/80 backdrop-blur-md rounded-2xl shadow-brand border border-white/20 p-8 animate-slide-up">
          <div className="flex items-center mb-6">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-success shadow-lg mr-4">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-secondary-900">
                Quick Actions
              </h2>
              <p className="text-secondary-600">Access key features and tools</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <button className="group bg-gradient-to-br from-primary-50 to-primary-100 border-2 border-primary-200 rounded-2xl p-6 text-left hover:from-primary-100 hover:to-primary-200 hover:border-primary-300 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-primary shadow-md mr-3">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                  </svg>
                </div>
                <div className="text-primary-700 font-bold text-lg">Profile Settings</div>
              </div>
              <div className="text-secondary-600 text-sm leading-relaxed">
                Update your personal information, preferences, and account settings
              </div>
              <div className="mt-4 flex items-center text-primary-600 text-sm font-semibold group-hover:text-primary-700">
                <span>Manage Profile</span>
                <svg className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
              </div>
            </button>

            {user?.user_type === "admin" && (
              <a
                href="/users"
                className="group bg-gradient-to-br from-purple-50 to-purple-100 border-2 border-purple-200 rounded-2xl p-6 text-left hover:from-purple-100 hover:to-purple-200 hover:border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl block cursor-pointer"
              >
                <div className="flex items-center mb-4">
                  <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 shadow-md mr-3">
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"></path>
                    </svg>
                  </div>
                  <div className="text-purple-700 font-bold text-lg">User Management</div>
                </div>
                <div className="text-secondary-600 text-sm leading-relaxed">
                  Create, edit, and manage system users and their permissions
                </div>
                <div className="mt-4 flex items-center text-purple-600 text-sm font-semibold group-hover:text-purple-700">
                  <span>Manage Users</span>
                  <svg className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                  </svg>
                </div>
              </a>
            )}

            <button className="group bg-gradient-to-br from-accent-50 to-accent-100 border-2 border-accent-200 rounded-2xl p-6 text-left hover:from-accent-100 hover:to-accent-200 hover:border-accent-300 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:ring-offset-2 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl cursor-pointer">
              <div className="flex items-center mb-4">
                <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-accent-600 shadow-md mr-3">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                  </svg>
                </div>
                <div className="text-accent-700 font-bold text-lg">Reports</div>
              </div>
              <div className="text-secondary-600 text-sm leading-relaxed">
                View detailed activity reports, analytics, and system insights
              </div>
              <div className="mt-4 flex items-center text-accent-600 text-sm font-semibold group-hover:text-accent-700">
                <span>View Reports</span>
                <svg className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                </svg>
              </div>
            </button>
          </div>
        </div>

        {/* Welcome Message based on user type */}
        <div className="mt-8 bg-gradient-brand rounded-2xl p-8 border border-white/20 shadow-brand animate-scale-in">
          <div className="flex items-start space-x-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-primary shadow-lg flex-shrink-0">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v18m0-18l4 4m-4-4l-4 4m4 14l4-4m-4 4l-4-4"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-secondary-900 mb-3">
                Welcome to AgriConnect, {user?.full_name}! 🌱
              </h3>
              <div className="bg-white/60 backdrop-blur-sm rounded-xl p-4 border border-white/40">
                <p className="text-secondary-700 leading-relaxed">
                  {user?.user_type === "admin"
                    ? "As an administrator, you have comprehensive access to manage the entire system, oversee user accounts, and coordinate all agricultural extension activities. Your role is crucial in ensuring seamless operations and supporting extension officers in their mission to help farmers."
                    : "As an extension officer, you're at the forefront of agricultural innovation. Connect with farmers in your community, provide expert guidance, share best practices, and help implement sustainable farming solutions that improve crop yields and farmer livelihoods."}
                </p>
                <div className="mt-4 flex items-center text-primary-700">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
                  </svg>
                  <span className="font-semibold text-sm">
                    {user?.user_type === "admin" 
                      ? "Empowering agricultural communities through technology" 
                      : "Making a difference in sustainable agriculture"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

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
