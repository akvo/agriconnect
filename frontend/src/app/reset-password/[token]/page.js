"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "../../../contexts/AuthContext";
import ResetPasswordForm from "../../../components/ResetPasswordForm";
import {
  ArrowPathIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  KeyIcon,
} from "@heroicons/react/24/outline";

export default function ResetPasswordPage() {
  const [tokenStatus, setTokenStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { token } = useParams();
  const router = useRouter();
  const { user } = useAuth();

  // Redirect if user is already logged in
  useEffect(() => {
    if (user) {
      router.push("/");
      return;
    }
  }, [user, router]);

  // Verify reset token on component mount
  useEffect(() => {
    if (!token) {
      setError("Invalid reset link");
      setLoading(false);
      return;
    }

    const verifyToken = async () => {
      try {
        const response = await fetch(`/api/auth/verify-reset-token/${token}`);
        const data = await response.json();

        if (response.ok) {
          setTokenStatus(data);
        } else {
          setError(data.detail || "Failed to verify reset token");
        }
      } catch (err) {
        setError("Failed to verify reset token. Please check your connection.");
      } finally {
        setLoading(false);
      }
    };

    verifyToken();
  }, [token]);

  if (user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-brand">
        <div className="text-center animate-fade-in">
          <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
          <p className="text-secondary-700 font-medium text-lg">
            Redirecting...
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-brand">
        <div className="text-center animate-fade-in">
          <div className="relative">
            <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
            <div
              className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse"
              style={{ borderRadius: "5px" }}
            ></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">
            Verifying reset link...
          </p>
          <p className="text-secondary-500 text-sm mt-2">
            Please wait while we validate your reset token
          </p>
        </div>
      </div>
    );
  }

  if (error || !tokenStatus?.valid) {
    const errorMessage = error || "Invalid reset token";
    const isExpired = tokenStatus?.expired;

    return (
      <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-brand relative overflow-hidden">
        {/* Background decorative elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div
            className="absolute -top-40 -right-40 w-80 h-80 bg-red-200/20 blur-3xl"
            style={{ borderRadius: "5px" }}
          ></div>
          <div
            className="absolute -bottom-40 -left-40 w-96 h-96 bg-red-200/20 blur-3xl"
            style={{ borderRadius: "5px" }}
          ></div>
        </div>

        <div className="w-full max-w-[36rem] relative z-10">
          {/* Header */}
          <div className="text-center mb-8 animate-slide-up">
            <div
              className="inline-flex items-center justify-center w-20 h-20 bg-red-500 mb-6"
              style={{
                borderRadius: "5px",
                border: "1px solid rgb(254, 202, 202)",
              }}
            >
              <ExclamationCircleIcon className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-secondary-900 mb-3 tracking-tight">
              {isExpired ? "Link Expired" : "Invalid Link"}
            </h1>
            <p className="text-secondary-600 text-lg font-medium">
              AgriConnect Platform
            </p>
            <div
              className="w-24 h-1 bg-red-500 mx-auto mt-4"
              style={{ borderRadius: "5px" }}
            ></div>
          </div>

          {/* Error Message */}
          <div
            className="bg-white/80 backdrop-blur-md p-8 shadow-lg animate-fade-in"
            style={{ borderRadius: "5px" }}
          >
            <div
              className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 mb-6 text-center"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex items-center justify-center mb-2">
                <ExclamationCircleIcon className="w-6 h-6 text-red-600 mr-2" />
                <span className="font-semibold">
                  {isExpired ? "Reset Link Expired" : "Invalid Reset Link"}
                </span>
              </div>
              <p className="text-sm">{errorMessage}</p>
            </div>

            {isExpired && (
              <div
                className="bg-blue-50 border border-blue-200 text-blue-800 px-6 py-4 mb-6 text-center"
                style={{ borderRadius: "5px" }}
              >
                <p className="text-sm">
                  <strong>Need a new reset link?</strong>
                  <br />
                  Password reset links expire after 1 hour. Please request a new
                  one.
                </p>
              </div>
            )}

            <div className="text-center space-y-3">
              <button
                onClick={() => router.push("/forgot-password")}
                className="w-full bg-gradient-primary text-white py-3 px-6 font-semibold focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200"
                style={{ borderRadius: "5px" }}
              >
                Request New Reset Link
              </button>
              <button
                onClick={() => router.push("/")}
                className="w-full bg-gray-100 text-secondary-700 py-3 px-6 font-semibold focus:outline-none focus:ring-2 focus:ring-gray-300 focus:ring-offset-2 transition-all duration-200 hover:bg-gray-200"
                style={{ borderRadius: "5px" }}
              >
                Return to Login
              </button>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center animate-fade-in">
            <p className="text-xs text-secondary-500 font-medium">
              AgriConnect © 2025. Connecting farmers with agricultural
              extension services.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-brand relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute -top-40 -right-40 w-80 h-80 bg-primary-200/20 blur-3xl"
          style={{ borderRadius: "5px" }}
        ></div>
        <div
          className="absolute -bottom-40 -left-40 w-96 h-96 bg-accent-200/20 blur-3xl"
          style={{ borderRadius: "5px" }}
        ></div>
        <div
          className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary-100/30 blur-2xl"
          style={{ borderRadius: "5px" }}
        ></div>
      </div>

      <div className="w-full max-w-[36rem] relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-slide-up">
          <div
            className="inline-flex items-center justify-center w-20 h-20 bg-gradient-primary mb-6"
            style={{
              borderRadius: "5px",
              border: "1px solid rgb(191, 219, 254)",
            }}
          >
            <KeyIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gradient mb-3 tracking-tight">
            Reset Password
          </h1>
          <p className="text-secondary-600 text-lg font-medium">
            AgriConnect Platform
          </p>
          <div
            className="w-24 h-1 bg-gradient-primary mx-auto mt-4"
            style={{ borderRadius: "5px" }}
          ></div>
        </div>

        {/* Token Verified Info */}
        <div
          className="bg-primary-50 border border-primary-200 text-primary-800 px-6 py-4 mb-6 text-center animate-scale-in backdrop-blur-sm"
          style={{ borderRadius: "5px" }}
        >
          <div className="flex items-center justify-center mb-2">
            <CheckCircleIcon className="w-5 h-5 text-primary-600 mr-2" />
            <span className="font-medium">Reset Link Verified!</span>
          </div>
          <p className="text-sm">
            You can now create a new password for your account.
          </p>
        </div>

        {/* Reset Password Form */}
        <div className="animate-fade-in">
          <ResetPasswordForm
            resetToken={token}
            userEmail={tokenStatus?.user_email}
          />
        </div>

        {/* Footer */}
        <div className="mt-8 text-center animate-fade-in">
          <p className="text-xs text-secondary-500 font-medium">
            AgriConnect © 2025. Connecting farmers with agricultural extension
            services.
          </p>
          <p className="text-xs text-secondary-400 mt-1">
            Empowering sustainable agriculture through digital innovation
          </p>
        </div>
      </div>
    </div>
  );
}
