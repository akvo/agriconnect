"use client";

import { useState } from "react";
import Link from "next/link";
import {
  EnvelopeIcon,
  AtSymbolIcon,
  PhoneIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  PaperAirplaneIcon,
  CheckCircleIcon,
} from "@heroicons/react/24/outline";

export default function ForgotPasswordForm() {
  const [resetMethod, setResetMethod] = useState("email"); // "email" or "phone"
  const [email, setEmail] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const payload =
      resetMethod === "email" ? { email } : { phone_number: phoneNumber };

    try {
      const response = await fetch(`/api/auth/forgot-password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setSuccess(true);
      } else {
        const data = await response.json();
        setError(data.detail || "Failed to send reset link");
      }
    } catch (err) {
      setError("Failed to send reset link. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    const displayValue = resetMethod === "email" ? email : phoneNumber;
    const methodText = resetMethod === "email" ? "email" : "WhatsApp message";

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
            {resetMethod === "email" ? "Check Your Email" : "Check WhatsApp"}
          </h2>
          <p className="text-secondary-600">
            If an account exists with <strong>{displayValue}</strong>, you will
            receive a password reset link via {methodText} shortly.
          </p>
        </div>

        <div
          className="bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 mb-6"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center justify-center mb-2">
            {resetMethod === "email" ? (
              <EnvelopeIcon className="w-5 h-5 text-blue-600 mr-2" />
            ) : (
              <PhoneIcon className="w-5 h-5 text-blue-600 mr-2" />
            )}
            <span className="font-medium text-sm">
              {resetMethod === "email" ? "Email Sent" : "WhatsApp Sent"}
            </span>
          </div>
          <p className="text-xs text-center">
            The reset link will expire in 1 hour.
            {resetMethod === "email" &&
              " If you don't see the email, please check your spam folder."}
          </p>
        </div>

        <div className="text-center">
          <Link
            href="/"
            className="inline-block bg-gradient-primary text-white py-3 px-6 font-semibold focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200"
            style={{ borderRadius: "5px" }}
          >
            Return to Login
          </Link>
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
          <EnvelopeIcon className="w-8 h-8 text-white" />
        </div>
        <h2 className="text-2xl font-bold text-secondary-900 mb-2">
          Forgot Password?
        </h2>
        <p className="text-secondary-600">
          Enter your email or phone number to receive a password reset link.
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

      {/* Method Toggle */}
      <div
        className="flex mb-6 bg-gray-100 p-1"
        style={{ borderRadius: "5px" }}
      >
        <button
          type="button"
          onClick={() => setResetMethod("email")}
          className={`flex-1 py-2 px-4 text-sm font-medium transition-all duration-200 ${
            resetMethod === "email"
              ? "bg-white text-primary-700 shadow-sm"
              : "text-secondary-600 hover:text-secondary-800"
          }`}
          style={{ borderRadius: "4px" }}
        >
          <EnvelopeIcon className="w-4 h-4 inline-block mr-2" />
          Email
        </button>
        <button
          type="button"
          onClick={() => setResetMethod("phone")}
          className={`flex-1 py-2 px-4 text-sm font-medium transition-all duration-200 ${
            resetMethod === "phone"
              ? "bg-white text-primary-700 shadow-sm"
              : "text-secondary-600 hover:text-secondary-800"
          }`}
          style={{ borderRadius: "4px" }}
        >
          <PhoneIcon className="w-4 h-4 inline-block mr-2" />
          WhatsApp
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {resetMethod === "email" ? (
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
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 pl-11 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200 bg-gray-50 focus:bg-white"
                style={{ borderRadius: "5px" }}
                placeholder="your@email.com"
              />
              <AtSymbolIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <label
              htmlFor="phoneNumber"
              className="block text-sm font-semibold text-secondary-700"
            >
              Phone Number
            </label>
            <div className="relative">
              <input
                type="tel"
                id="phoneNumber"
                name="phoneNumber"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                required
                className="w-full px-4 py-3 pl-11 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all duration-200 bg-gray-50 focus:bg-white"
                style={{ borderRadius: "5px" }}
                placeholder="+255712345678"
              />
              <PhoneIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-secondary-400" />
            </div>
            <p className="text-xs text-secondary-500 mt-1 ml-1">
              Enter your phone number with country code (e.g., +255...)
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-primary text-white py-3 px-6 font-semibold text-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:opacity-70 disabled:cursor-not-allowed transform transition-all duration-200"
          style={{ borderRadius: "5px" }}
        >
          {loading ? (
            <div className="flex items-center justify-center">
              <ArrowPathIcon className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" />
              Sending...
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <span>Send Reset Link</span>
              <PaperAirplaneIcon className="ml-2 w-5 h-5" />
            </div>
          )}
        </button>
      </form>

      <div className="mt-8 text-center">
        <Link
          href="/"
          className="text-sm text-primary-600 hover:text-primary-700 font-medium"
        >
          Back to Login
        </Link>
      </div>
    </div>
  );
}
