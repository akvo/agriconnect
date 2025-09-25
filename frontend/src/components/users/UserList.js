"use client";

import {
  UsersIcon,
  UserIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  EllipsisVerticalIcon,
  PencilIcon,
  TrashIcon,
  Cog6ToothIcon,
  BookOpenIcon,
  ArrowPathIcon,
  MapPinIcon,
} from "@heroicons/react/24/outline";

export default function UserList({
  users,
  loading,
  onEditUser,
  onDeleteUser,
  onResendInvitation,
  currentUser,
}) {
  const getUserTypeLabel = (userType) => {
    switch (userType) {
      case "admin":
        return "Administrator";
      case "eo":
        return "Extension Officer";
      default:
        return userType;
    }
  };

  const getUserTypeBadgeColor = (userType) => {
    switch (userType) {
      case "admin":
        return "bg-purple-100 text-purple-800";
      case "eo":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center animate-fade-in">
        <div className="relative mx-auto mb-4">
          <ArrowPathIcon className="animate-spin h-12 w-12 text-primary-600 mx-auto" />
          <div className="absolute inset-0 rounded-[5px] bg-gradient-primary opacity-20 blur-lg animate-pulse"></div>
        </div>
        <p className="text-secondary-700 font-medium">Loading users...</p>
        <p className="text-secondary-500 text-sm mt-1">
          Please wait while we fetch the user data
        </p>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="p-8 text-center">
        <UsersIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900">No users found</h3>
        <p className="mt-1 text-gray-500">
          Try adjusting your search criteria or create a new user.
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
                <UserIcon className="w-4 h-4 mr-2 text-secondary-500" />
                User
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <ClipboardDocumentListIcon className="w-4 h-4 mr-2 text-secondary-500" />
                Type
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <CheckCircleIcon className="w-4 h-4 mr-2 text-secondary-500" />
                Status
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
          {users.map((user, index) => (
            <tr
              key={user.id}
              className="hover:bg-primary-50/50 transition-all duration-200 group animate-fade-in"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <td className="px-8 py-6 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="ml-4">
                    <div className="text-base font-bold text-secondary-900">
                      {user.full_name}
                    </div>
                    <div className="text-sm text-secondary-500 font-medium flex items-center">
                      {user.email}
                    </div>
                    {user.administrative_location?.full_path && (
                      <div className="text-xs text-gray-400 mt-1 flex items-center">
                        <MapPinIcon className="w-3 h-3 mr-1" />
                        {user.administrative_location.full_path}
                      </div>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <span
                  className={`inline-flex items-center px-3 py-1 text-sm font-medium ${
                    user.user_type === "admin"
                      ? "text-purple-700"
                      : "text-blue-700"
                  }`}
                >
                  {user.user_type === "admin" ? (
                    <Cog6ToothIcon className="w-4 h-4 mr-2 flex-shrink-0" />
                  ) : (
                    <BookOpenIcon className="w-4 h-4 mr-2 flex-shrink-0" />
                  )}
                  <span className="leading-none">
                    {getUserTypeLabel(user.user_type)}
                  </span>
                </span>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <span
                  className={`inline-flex items-center px-3 py-1 text-sm font-medium ${
                    user.is_active
                      ? "text-green-700"
                      : user.password_set_at
                        ? "text-red-700"
                        : "text-yellow-700"
                  }`}
                >
                  {user.is_active ? (
                    <CheckCircleIcon className="w-4 h-4 mr-2" />
                  ) : user.password_set_at ? (
                    <XCircleIcon className="w-4 h-4 mr-2" />
                  ) : (
                    <ClockIcon className="w-4 h-4 mr-2" />
                  )}
                  {user.is_active
                    ? "Active"
                    : user.password_set_at
                      ? "Inactive"
                      : "Pending"}
                </span>
              </td>
              <td className="px-8 py-6 whitespace-nowrap text-right">
                <div className="flex items-center justify-end space-x-3">
                  {!user.is_active && !user.password_set_at && (
                    <button
                      onClick={() => onResendInvitation?.(user)}
                      className="bg-[#f59e0b] hover:bg-[#d97706] text-white px-4 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200 flex items-center cursor-pointer"
                      title="Resend invitation email"
                    >
                      <ArrowPathIcon className="w-4 h-4 mr-1" />
                      Resend
                    </button>
                  )}
                  <button
                    onClick={() => onEditUser(user)}
                    className="bg-[#3b82f6] hover:bg-[#2563eb] text-white px-4 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200    flex items-center cursor-pointer"
                  >
                    <PencilIcon className="w-4 h-4 mr-1" />
                    Edit
                  </button>
                  {currentUser.id !== user.id && (
                    <button
                      onClick={() => onDeleteUser(user.id)}
                      className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-[5px] text-sm font-semibold transition-all duration-200    flex items-center cursor-pointer"
                    >
                      <TrashIcon className="w-4 h-4 mr-1" />
                      Delete
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
