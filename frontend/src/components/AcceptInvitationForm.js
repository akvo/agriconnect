"use client";

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { 
  UserIcon, 
  LockClosedIcon, 
  ExclamationCircleIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  KeyIcon
} from "@heroicons/react/24/outline";

export default function AcceptInvitationForm({ invitationToken, userInfo, onSuccess }) {
  const [formData, setFormData] = useState({
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUserSession } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    // Validate password length
    if (formData.password.length < 8) {
      setError("Password must be at least 8 characters long");
      return;
    }

    setLoading(true);

    try {
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_BASE_URL}/api/auth/accept-invitation/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies for refresh token
        body: JSON.stringify({
          invitation_token: invitationToken,
          password: formData.password,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        // Set user session with the returned access token and user data
        if (window.setUserSession) {
          window.setUserSession(data.user, data.access_token);
        }
        
        onSuccess?.(data.user);
      } else {
        setError(data.detail || "Failed to accept invitation");
      }
    } catch (err) {
      setError("Failed to accept invitation. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full bg-white/80 backdrop-blur-md p-8 shadow-lg" style={{borderRadius: '5px'}}>
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary mb-4" style={{borderRadius: '5px'}}>
          <KeyIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-2">
          Set Your Password
        </h2>
        <p className="text-secondary-600">Create a secure password to complete your account setup</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 mb-6 animate-scale-in" style={{borderRadius: '5px'}}>
          <div className="flex items-center">
            <ExclamationCircleIcon className="w-5 h-5 text-red-600 mr-2 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        </div>
      )}

      {/* User Info Display */}
      {userInfo && (
        <div className="bg-gray-50 p-4 mb-6 border border-gray-200" style={{borderRadius: '5px'}}>
          <div className="flex items-center">
            <UserIcon className="w-5 h-5 text-secondary-600 mr-3" />
            <div>
              <p className="font-semibold text-secondary-900">{userInfo.full_name}</p>
              <p className="text-sm text-secondary-600">
                {userInfo.email} • {userInfo.user_type === 'admin' ? 'Administrator' : 'Extension Officer'}
              </p>
            </div>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label
            htmlFor="password"
            className="block text-sm font-semibold text-secondary-700"
          >
            New Password
          </label>
          <div className="relative">
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200"
              style={{borderRadius: '5px'}}
              placeholder="••••••••"
            />
            <LockClosedIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
          <p className="text-xs text-secondary-500 mt-1 ml-1">
            Must be at least 8 characters long
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="confirmPassword"
            className="block text-sm font-semibold text-secondary-700"
          >
            Confirm Password
          </label>
          <div className="relative">
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200"
              style={{borderRadius: '5px'}}
              placeholder="••••••••"
            />
            <LockClosedIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-primary text-white py-3 px-6 font-semibold text-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-70 disabled:cursor-not-allowed transform transition-all duration-200"
          style={{borderRadius: '5px'}}
        >
          {loading ? (
            <div className="flex items-center justify-center">
              <ArrowPathIcon className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
              Setting up your account...
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <span>Complete Account Setup</span>
              <CheckCircleIcon className="ml-2 w-5 h-5" />
            </div>
          )}
        </button>
      </form>

      <div className="mt-8 text-center">
        <div className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3" style={{borderRadius: '5px'}}>
          <div className="flex items-center justify-center mb-2">
            <CheckCircleIcon className="w-5 h-5 text-blue-600 mr-2" />
            <span className="font-medium text-sm">Secure Account Setup</span>
          </div>
          <p className="text-xs">
            Your password will be encrypted and stored securely. After setting your password, 
            you'll be automatically logged in to AgriConnect.
          </p>
        </div>
      </div>
    </div>
  );
}