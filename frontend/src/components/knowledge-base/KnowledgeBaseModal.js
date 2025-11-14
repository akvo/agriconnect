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
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (!knowledgeBase.id) {
        // Create new knowledge base
        await knowledgeBaseApi.create(formData);
      } else {
        // Update existing knowledge base
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

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div
        className="bg-white/90 backdrop-blur-md w-full max-w-[42rem] animate-scale-in p-8"
        style={{ borderRadius: "5px", border: "1px solid rgb(191, 219, 254)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">
            Knowledge Base Details
          </h3>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

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
            <div>
              <label
                htmlFor="title"
                className="block text-sm font-medium text-gray-700"
              >
                Title *
              </label>
              <input
                type="text"
                id="title"
                name="title"
                required
                value={formData.title}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
                placeholder="Enter title"
              />
            </div>

            <div>
              <label
                htmlFor="description"
                className="block text-sm font-medium text-gray-700"
              >
                Description
              </label>
              <textarea
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                className="mt-1 block w-full px-3 py-2 bg-gray-50 focus:bg-white focus:outline-none focus:ring-green-500 focus:border-green-500"
                style={{ borderRadius: "5px" }}
                placeholder="Enter description"
                rows={4}
              />
            </div>
          </div>

          <div className="mt-6 flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-white py-2 px-4 bg-gray-50 focus:bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
              style={{ borderRadius: "5px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-green-600 py-2 px-4 border border-transparent text-sm font-medium text-white hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
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
