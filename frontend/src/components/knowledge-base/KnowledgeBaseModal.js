"use client";

import { useState } from "react";
import knowledgeBaseApi from "../../lib/knowledgeBaseApi";
import { XMarkIcon } from "@heroicons/react/24/outline";

export default function KnowledgeBaseModal({
  onClose,
  onKnowledgeBaseUpdated,
  knowledgeBase = {},
}) {
  const [formData, setFormData] = useState({
    title: knowledgeBase.title || "",
    description: knowledgeBase.description || "",
    is_active: knowledgeBase.is_active ?? false,
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (!knowledgeBase.id) {
        // CREATE → do NOT send is_active
        await knowledgeBaseApi.create({
          title: formData.title,
          description: formData.description,
          is_active: formData.is_active,
        });
      } else {
        // UPDATE → send is_active
        await knowledgeBaseApi.update(knowledgeBase.id, formData);
      }

      onKnowledgeBaseUpdated();
    } catch (err) {
      setError(
        err.response?.data?.detail || "Failed to update knowledge base."
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleActive = () => {
    setFormData((prev) => ({ ...prev, is_active: !prev.is_active }));
  };

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div
        className="bg-white/90 backdrop-blur-md w-full max-w-[42rem] animate-scale-in p-8"
        style={{ borderRadius: "5px", border: "1px solid rgb(191, 219, 254)" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            Knowledge Base Details
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {error && (
            <div
              className="bg-red-50 border border-red-200 p-3 mb-4"
              style={{ borderRadius: "5px" }}
            >
              <div className="text-red-700 text-sm">{error}</div>
            </div>
          )}

          <div className="space-y-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Title *
              </label>
              <input
                type="text"
                name="title"
                required
                value={formData.title}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:ring-green-500"
                style={{ borderRadius: "5px" }}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={4}
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:ring-green-500"
                style={{ borderRadius: "5px" }}
              />
            </div>

            {/* Active Toggle — shown for BOTH create & update */}
            <div className="flex items-center mt-4 space-x-3">
              <button
                type="button"
                onClick={toggleActive}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all ${
                  formData.is_active ? "bg-green-500" : "bg-gray-300"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                    formData.is_active ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>

              <span className="text-sm text-gray-600">
                {formData.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          </div>

          {/* Footer Buttons */}
          <div className="mt-6 flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-gray-50 text-sm py-2 px-4 font-medium text-gray-700 hover:bg-gray-100"
              style={{ borderRadius: "5px" }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-green-600 text-sm py-2 px-4 text-white hover:bg-green-700 disabled:opacity-50"
              style={{ borderRadius: "5px" }}
            >
              {loading ? "Saving..." : "Save Knowledge Base"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
