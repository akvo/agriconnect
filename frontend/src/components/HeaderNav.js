"use client";

import { useAuth } from "../contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function HeaderNav({ title = "Dashboard", breadcrumbs = null }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
  };

  const handleBreadcrumbClick = (path) => {
    router.push(path);
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
    <header className="bg-white/90 backdrop-blur-md shadow-lg border-b border-white/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          <div className="flex items-center space-x-4">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-primary shadow-lg">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v18m0-18l4 4m-4-4l-4 4m4 14l4-4m-4 4l-4-4"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
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
                        <svg className="w-4 h-4 text-secondary-400 mx-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7"></path>
                        </svg>
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
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-primary shadow-md">
              <span className="text-sm font-bold text-white">
                {user?.full_name?.charAt(0)?.toUpperCase()}
              </span>
            </div>
            <button
              onClick={handleLogout}
              className="bg-red-500 hover:bg-red-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 shadow-lg hover:shadow-xl cursor-pointer"
            >
              <div className="flex items-center">
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                </svg>
                Logout
              </div>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}