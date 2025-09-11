"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "../../../contexts/AuthContext";
import AcceptInvitationForm from "../../../components/AcceptInvitationForm";
import { ArrowPathIcon, ExclamationCircleIcon, CheckCircleIcon, CommandLineIcon } from "@heroicons/react/24/outline";

export default function AcceptInvitationPage() {
  const [invitationStatus, setInvitationStatus] = useState(null);
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

  // Verify invitation token on component mount
  useEffect(() => {
    if (!token) {
      setError("Invalid invitation link");
      setLoading(false);
      return;
    }

    const verifyInvitation = async () => {
      try {
        const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${API_BASE_URL}/api/auth/verify-invitation/${token}`);
        const data = await response.json();

        if (response.ok) {
          setInvitationStatus(data);
        } else {
          setError(data.detail || "Failed to verify invitation");
        }
      } catch (err) {
        setError("Failed to verify invitation. Please check your connection.");
      } finally {
        setLoading(false);
      }
    };

    verifyInvitation();
  }, [token]);

  const handleInvitationAccepted = () => {
    // The AcceptInvitationForm component will handle login and redirect
    router.push("/");
  };

  if (user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-brand">
        <div className="text-center animate-fade-in">
          <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-6" />
          <p className="text-secondary-700 font-medium text-lg">Redirecting...</p>
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
            <div className="absolute inset-0 bg-gradient-primary opacity-20 blur-lg animate-pulse" style={{borderRadius: '5px'}}></div>
          </div>
          <p className="text-secondary-700 font-medium text-lg">Verifying invitation...</p>
          <p className="text-secondary-500 text-sm mt-2">Please wait while we validate your invitation</p>
        </div>
      </div>
    );
  }

  if (error || !invitationStatus?.valid) {
    const errorMessage = error || invitationStatus?.error_message || "Invalid invitation";
    const isExpired = invitationStatus?.expired;

    return (
      <div className="min-h-screen flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-brand relative overflow-hidden">
        {/* Background decorative elements */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-red-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
          <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-red-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
        </div>
        
        <div className="w-full max-w-[36rem] relative z-10">
          {/* Header */}
          <div className="text-center mb-8 animate-slide-up">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-red-500 mb-6" style={{borderRadius: '5px', border: '1px solid rgb(254, 202, 202)'}}>
              <ExclamationCircleIcon className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-4xl font-bold text-secondary-900 mb-3 tracking-tight">
              {isExpired ? "Invitation Expired" : "Invalid Invitation"}
            </h1>
            <p className="text-secondary-600 text-lg font-medium">AgriConnect Platform</p>
            <div className="w-24 h-1 bg-red-500 mx-auto mt-4" style={{borderRadius: '5px'}}></div>
          </div>

          {/* Error Message */}
          <div className="bg-white/80 backdrop-blur-md p-8 shadow-lg animate-fade-in" style={{borderRadius: '5px'}}>
            <div className="bg-red-50 border border-red-200 text-red-800 px-6 py-4 mb-6 text-center" style={{borderRadius: '5px'}}>
              <div className="flex items-center justify-center mb-2">
                <ExclamationCircleIcon className="w-6 h-6 text-red-600 mr-2" />
                <span className="font-semibold">
                  {isExpired ? "Invitation Expired" : "Invalid Invitation"}
                </span>
              </div>
              <p className="text-sm">{errorMessage}</p>
            </div>

            {isExpired && (
              <div className="bg-blue-50 border border-blue-200 text-blue-800 px-6 py-4 mb-6 text-center" style={{borderRadius: '5px'}}>
                <p className="text-sm">
                  <strong>Need a new invitation?</strong><br />
                  Please contact your administrator to resend your invitation link.
                </p>
              </div>
            )}

            <div className="text-center">
              <button
                onClick={() => router.push("/")}
                className="bg-gradient-primary text-white py-3 px-6 font-semibold focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200"
                style={{borderRadius: '5px'}}
              >
                Return to Login
              </button>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-8 text-center animate-fade-in">
            <p className="text-xs text-secondary-500 font-medium">
              AgriConnect © 2025. Connecting farmers with agricultural extension services.
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
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-accent-200/20 blur-3xl" style={{borderRadius: '5px'}}></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-primary-100/30 blur-2xl" style={{borderRadius: '5px'}}></div>
      </div>
      
      <div className="w-full max-w-[36rem] relative z-10">
        {/* Header */}
        <div className="text-center mb-8 animate-slide-up">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-primary mb-6" style={{borderRadius: '5px', border: '1px solid rgb(191, 219, 254)'}}>
            <CheckCircleIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gradient mb-3 tracking-tight">Welcome to AgriConnect</h1>
          <p className="text-secondary-600 text-lg font-medium">Complete Your Account Setup</p>
          <div className="w-24 h-1 bg-gradient-primary mx-auto mt-4" style={{borderRadius: '5px'}}></div>
        </div>

        {/* Invitation Info */}
        {invitationStatus?.user_info && (
          <div className="bg-primary-50 border border-primary-200 text-primary-800 px-6 py-4 mb-6 text-center animate-scale-in backdrop-blur-sm" style={{borderRadius: '5px'}}>
            <div className="flex items-center justify-center mb-2">
              <CheckCircleIcon className="w-5 h-5 text-primary-600 mr-2" />
              <span className="font-medium">Invitation Verified!</span>
            </div>
            <p className="text-sm">
              <strong>{invitationStatus.user_info.full_name}</strong><br />
              {invitationStatus.user_info.email} • {invitationStatus.user_info.user_type === 'admin' ? 'Administrator' : 'Extension Officer'}
            </p>
          </div>
        )}

        {/* Accept Invitation Form */}
        <div className="animate-fade-in">
          <AcceptInvitationForm
            invitationToken={token}
            userInfo={invitationStatus?.user_info}
            onSuccess={handleInvitationAccepted}
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