"use client";

import { useAuth } from "../contexts/AuthContext";
import { useRouter } from "next/navigation";
import { ArrowLeftEndOnRectangleIcon, ChevronRightIcon, CommandLineIcon } from "@heroicons/react/24/outline";

export default function HeaderNav({ title = "Dashboard", breadcrumbs = null, onProfileClick }) {
  const { user, logout, refreshUser } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    if (confirm('Are you sure you want to log out?')) {
      await logout();
    }
  };

  const handleBreadcrumbClick = (path) => {
    router.push(path);
  };

  const handleProfileClick = () => {
    if (onProfileClick) {
      onProfileClick();
    }
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

  return (
    <header className="bg-white/90 backdrop-blur-md shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          <div className="flex items-center space-x-4">
            <div className="flex items-center justify-center w-12 h-12 bg-gradient-primary" style={{borderRadius: '5px'}}>
              <CommandLineIcon className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gradient">
                AgriConnect
              </h1>
              {breadcrumbs ? (
                <nav className="flex items-center space-x-2 text-sm">
                  {breadcrumbs.map((crumb, index) => (
                    <div key={index} className="flex items-center">
                      {index > 0 && (
                        <ChevronRightIcon className="w-4 h-4 text-secondary-400 mx-2" />
                      )}
                      {crumb.path ? (
                        <button
                          onClick={() => handleBreadcrumbClick(crumb.path)}
                          className="text-secondary-600 hover:text-primary-600 font-medium transition-colors duration-200 cursor-pointer hover:underline"
                        >
                          {crumb.label}
                        </button>
                      ) : (
                        <span className="text-secondary-900 font-semibold">{crumb.label}</span>
                      )}
                    </div>
                  ))}
                </nav>
              ) : (
                <p className="text-sm text-secondary-600 font-medium">{title}</p>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-6">
            <div className="text-right">
              <p className="text-sm font-medium text-secondary-700">
                Welcome back, {user?.full_name}
              </p>
              <p className="text-xs text-secondary-500">
                {getUserTypeLabel(user?.user_type)}
              </p>
            </div>
            <button
              onClick={handleProfileClick}
              className="flex items-center justify-center w-10 h-10 bg-gradient-primary transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 cursor-pointer"              style={{borderRadius: '5px'}}
              title="Edit Profile"
            >
              <span className="text-sm font-bold text-white">
                {user?.full_name?.charAt(0)?.toUpperCase()}
              </span>
            </button>
            <button
              onClick={handleLogout}
              className="bg-red-500 hover:bg-red-600 text-white px-5 py-2.5 text-sm font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 cursor-pointer"              style={{borderRadius: '5px'}}
            >
              <div className="flex items-center">
                <ArrowLeftEndOnRectangleIcon className="w-4 h-4 mr-2" />
                Logout
              </div>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}