"use client";

import { useState } from "react";
import { XMarkIcon, PencilIcon } from "@heroicons/react/24/outline";
import api from "../../lib/api";

export default function EditCustomerModal({
  customer,
  onClose,
  onCustomerUpdated,
}) {
  const [formData, setFormData] = useState({
    full_name: customer.full_name || "",
    language: customer.language || "en",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const submitData = {
        full_name: formData.full_name.trim(),
        language: formData.language,
      };

      await api.put(`/customers/${customer.id}`, submitData);
      onCustomerUpdated();
    } catch (err) {
      console.error("Error updating customer:", err);
      setError(err.response?.data?.detail || "Failed to update customer");
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
            <h3 className="text-lg font-medium text-gray-900">Edit Customer</h3>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Phone Number
              </label>
              <input
                type="tel"
                value={customer.phone_number}
                disabled
                className="w-full px-3 py-2 border border-gray-300 bg-gray-100 text-gray-500 cursor-not-allowed"
                style={{ borderRadius: "5px" }}
              />
              <p className="text-xs text-gray-500 mt-1">
                Phone number cannot be changed
              </p>
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
                placeholder="Customer's full name"
                className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
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
                className="w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
              >
                <option value="en">English</option>
                <option value="sw">Swahili</option>
              </select>
            </div>

            <div className="bg-gray-50 p-3 rounded-md">
              <h4 className="text-sm font-medium text-gray-900 mb-2">
                Customer Info
              </h4>
              <div className="text-sm text-gray-600 space-y-1">
                <p>
                  <strong>ID:</strong> #{customer.id}
                </p>
                <p>
                  <strong>Created:</strong>{" "}
                  {new Date(customer.created_at).toLocaleDateString()}
                </p>
                {customer.updated_at &&
                  customer.updated_at !== customer.created_at && (
                    <p>
                      <strong>Last Updated:</strong>{" "}
                      {new Date(customer.updated_at).toLocaleDateString()}
                    </p>
                  )}
              </div>
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
              {loading ? "Updating..." : "Update Customer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
