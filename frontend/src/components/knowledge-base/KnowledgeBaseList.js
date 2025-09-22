"use client";

import {
  DocumentIcon,
  CalendarIcon,
  EyeIcon,
  PencilIcon,
  TrashIcon,
  CloudArrowUpIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import DataTable from "../common/DataTable";

export default function KnowledgeBaseList({
  knowledgeBases,
  loading,
  onViewKnowledgeBase,
  onEditKnowledgeBase,
  onDeleteKnowledgeBase,
}) {
  const columns = [
    {
      title: "Document",
      icon: DocumentIcon,
    },
    {
      title: "Status",
      icon: ClockIcon,
    },
    {
      title: "Created",
      icon: CalendarIcon,
    },
    {
      title: "Actions",
      align: "right",
    },
  ];

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case "done":
        return {
          color: "bg-green-100 text-green-800",
          icon: CheckCircleIcon,
          text: "Completed",
        };
      case "failed":
        return {
          color: "bg-red-100 text-red-800",
          icon: ExclamationTriangleIcon,
          text: "Failed",
        };
      case "timeout":
        return {
          color: "bg-orange-100 text-orange-800",
          icon: ExclamationTriangleIcon,
          text: "Timeout",
        };
      case "queued":
      default:
        return {
          color: "bg-blue-100 text-blue-800",
          icon: ClockIcon,
          text: "Processing",
        };
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "Unknown size";
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  const getFileTypeIcon = (contentType) => {
    if (contentType?.includes("pdf")) return "📄";
    if (contentType?.includes("word")) return "📝";
    if (contentType?.includes("text")) return "📃";
    return "📄";
  };

  const renderRow = (kb, index) => {
    const statusInfo = getStatusBadge(kb.status);
    const StatusIcon = statusInfo.icon;

    return (
      <>
        <td className="px-8 py-6 whitespace-nowrap">
          <div className="flex items-center">
            <div className="text-2xl mr-3">
              {getFileTypeIcon(kb.extra_data?.content_type)}
            </div>
            <div className="ml-2">
              <div className="text-base font-bold text-secondary-900">
                {kb.title}
              </div>
              <div className="text-sm text-secondary-600">{kb.filename}</div>
              {kb.description && (
                <div className="text-xs text-secondary-500 mt-1 max-w-xs truncate">
                  {kb.description}
                </div>
              )}
              {kb.extra_data?.size && (
                <div className="text-xs text-secondary-400 mt-1">
                  {formatFileSize(kb.extra_data.size)}
                </div>
              )}
            </div>
          </div>
        </td>
        <td className="px-8 py-6 whitespace-nowrap">
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ${statusInfo.color}`}
          >
            <StatusIcon className="w-4 h-4 mr-2 flex-shrink-0" />
            <span className="leading-none">{statusInfo.text}</span>
          </span>
        </td>
        <td className="px-8 py-6 whitespace-nowrap">
          <div className="text-sm text-secondary-600">
            {formatDate(kb.created_at)}
          </div>
          {kb.updated_at && kb.updated_at !== kb.created_at && (
            <div className="text-xs text-secondary-500">
              Updated: {formatDate(kb.updated_at)}
            </div>
          )}
        </td>
        <td className="px-8 py-6 whitespace-nowrap text-right">
          <div className="flex items-center justify-end space-x-2">
            <button
              onClick={() => onViewKnowledgeBase(kb)}
              className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
            >
              <EyeIcon className="w-4 h-4 mr-1" />
              View
            </button>
            <button
              onClick={() => onEditKnowledgeBase(kb)}
              className="bg-[#3b82f6] hover:bg-[#2563eb] text-white px-3 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
            >
              <PencilIcon className="w-4 h-4 mr-1" />
              Edit
            </button>
            <button
              onClick={() => onDeleteKnowledgeBase(kb)}
              className="bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
            >
              <TrashIcon className="w-4 h-4 mr-1" />
              Delete
            </button>
          </div>
        </td>
      </>
    );
  };

  return (
    <DataTable
      columns={columns}
      data={knowledgeBases}
      loading={loading}
      emptyStateIcon={CloudArrowUpIcon}
      emptyStateTitle="No knowledge base documents found"
      emptyStateMessage="Upload your first document to get started with AI-powered assistance."
      renderRow={renderRow}
    />
  );
}
