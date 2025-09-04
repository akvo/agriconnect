"use client";

export default function UserList({
  users,
  loading,
  onEditUser,
  onDeleteUser,
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
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-200 border-t-primary-600 mx-auto"></div>
          <div className="absolute inset-0 rounded-full bg-gradient-primary opacity-20 blur-lg animate-pulse"></div>
        </div>
        <p className="text-secondary-700 font-medium">Loading users...</p>
        <p className="text-secondary-500 text-sm mt-1">Please wait while we fetch the user data</p>
      </div>
    );
  }

  if (users.length === 0) {
    return (
      <div className="p-8 text-center">
        <svg
          className="h-12 w-12 text-gray-400 mx-auto mb-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1}
            d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
          />
        </svg>
        <h3 className="text-lg font-medium text-gray-900">No users found</h3>
        <p className="mt-1 text-gray-500">
          Try adjusting your search criteria or create a new user.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl shadow-brand border border-white/20 bg-white/80 backdrop-blur-md">
      <table className="min-w-full divide-y divide-secondary-100">
        <thead className="bg-gradient-to-r from-secondary-50 to-secondary-100">
          <tr>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <svg className="w-4 h-4 mr-2 text-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                </svg>
                User
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <svg className="w-4 h-4 mr-2 text-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"></path>
                </svg>
                Contact
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <svg className="w-4 h-4 mr-2 text-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5-7a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h4"></path>
                </svg>
                Type
              </div>
            </th>
            <th className="px-8 py-5 text-left text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center">
                <svg className="w-4 h-4 mr-2 text-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                Status
              </div>
            </th>
            <th className="px-8 py-5 text-right text-xs font-bold text-secondary-700 uppercase tracking-wider">
              <div className="flex items-center justify-end">
                <svg className="w-4 h-4 mr-2 text-secondary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"></path>
                </svg>
                Actions
              </div>
            </th>
          </tr>
        </thead>
        <tbody className="bg-white/60 backdrop-blur-sm divide-y divide-secondary-100">
          {users.map((user, index) => (
            <tr key={user.id} className="hover:bg-primary-50/50 transition-all duration-200 group animate-fade-in" style={{ animationDelay: `${index * 50}ms` }}>
              <td className="px-8 py-6 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="h-12 w-12 flex-shrink-0">
                    <div className="h-12 w-12 rounded-xl bg-gradient-primary shadow-md flex items-center justify-center group-hover:shadow-lg transition-all duration-200">
                      <span className="text-lg font-bold text-white">
                        {user.full_name?.charAt(0)?.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-base font-bold text-secondary-900">
                      {user.full_name}
                    </div>
                    <div className="text-sm text-secondary-500 font-medium">ID: #{user.id}</div>
                  </div>
                </div>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <div className="space-y-1">
                  <div className="text-sm font-semibold text-secondary-900 flex items-center">
                    <svg className="w-4 h-4 mr-2 text-secondary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207"></path>
                    </svg>
                    {user.email}
                  </div>
                  <div className="text-sm text-secondary-600 flex items-center">
                    <svg className="w-4 h-4 mr-2 text-secondary-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>
                    </svg>
                    {user.phone_number}
                  </div>
                </div>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <span
                  className={`inline-flex items-center px-4 py-2 rounded-xl text-sm font-bold shadow-sm ${getUserTypeBadgeColor(user.user_type)}`}
                >
                  {user.user_type === "admin" ? (
                    <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                    </svg>
                  )}
                  <span className="leading-none">{getUserTypeLabel(user.user_type)}</span>
                </span>
              </td>
              <td className="px-8 py-6 whitespace-nowrap">
                <span
                  className={`inline-flex items-center px-4 py-2 rounded-xl text-sm font-bold shadow-sm ${
                    user.is_active === "true"
                      ? "bg-primary-100 text-primary-800 border border-primary-200"
                      : "bg-red-100 text-red-800 border border-red-200"
                  }`}
                >
                  {user.is_active === "true" ? (
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                  )}
                  {user.is_active === "true" ? "Active" : "Inactive"}
                </span>
              </td>
              <td className="px-8 py-6 whitespace-nowrap text-right">
                <div className="flex items-center justify-end space-x-3">
                  <button
                    onClick={() => onEditUser(user)}
                    className="bg-[#3b82f6] hover:bg-[#2563eb] text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg flex items-center cursor-pointer"
                  >
                    <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                    </svg>
                    Edit
                  </button>
                  {currentUser.id !== user.id && (
                    <button
                      onClick={() => onDeleteUser(user.id)}
                      className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 transform hover:scale-105 shadow-md hover:shadow-lg flex items-center cursor-pointer"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                      </svg>
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
