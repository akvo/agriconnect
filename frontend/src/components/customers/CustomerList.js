"use client";

import {
  UserIcon,
  PhoneIcon,
  GlobeAltIcon,
  ClockIcon,
  PencilIcon,
  TrashIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";
import DataTable from "../common/DataTable";
import { useAuth } from "@/contexts/AuthContext";

export default function CustomerList({
  customers,
  loading,
  onEditCustomer,
  onDeleteCustomer,
}) {
  const { user } = useAuth();

  const columns = [
    {
      title: "Customer",
      icon: UserIcon,
    },
    {
      title: "Language",
      icon: GlobeAltIcon,
    },
    {
      title: "Created",
      icon: ClockIcon,
    },
    {
      title: "Actions",
      align: "right",
    },
  ];

  const getLanguageLabel = (language) => {
    switch (language) {
      case "en":
        return "English";
      case "sw":
        return "Swahili";
      default:
        return language;
    }
  };

  const getLanguageBadgeColor = (language) => {
    switch (language) {
      case "en":
        return "bg-blue-100 text-blue-800";
      case "sw":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const renderRow = (customer, index) => (
    <>
      <td className="px-8 py-6 whitespace-nowrap">
        <div className="flex items-center">
          <div className="ml-4">
            <div className="text-base font-bold text-secondary-900">
              {customer.full_name || "Unnamed Customer"}
            </div>
            <div className="text-sm font-semibold text-secondary-900 flex items-center">
              <PhoneIcon className="w-4 h-4 mr-2 text-secondary-400" />
              {customer.phone_number}
            </div>
          </div>
        </div>
      </td>
      <td className="px-8 py-6 whitespace-nowrap">
        {customer.language ? (
          <span
            className={`inline-flex items-center px-4 py-2 rounded-[5px] text-sm font-bold ${getLanguageBadgeColor(customer.language)}`}
          >
            <GlobeAltIcon className="w-4 h-4 mr-2 flex-shrink-0" />
            <span className="leading-none">
              {getLanguageLabel(customer.language)}
            </span>
          </span>
        ) : (
          <span className="text-secondary-500 text-sm">N/A</span>
        )}
      </td>
      <td className="px-8 py-6 whitespace-nowrap">
        <div className="text-sm text-secondary-600">
          {formatDate(customer.created_at)}
        </div>
        {customer.updated_at && customer.updated_at !== customer.created_at && (
          <div className="text-xs text-secondary-500">
            Updated: {formatDate(customer.updated_at)}
          </div>
        )}
      </td>
      <td className="px-8 py-6 whitespace-nowrap text-right">
        <div className="flex items-center justify-end space-x-3">
          <button
            onClick={() => onEditCustomer(customer)}
            className="bg-[#3b82f6] hover:bg-[#2563eb] text-white px-4 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
          >
            <PencilIcon className="w-4 h-4 mr-1" />
            Edit
          </button>
          {user?.user_type === "admin" && (
            <button
              onClick={() => onDeleteCustomer(customer)}
              className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
            >
              <TrashIcon className="w-4 h-4 mr-1" />
              Delete
            </button>
          )}
        </div>
      </td>
    </>
  );

  return (
    <DataTable
      columns={columns}
      data={customers}
      loading={loading}
      emptyStateIcon={UsersIcon}
      emptyStateTitle="No customers found"
      emptyStateMessage="Try adjusting your search criteria or create a new customer."
      renderRow={renderRow}
    />
  );
}
