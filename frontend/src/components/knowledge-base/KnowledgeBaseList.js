"use client";

import {
  CalendarIcon,
  PencilIcon,
  TrashIcon,
  EllipsisVerticalIcon,
  CircleStackIcon,
  ArrowPathIcon
} from "@heroicons/react/24/outline";

export default function KnowledgeBaseList({
  knowledgeBases,
  loading,
  onEditKnowledgeBase,
  onDeleteKnowledgeBase,
}) {
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

  if (loading) {
    return (
      <div className="p-8 text-center animate-fade-in">
        <div className="relative mx-auto mb-4">
          <ArrowPathIcon className="animate-spin h-12 w-12 text-primary-600 mx-auto" />
          <div className="absolute inset-0 rounded-[5px] bg-gradient-primary opacity-20 blur-lg animate-pulse"></div>
        </div>
        <p className="text-secondary-700 font-medium">Loading knowledge base...</p>
        <p className="text-secondary-500 text-sm mt-1">
          Please wait while we fetch the knowledge base data
        </p>
      </div>
    );
  }

  if (knowledgeBases.length === 0) {
    return (
      <div className="p-8 text-center">
        <CircleStackIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900">No knowledge bases found</h3>
        <p className="mt-1 text-gray-500">
          Try adjusting your search criteria or create a new knowledge base.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[5px] bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gradient-to-r from-secondary-50 to-secondary-100">
          <tr>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <CircleStackIcon className="w-4 h-4 mr-2 text-secondary-500" />
                Knowledge Base
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <CalendarIcon className="w-4 h-4 mr-2 text-secondary-500" />
                Created
              </div>
            </th>
            <th className="px-8 py-5 text-right text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center justify-end">
                <EllipsisVerticalIcon className="w-4 h-4 mr-2 text-secondary-500" />
                Actions
              </div>
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {knowledgeBases.map((kb, index) => (
            <tr
              key={kb.id}
              className="hover:bg-primary-50/50 transition-all duration-200 group animate-fade-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <td className="px-8 py-6 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="ml-4">
                    <div className="text-base font-bold text-secondary-900">
                      {kb.title}
                    </div>
                    <div className="text-sm text-secondary-100 font-normal flex items-center">
                      {kb.description}
                    </div>
                  </div>
                </div>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <div className="text-sm text-secondary-600">
                  {formatDate(kb.created_at)}
                </div>
              </td>
              <td className="px-8 py-6 whitespace-nowrap text-right">
                <div className="flex items-center justify-end space-x-3">
                  <button
                    onClick={() => onEditKnowledgeBase(kb.id)}
                    className="bg-[#3b82f6] hover:bg-[#2563eb] text-white px-4 py-2 rounded-[5px] text-xs font-semibold transition-all duration-200    flex items-center cursor-pointer"
                  >
                    <PencilIcon className="w-4 h-4 mr-1" />
                    Edit
                  </button>
                  <button
                    onClick={() => onDeleteKnowledgeBase(kb)}
                    className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-[5px] text-xs font-semibold transition-all duration-200    flex items-center cursor-pointer"
                  >
                    <TrashIcon className="w-4 h-4 mr-1" />
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
