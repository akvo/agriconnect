"use client";

import Link from "next/link";
import {
  ExclamationTriangleIcon,
  HomeIcon,
  ArrowLeftIcon,
} from "@heroicons/react/24/outline";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-brand flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        {/* 404 Icon */}
        <div className="mb-8">
          <div
            className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-orange-500 to-red-500 mb-6"
            style={{ borderRadius: "5px" }}
          >
            <ExclamationTriangleIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-6xl font-bold text-gradient mb-2">404</h1>
          <h2 className="text-2xl font-bold text-secondary-900 mb-4">
            Page Not Found
          </h2>
          <p className="text-secondary-600 text-lg leading-relaxed">
            The page you&apos;re looking for doesn&apos;t exist or has been
            moved.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="space-y-4">
          <Link
            href="/"
            className="inline-flex items-center justify-center w-full px-6 py-3 bg-gradient-primary text-white font-semibold transition-all duration-200 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            style={{ borderRadius: "5px" }}
          >
            <HomeIcon className="w-5 h-5 mr-2" />
            Back to Dashboard
          </Link>

          <button
            onClick={() => window.history.back()}
            className="inline-flex items-center justify-center w-full px-6 py-3 bg-white text-secondary-700 font-semibold border border-secondary-300 transition-all duration-200 hover:bg-secondary-50 focus:outline-none focus:ring-2 focus:ring-secondary-500 focus:ring-offset-2"
            style={{ borderRadius: "5px" }}
          >
            <ArrowLeftIcon className="w-5 h-5 mr-2" />
            Go Back
          </button>
        </div>

        {/* Help Text */}
        <div className="mt-8 text-sm text-secondary-500">
          <p>
            If you believe this is an error, please contact support or try
            refreshing the page.
          </p>
        </div>
      </div>
    </div>
  );
}
