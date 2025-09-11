"use client";

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import {
  UserIcon,
  EnvelopeIcon,
  LockClosedIcon,
  ExclamationCircleIcon,
  AtSymbolIcon,
  ArrowRightIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";

export default function LoginForm({ onSuccess }) {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result = await login(formData.email, formData.password);

    if (result.success) {
      onSuccess?.();
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

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
          <UserIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-2">
          Welcome Back
        </h2>
        <p className="text-secondary-600">
          Sign in to your AgriConnect account
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

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label
            htmlFor="email"
            className="block text-sm font-semibold text-secondary-700"
          >
            Email Address
          </label>
          <div className="relative">
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200 bg-gray-50 focus:bg-white"
              style={{ borderRadius: "5px" }}
              placeholder="your@email.com"
            />
            <AtSymbolIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="password"
            className="block text-sm font-semibold text-secondary-700"
          >
            Password
          </label>
          <div className="relative">
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200 bg-gray-50 focus:bg-white"
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
              Signing in...
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <span>Sign In</span>
              <ArrowRightIcon className="ml-2 w-5 h-5" />
            </div>
          )}
        </button>
      </form>

      <div className="mt-8 text-center">
        <p className="text-sm text-secondary-500 font-medium">
          Access is by invitation only. Contact your administrator for access.
        </p>
      </div>
    </div>
  );
}
