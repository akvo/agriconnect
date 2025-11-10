"use client";

import { useState, useRef, useEffect } from "react";
import {
  XMarkIcon,
  CloudArrowUpIcon,
  DocumentIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";

export default function DocumentUploadModal({
  isOpen,
  onClose,
  onUpload,
  onEdit,
  selectedDocument,
  uploading = false,
}) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  const supportedTypes = [
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ];

  const supportedExtensions = [".pdf", ".txt", ".docx"];

  useEffect(() => {
    if (selectedDocument) {
      setTitle(selectedDocument?.extra_data?.title || "");
      setDescription(selectedDocument?.extra_data?.description || "");
      setSelectedFile(null); // Clear selected file when editing
    } else {
      setTitle("");
      setDescription("");
      setSelectedFile(null);
    }
    setError("");
  }, [selectedDocument, isOpen]);

  const handleFileSelect = (file) => {
    setError("");

    if (!supportedTypes.includes(file.type)) {
      setError(
        "Unsupported file type. Only PDF, TXT, and DOCX files are allowed."
      );
      return;
    }

    // Auto-generate title from filename if not set
    if (!title) {
      const nameWithoutExt = file.name.replace(/\.[^/.]+$/, "");
      setTitle(nameWithoutExt);
    }

    setSelectedFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleFileInputChange = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedFile) {
      setError("Please select a file to upload.");
      return;
    }

    if (!title.trim()) {
      setError("Please enter a title for this document.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("title", title.trim());
    if (description.trim()) {
      formData.append("description", description.trim());
    }

    try {
      await onUpload(formData);
      handleClose();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to upload file. Please try again."
      );
    }
  };

  const handleEdit = async (e) => {
    e.preventDefault();

    if (!title.trim()) {
      setError("Please enter a title for this document.");
      return;
    }

    const formData = new FormData();
    formData.append("title", title.trim());
    if (description.trim()) {
      formData.append("description", description.trim());
    }

    try {
      await onEdit(formData, selectedDocument.id);
      handleClose();
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to save changes. Please try again."
      );
    }
  }

  const handleClose = () => {
    if (!uploading) {
      setSelectedFile(null);
      setTitle("");
      setDescription("");
      setError("");
      setDragActive(false);
      onClose();
    }
  };

  const formatFileSize = (bytes) => {
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            {selectedDocument ? "Edit" : "Upload"} Document
          </h2>
          <button
            onClick={handleClose}
            disabled={uploading}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={selectedDocument ? handleEdit : handleSubmit} className="p-6 space-y-6">
          {/* File Drop Zone */}
          {!selectedDocument ?
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700">
                Document File *
              </label>
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragActive
                    ? "border-blue-400 bg-blue-50"
                    : selectedFile
                      ? "border-green-400 bg-green-50"
                      : "border-gray-300 hover:border-gray-400"
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                {selectedFile ? (
                  <div className="space-y-2">
                    <DocumentIcon className="w-12 h-12 text-green-600 mx-auto" />
                    <div className="text-sm font-semibold text-gray-900">
                      {selectedFile.name}
                    </div>
                    <div className="text-xs text-gray-500">
                      {formatFileSize(selectedFile.size)}
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelectedFile(null)}
                      className="text-sm text-red-600 hover:text-red-800 underline"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <CloudArrowUpIcon className="w-12 h-12 text-gray-400 mx-auto" />
                    <div className="space-y-2">
                      <div className="text-lg font-semibold text-gray-900">
                        Drop your file here, or{" "}
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="text-blue-600 hover:text-blue-800 underline cursor-pointer"
                        >
                          browse
                        </button>
                      </div>
                      <div className="text-sm text-gray-500">
                        Supports: {supportedExtensions.join(", ")}
                      </div>
                      <div className="text-xs text-gray-400">
                        Maximum file size: 50MB
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={supportedExtensions.join(",")}
                onChange={handleFileInputChange}
                className="hidden"
                disabled={uploading}
              />
            </div> : ""
          }

          {/* Title Input */}
          <div className="space-y-2">
            <label
              htmlFor="title"
              className="block text-sm font-semibold text-gray-700"
            >
              Title *
            </label>
            <input
              type="text"
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter a descriptive title for this document"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              disabled={uploading}
              required
            />
          </div>

          {/* Description Input */}
          <div className="space-y-2">
            <label
              htmlFor="description"
              className="block text-sm font-semibold text-gray-700"
            >
              Description (Optional)
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the content of this document to help with AI processing"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              disabled={uploading}
            />
          </div>

          {/* Error Message */}
          {error && (
            <div className="flex items-center space-x-2 text-red-600 bg-red-50 p-3 rounded-md">
              <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={uploading}
              className="px-4 py-2 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={selectedDocument ? false : !selectedFile || !title.trim() || uploading}
              className="px-6 py-2 text-sm font-semibold text-white bg-blue-600 border border-transparent rounded-md shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {uploading && (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
              )}
              {uploading ? selectedDocument ? "Saving" :"Uploading..." : selectedDocument ? "Save" : "Upload Document"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
