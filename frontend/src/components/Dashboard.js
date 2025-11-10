"use client";

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import HeaderNav from "./HeaderNav";
import EditUserModal from "./users/EditUserModal";
import {
  UsersIcon,
  ChartBarIcon,
  BoltIcon,
  BuildingStorefrontIcon,
  ChevronRightIcon,
  SparklesIcon,
  DocumentIcon,
  BeakerIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";

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
        {/* Quick Actions */}
        <div
          className="bg-white/80 backdrop-blur-md p-8 animate-slide-up"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center mb-6">
            <div
              className="flex items-center justify-center w-12 h-12 bg-gradient-success mr-4"
              style={{ borderRadius: "5px" }}
            >
              <BoltIcon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-secondary-900">
                Quick Actions
              </h2>
              <p className="text-secondary-600">
                Access key features and tools
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <a
              href="/customers"
              className="group bg-gradient-to-br from-green-50 to-green-100 p-6 text-left hover:from-green-100 hover:to-green-200 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all duration-300 block cursor-pointer shadow-sm hover:shadow-md"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex items-center mb-4">
                <div
                  className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-green-500 to-green-600 mr-3"
                  style={{ borderRadius: "5px" }}
                >
                  <BuildingStorefrontIcon className="w-5 h-5 text-white" />
                </div>
                <div className="text-green-700 font-bold text-lg">
                  Customer Management
                </div>
              </div>
              <div className="text-secondary-600 text-sm leading-relaxed">
                View and manage customer information, track interactions, and
                customer support
              </div>
              <div className="mt-4 flex items-center text-green-600 text-sm font-semibold group-hover:text-green-700">
                <span>Manage Customers</span>
                <ChevronRightIcon className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" />
              </div>
            </a>

            <Link
              href="/knowledge-base"
              className="group bg-gradient-to-br from-blue-50 to-blue-100 p-6 text-left hover:from-blue-100 hover:to-blue-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-300 block cursor-pointer shadow-sm hover:shadow-md"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex items-center mb-4">
                <div
                  className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 mr-3"
                  style={{ borderRadius: "5px" }}
                >
                  <DocumentIcon className="w-5 h-5 text-white" />
                </div>
                <div className="text-blue-700 font-bold text-lg">
                  Knowledge Base
                </div>
              </div>
              <div className="text-secondary-600 text-sm leading-relaxed">
                Upload and manage knowledge bases for AI-powered assistance and
                knowledge sharing
              </div>
              <div className="mt-4 flex items-center text-blue-600 text-sm font-semibold group-hover:text-blue-700">
                <span>Manage Knowledge Bases</span>
                <ChevronRightIcon className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" />
              </div>
            </Link>

            {user?.user_type === "admin" && (
              <>
                <a
                  href="/users"
                  className="group bg-gradient-to-br from-purple-50 to-purple-100 p-6 text-left hover:from-purple-100 hover:to-purple-200 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 transition-all duration-300 block cursor-pointer shadow-sm hover:shadow-md"
                  style={{ borderRadius: "5px" }}
                >
                  <div className="flex items-center mb-4">
                    <div
                      className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-purple-500 to-purple-600 mr-3"
                      style={{ borderRadius: "5px" }}
                    >
                      <UsersIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="text-purple-700 font-bold text-lg">
                      User Management
                    </div>
                  </div>
                  <div className="text-secondary-600 text-sm leading-relaxed">
                    Create, edit, and manage system users and their permissions
                  </div>
                  <div className="mt-4 flex items-center text-purple-600 text-sm font-semibold group-hover:text-purple-700">
                    <span>Manage Users</span>
                    <ChevronRightIcon className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" />
                  </div>
                </a>

                <a
                  href="/playground"
                  className="group bg-gradient-to-br from-indigo-50 to-indigo-100 p-6 text-left hover:from-indigo-100 hover:to-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-all duration-300 block cursor-pointer shadow-sm hover:shadow-md"
                  style={{ borderRadius: "5px" }}
                >
                  <div className="flex items-center mb-4">
                    <div
                      className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-indigo-500 to-indigo-600 mr-3"
                      style={{ borderRadius: "5px" }}
                    >
                      <BeakerIcon className="w-5 h-5 text-white" />
                    </div>
                    <div className="text-indigo-700 font-bold text-lg">
                      Chat Playground
                    </div>
                  </div>
                  <div className="text-secondary-600 text-sm leading-relaxed">
                    Test and fine-tune AI prompts with custom configurations
                  </div>
                  <div className="mt-4 flex items-center text-indigo-600 text-sm font-semibold group-hover:text-indigo-700">
                    <span>Open Playground</span>
                    <ChevronRightIcon className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" />
                  </div>
                </a>
              </>
            )}

            <button
              className="group bg-gradient-to-br from-orange-50 to-orange-100 p-6 text-left hover:from-orange-100 hover:to-orange-200 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition-all duration-300 cursor-pointer shadow-sm hover:shadow-md"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex items-center mb-4">
                <div
                  className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-orange-500 to-orange-600 mr-3"
                  style={{ borderRadius: "5px" }}
                >
                  <ChartBarIcon className="w-5 h-5 text-white" />
                </div>
                <div className="text-orange-700 font-bold text-lg">Reports</div>
              </div>
              <div className="text-secondary-600 text-sm leading-relaxed">
                View detailed activity reports, analytics, and system insights
              </div>
              <div className="mt-4 flex items-center text-orange-600 text-sm font-semibold group-hover:text-orange-700">
                <span>View Reports</span>
                <ChevronRightIcon className="ml-2 w-4 h-4 transform group-hover:translate-x-1 transition-transform duration-200" />
              </div>
            </button>
          </div>
        </div>

        {/* Welcome Message based on user type */}
        <div
          className="mt-8 bg-gradient-brand p-8 animate-scale-in"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-start space-x-4">
            <div
              className="flex items-center justify-center w-16 h-16 bg-gradient-primary flex-shrink-0"
              style={{ borderRadius: "5px" }}
            >
              <SparklesIcon className="w-8 h-8 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-secondary-900 mb-3">
                Welcome to AgriConnect, {user?.full_name}! 🌱
              </h3>
              <div
                className="bg-white/60 backdrop-blur-sm p-4"
                style={{ borderRadius: "5px" }}
              >
                <p className="text-secondary-700 leading-relaxed">
                  {user?.user_type === "admin"
                    ? "As an administrator, you have comprehensive access to manage the entire system, oversee user accounts, and coordinate all agricultural extension activities. Your role is crucial in ensuring seamless operations and supporting extension officers in their mission to help farmers."
                    : "As an extension officer, you're at the forefront of agricultural innovation. Connect with farmers in your community, provide expert guidance, share best practices, and help implement sustainable farming solutions that improve crop yields and farmer livelihoods."}
                </p>
                <div className="mt-4 flex items-center text-primary-700">
                  <BoltIcon className="w-5 h-5 mr-2" />
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
