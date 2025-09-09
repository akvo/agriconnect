"use client";

import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { 
  UserIcon, 
  AtSymbolIcon, 
  PhoneIcon,
  LockClosedIcon, 
  ExclamationCircleIcon,
  ChevronDownIcon,
  ArrowPathIcon,
  UserPlusIcon,
  ClipboardDocumentListIcon
} from "@heroicons/react/24/outline";

export default function RegisterForm({ onSuccess, onSwitchToLogin }) {
  const [formData, setFormData] = useState({
    email: "",
    phone_number: "",
    password: "",
    confirmPassword: "",
    full_name: "",
    user_type: "eo", // default to extension officer
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();

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

    // Validate phone number format
    if (
      !formData.phone_number.startsWith("+") ||
      formData.phone_number.length < 10
    ) {
      setError("Phone number must start with + and be at least 10 characters");
      return;
    }

    setLoading(true);

    const { confirmPassword, ...registrationData } = formData;
    const result = await register(registrationData);

    if (result.success) {
      onSuccess?.(result.user);
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="w-full bg-white/80 backdrop-blur-md p-8 shadow-lg" style={{borderRadius: '5px'}}>
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-primary mb-4" style={{borderRadius: '5px'}}>
          <UserPlusIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-2">
          Create Account
        </h2>
        <p className="text-secondary-600">Join the AgriConnect community</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 mb-6 animate-scale-in" style={{borderRadius: '5px'}}>
          <div className="flex items-center">
            <ExclamationCircleIcon className="w-5 h-5 text-red-600 mr-2 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label
            htmlFor="full_name"
            className="block text-sm font-semibold text-secondary-700"
          >
            Full Name
          </label>
          <div className="relative">
            <input
              type="text"
              id="full_name"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200 "
              style={{borderRadius: '5px'}}
              placeholder="Enter your full name"
            />
            <UserIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
        </div>

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
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200 "
              style={{borderRadius: '5px'}}
              placeholder="your@email.com"
            />
            <AtSymbolIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="phone_number"
            className="block text-sm font-semibold text-secondary-700"
          >
            Phone Number
          </label>
          <div className="relative">
            <input
              type="tel"
              id="phone_number"
              name="phone_number"
              value={formData.phone_number}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200 "
              style={{borderRadius: '5px'}}
              placeholder="+1234567890"
            />
            <PhoneIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
          </div>
          <p className="text-xs text-secondary-500 mt-1 ml-1">
            Must start with + and country code
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="user_type"
            className="block text-sm font-semibold text-secondary-700"
          >
            User Type
          </label>
          <div className="relative">
            <select
              id="user_type"
              name="user_type"
              value={formData.user_type}
              onChange={handleChange}
              required
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200  appearance-none"
              style={{borderRadius: '5px'}}
            >
              <option value="eo">Extension Officer</option>
              <option value="admin">Administrator</option>
            </select>
            <ClipboardDocumentListIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
            <ChevronDownIcon className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400 pointer-events-none" />
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
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200 "
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
              className="w-full px-4 py-3 pl-11 bg-gray-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500  transition-all duration-200 "
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
              Creating account...
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <span>Create Account</span>
              <UserPlusIcon className="ml-2 w-5 h-5" />
            </div>
          )}
        </button>
      </form>

      <div className="mt-8 text-center">
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-secondary-200"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-white text-secondary-500 font-medium">Already have an account?</span>
          </div>
        </div>
        <button
          onClick={onSwitchToLogin}
          className="mt-4 text-primary-600 hover:text-primary-700 font-semibold text-sm transition-colors duration-200 hover:underline cursor-pointer"
        >
          Sign in here
        </button>
      </div>
    </div>
  );
}
