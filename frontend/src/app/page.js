"use client";

import { useState, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";
import LoginForm from "../components/LoginForm";
import Dashboard from "../components/Dashboard";
import { ArrowPathIcon, SparklesIcon, CheckCircleIcon, CommandLineIcon } from "@heroicons/react/24/outline";

export default function Home() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState("login");
  const [successMessage, setSuccessMessage] = useState("");

  const handleLoginSuccess = () => {
    // User state will be updated by AuthContext, component will re-render
    setSuccessMessage("Login successful! Welcome to AgriConnect.");
  };


  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-brand">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
            <div className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse" style={{borderRadius: '5px'}}></div>
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
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-accent-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary-100/30 blur-2xl" style={{borderRadius: '5px'}}></div>
      </div>
      
      <div className="w-full max-w-[36rem] relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-slide-up">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-primary mb-6" style={{borderRadius: '5px', border: '1px solid rgb(191, 219, 254)'}}>
            <CommandLineIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-5xl font-bold text-gradient mb-3 tracking-tight">AgriConnect</h1>
          <p className="text-secondary-600 text-lg font-medium">Agricultural Extension Platform</p>
          <div className="w-24 h-1 bg-gradient-primary mx-auto mt-4" style={{borderRadius: '5px'}}></div>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="bg-primary-50 border border-primary-200 text-primary-800 px-6 py-4 mb-6 text-center animate-scale-in backdrop-blur-sm" style={{borderRadius: '5px'}}>
            <div className="flex items-center justify-center mb-2">
              <CheckCircleIcon className="w-5 h-5 text-primary-600 mr-2" />
              <span className="font-medium">Success!</span>
            </div>
            {successMessage}
          </div>
        )}

        {/* Authentication Forms */}
        <div className="animate-fade-in">
          <LoginForm
            onSuccess={handleLoginSuccess}
          />
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
