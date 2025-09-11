"use client";

import { ArrowPathIcon, EllipsisVerticalIcon } from "@heroicons/react/24/outline";

export default function DataTable({
  columns,
  data,
  loading,
  emptyStateIcon: EmptyIcon,
  emptyStateTitle,
  emptyStateMessage,
  renderRow,
  className = ""
}) {
  if (loading) {
    return (
      <div className="p-8 text-center animate-fade-in">
        <div className="relative mx-auto mb-4">
          <ArrowPathIcon className="animate-spin h-12 w-12 text-primary-600 mx-auto" />
          <div className="absolute inset-0 rounded-[5px] bg-gradient-primary opacity-20 blur-lg animate-pulse"></div>
        </div>
        <p className="text-secondary-700 font-medium">Loading data...</p>
        <p className="text-secondary-500 text-sm mt-1">Please wait while we fetch the data</p>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="p-8 text-center">
        {EmptyIcon && <EmptyIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />}
        <h3 className="text-lg font-medium text-gray-900">{emptyStateTitle}</h3>
        <p className="mt-1 text-gray-500">{emptyStateMessage}</p>
      </div>
    );
  }

  return (
    <div className={`overflow-hidden rounded-[5px] bg-white shadow-sm ${className}`}>
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gradient-to-r from-secondary-50 to-secondary-100">
          <tr>
            {columns.map((column, index) => (
              <th
                key={index}
                className={`px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider ${
                  column.align === 'right' ? 'text-right' : ''
                }`}
              >
                <div className={`flex items-center ${column.align === 'right' ? 'justify-end' : ''}`}>
                  {column.icon && <column.icon className="w-4 h-4 mr-2 text-secondary-500" />}
                  {column.title}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {data.map((item, index) => (
            <tr
              key={item.id || index}
              className="hover:bg-primary-50/50 transition-all duration-200 group animate-fade-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {renderRow(item, index)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}