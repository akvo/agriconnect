"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import LoginForm from "../components/LoginForm";
import RegisterForm from "../components/RegisterForm";
import Dashboard from "../components/Dashboard";

export default function Home() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState("login"); // 'login', 'register'
  const [successMessage, setSuccessMessage] = useState("");

  const handleLoginSuccess = () => {
    // User state will be updated by AuthContext, component will re-render
    setSuccessMessage("Login successful! Welcome to AgriConnect.");
  };

  const handleRegisterSuccess = (userData) => {
    setSuccessMessage(
      `Registration successful! Please log in with your credentials.`
    );
    setCurrentView("login");
  };

  const handleSwitchToRegister = () => {
    setCurrentView("register");
    setSuccessMessage("");
  };

  const handleSwitchToLogin = () => {
    setCurrentView("login");
    setSuccessMessage("");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-brand">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary-200 border-t-primary-600 mx-auto mb-6"></div>
            <div className="absolute inset-0 rounded-full bg-gradient-primary opacity-20 blur-lg animate-pulse"></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">Loading AgriConnect...</p>
          <p className="text-secondary-500 text-sm mt-2">Please wait while we prepare your dashboard</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <Dashboard />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-brand relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 rounded-full bg-primary-200/20 blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-accent-200/20 blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full bg-primary-100/30 blur-2xl"></div>
      </div>
      
      <div className="w-full max-w-[36rem] relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-slide-up">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-primary shadow-brand mb-6">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v18m0-18l4 4m-4-4l-4 4m4 14l4-4m-4 4l-4-4"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </div>
          <h1 className="text-5xl font-bold text-gradient mb-3 tracking-tight">AgriConnect</h1>
          <p className="text-secondary-600 text-lg font-medium">Agricultural Extension Platform</p>
          <div className="w-24 h-1 bg-gradient-primary rounded-full mx-auto mt-4"></div>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="bg-primary-50 border border-primary-200 text-primary-800 px-6 py-4 rounded-xl mb-6 text-center shadow-lg animate-scale-in backdrop-blur-sm">
            <div className="flex items-center justify-center mb-2">
              <svg className="w-5 h-5 text-primary-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <span className="font-medium">Success!</span>
            </div>
            {successMessage}
          </div>
        )}

        {/* Authentication Forms */}
        <div className="animate-fade-in">
          {currentView === "login" ? (
            <LoginForm
              onSuccess={handleLoginSuccess}
              onSwitchToRegister={handleSwitchToRegister}
            />
          ) : (
            <RegisterForm
              onSuccess={handleRegisterSuccess}
              onSwitchToLogin={handleSwitchToLogin}
            />
          )}
        </div>

        {/* Footer */}
        <div className="mt-8 text-center animate-fade-in">
          <p className="text-xs text-secondary-500 font-medium">
            AgriConnect © 2025. Connecting farmers with agricultural extension services.
          </p>
          <p className="text-xs text-secondary-400 mt-1">
            Empowering sustainable agriculture through digital innovation
          </p>
        </div>
      </div>
    </div>
  );
}
