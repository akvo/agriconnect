"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  LockClosedIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  KeyIcon,
} from "@heroicons/react/24/outline";

export default function ResetPasswordForm({ resetToken, userEmail }) {
  const [formData, setFormData] = useState({
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const router = useRouter();

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
      const response = await fetch(`/api/auth/reset-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          reset_token: resetToken,
          password: formData.password,
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setSuccess(true);
      } else {
        setError(data.detail || "Failed to reset password");
      }
    } catch (err) {
      setError("Failed to reset password. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div
        className="w-full bg-white/80 backdrop-blur-md p-8 shadow-lg"
        style={{ borderRadius: "5px" }}
      >
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary mb-4"
            style={{ borderRadius: "5px" }}
          >
            <CheckCircleIcon className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-secondary-900 mb-2">
            Password Reset Complete
          </h2>
          <p className="text-secondary-600">
            Your password has been successfully reset. You can now log in with
            your new password.
          </p>
        </div>

        <div className="text-center">
          <button
            onClick={() => router.push("/")}
            className="w-full bg-gradient-primary text-white py-3 px-6 font-semibold text-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200"
            style={{ borderRadius: "5px" }}
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      className="w-full bg-white/80 backdrop-blur-md p-8 shadow-lg"
      style={{ borderRadius: "5px" }}
    >
      <div className="text-center mb-8">
        <div
          className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary mb-4"
          style={{ borderRadius: "5px" }}
        >
          <KeyIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-2">
          Reset Your Password
        </h2>
        <p className="text-secondary-600">
          Create a new secure password for your account
        </p>
      </div>

      {error && (
        <div
          className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 mb-6 animate-scale-in"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center">
            <ExclamationCircleIcon className="w-5 h-5 text-red-600 mr-2 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        </div>
      )}

      {/* User Email Display */}
      {userEmail && (
        <div
          className="bg-gray-50 p-4 mb-6 border border-gray-200"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center justify-center">
            <LockClosedIcon className="w-5 h-5 text-secondary-600 mr-3" />
            <p className="text-secondary-900">
              Resetting password for: <strong>{userEmail}</strong>
            </p>
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
              style={{ borderRadius: "5px" }}
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
              style={{ borderRadius: "5px" }}
              placeholder="••••••••"
            />
            <LockClosedIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-primary text-white py-3 px-6 font-semibold text-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-70 disabled:cursor-not-allowed transform transition-all duration-200"
          style={{ borderRadius: "5px" }}
        >
          {loading ? (
            <div className="flex items-center justify-center">
              <ArrowPathIcon className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
              Resetting password...
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <span>Reset Password</span>
              <CheckCircleIcon className="ml-2 w-5 h-5" />
            </div>
          )}
        </button>
      </form>

      <div className="mt-8 text-center">
        <div
          className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center justify-center mb-2">
            <CheckCircleIcon className="w-5 h-5 text-blue-600 mr-2" />
            <span className="font-medium text-sm">Secure Password Reset</span>
          </div>
          <p className="text-xs">
            Your new password will be encrypted and stored securely. After
            resetting, you can log in with your new password.
          </p>
        </div>
      </div>
    </div>
  );
}
