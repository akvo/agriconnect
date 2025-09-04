'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import LoginForm from '../components/LoginForm';
import RegisterForm from '../components/RegisterForm';
import Dashboard from '../components/Dashboard';

export default function Home() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState('login'); // 'login', 'register'
  const [successMessage, setSuccessMessage] = useState('');

  const handleLoginSuccess = () => {
    // User state will be updated by AuthContext, component will re-render
    setSuccessMessage('Login successful! Welcome to AgriConnect.');
  };

  const handleRegisterSuccess = (userData) => {
    setSuccessMessage(`Registration successful! Please log in with your credentials.`);
    setCurrentView('login');
  };

  const handleSwitchToRegister = () => {
    setCurrentView('register');
    setSuccessMessage('');
  };

  const handleSwitchToLogin = () => {
    setCurrentView('login');
    setSuccessMessage('');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (user) {
    return <Dashboard />;
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">AgriConnect</h1>
          <p className="text-gray-600">Agricultural Extension Platform</p>
        </div>

        {/* Success Message */}
        {successMessage && (
          <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-6 text-center">
            {successMessage}
          </div>
        )}

        {/* Authentication Forms */}
        {currentView === 'login' ? (
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

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-gray-500">
            AgriConnect © 2025. Connecting farmers with agricultural extension services.
          </p>
        </div>
      </div>
    </div>
  );
}
