"use client";

import { useState } from "react";
import { XMarkIcon, UserPlusIcon } from "@heroicons/react/24/outline";
import api from "../../lib/api";

export default function CreateCustomerModal({ onClose, onCustomerCreated }) {
  const [formData, setFormData] = useState({
    phone_number: "",
    full_name: "",
    language: "en",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const submitData = {
        phone_number: formData.phone_number,
        language: formData.language,
      };

      if (formData.full_name.trim()) {
        submitData.full_name = formData.full_name;
      }

      await api.post("/customers/", submitData);
      onCustomerCreated();
    } catch (err) {
      console.error("Error creating customer:", err);
      setError(err.response?.data?.detail || "Failed to create customer");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div
        className="bg-white/90 backdrop-blur-md w-full max-w-[32rem] animate-scale-in p-8"
        style={{ borderRadius: "5px", border: "1px solid rgb(191, 219, 254)" }}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900">
              Create New Customer
            </h3>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 cursor-pointer"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {error && (
            <div
              className="bg-red-50 border border-red-200 p-3 mb-4"
              style={{ borderRadius: "5px" }}
            >
              <div className="text-red-700 text-sm">{error}</div>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label
                htmlFor="phone_number"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Phone Number *
              </label>
              <input
                type="tel"
                id="phone_number"
                name="phone_number"
                required
                value={formData.phone_number}
                onChange={handleChange}
                placeholder="+255123456789"
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
              />
            </div>

            <div>
              <label
                htmlFor="full_name"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Full Name
              </label>
              <input
                type="text"
                id="full_name"
                name="full_name"
                value={formData.full_name}
                onChange={handleChange}
                placeholder="Customer's full name (optional)"
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
              />
            </div>

            <div>
              <label
                htmlFor="language"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Preferred Language
              </label>
              <select
                id="language"
                name="language"
                value={formData.language}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
              >
                <option value="en">English</option>
                <option value="sw">Swahili</option>
              </select>
            </div>
          </div>

          <div className="mt-6 flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 cursor-pointer transition-colors duration-200"
              style={{ borderRadius: "5px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-green-600 py-2 px-4 border border-transparent text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors duration-200"
              style={{ borderRadius: "5px" }}
            >
              {loading ? "Creating..." : "Create Customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
