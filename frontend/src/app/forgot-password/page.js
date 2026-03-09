"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../contexts/AuthContext";
import ForgotPasswordForm from "../../components/ForgotPasswordForm";
import {
  ArrowPathIcon,
  EnvelopeIcon,
} from "@heroicons/react/24/outline";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (user) {
      router.push("/");
    }
  }, [user, router]);

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
          <p className="text-secondary-700 font-medium text-lg">Loading...</p>
        </div>
      </div>
    );
  }

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
            <EnvelopeIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gradient mb-3 tracking-tight">
            Password Reset
          </h1>
          <p className="text-secondary-600 text-lg font-medium">
            AgriConnect Platform
          </p>
          <div
            className="w-24 h-1 bg-gradient-primary mx-auto mt-4"
            style={{ borderRadius: "5px" }}
          ></div>
        </div>

        {/* Forgot Password Form */}
        <div className="animate-fade-in">
          <ForgotPasswordForm />
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
