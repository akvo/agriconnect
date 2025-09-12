"use client";

import { useState } from "react";
import { XMarkIcon, ExclamationTriangleIcon } from "@heroicons/react/24/outline";

export default function DeleteCustomerModal({
  customer,
  onClose,
  onDeleteConfirmed,
}) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDeleteConfirmed(customer.id);
      onClose();
    } catch (error) {
      console.error("Error deleting customer:", error);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm overflow-y-auto h-full w-full z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full mx-auto transform transition-all p-6">
        <div className="flex items-start justify-between">
            <div className="flex items-center">
              <div className="flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
              </div>
              <div className="ml-3">
                <h3 className="text-lg leading-6 font-medium text-gray-900">
                  Delete Customer
                </h3>
              </div>
            </div>
            <button
              onClick={onClose}
              className="ml-3 p-1 text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="mt-4">
            <div className="text-sm text-gray-600">
              <p className="mb-3">
                Are you sure you want to delete customer{" "}
                <span className="font-semibold text-gray-900">
                  {customer.full_name || customer.phone_number}
                </span>?
              </p>
              
              <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-4">
                <div className="flex">
                  <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mt-0.5 mr-2 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-medium text-yellow-800">
                      Warning: This action cannot be undone
                    </h4>
                    <p className="text-sm text-yellow-700 mt-1">
                      Deleting this customer will also permanently delete:
                    </p>
                    <ul className="text-sm text-yellow-700 mt-2 list-disc list-inside">
                      <li>All messages sent by or to this customer</li>
                      <li>All conversation history</li>
                      <li>Customer profile information</li>
                    </ul>
                  </div>
                </div>
              </div>

              <p className="text-sm text-gray-500">
                Customer ID: {customer.id} | Phone: {customer.phone_number}
              </p>
            </div>
          </div>

          <div className="mt-6 sm:flex sm:flex-row-reverse">
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              className={`w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white sm:ml-3 sm:w-auto sm:text-sm ${
                isDeleting
                  ? "bg-red-400 cursor-not-allowed"
                  : "bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              }`}
            >
              {isDeleting ? "Deleting..." : "Delete Customer"}
            </button>
            <button
              type="button"
              onClick={onClose}
              disabled={isDeleting}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 sm:mt-0 sm:w-auto sm:text-sm"
            >
              Cancel
            </button>
        </div>
      </div>
    </div>
  );
}