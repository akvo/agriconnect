"use client";

import { useState, useEffect, useRef } from "react";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import {
  countries,
  DEFAULT_COUNTRY,
  parsePhoneNumber,
  formatPhoneNumber,
} from "../../lib/countryData";

export default function PhoneInput({
  value,
  onChange,
  name = "phone_number",
  id = "phone_number",
  required = false,
  disabled = false,
  placeholder = "712345678",
}) {
  const [selectedCountry, setSelectedCountry] = useState(DEFAULT_COUNTRY);
  const [localNumber, setLocalNumber] = useState("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Parse initial value on mount only
  useEffect(() => {
    if (value) {
      const { country, localNumber: parsed } = parsePhoneNumber(value);
      setSelectedCountry(country);
      setLocalNumber(parsed);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
        setSearchTerm("");
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleCountrySelect = (country) => {
    setSelectedCountry(country);
    setIsDropdownOpen(false);
    setSearchTerm("");

    // Update the full phone number
    const fullNumber = formatPhoneNumber(country, localNumber);
    onChange({
      target: {
        name,
        value: fullNumber,
      },
    });

    // Focus back on input
    inputRef.current?.focus();
  };

  const handleLocalNumberChange = (e) => {
    const newLocalNumber = e.target.value.replace(/[^\d]/g, "");
    setLocalNumber(newLocalNumber);

    // Update the full phone number
    const fullNumber = formatPhoneNumber(selectedCountry, newLocalNumber);
    onChange({
      target: {
        name,
        value: fullNumber,
      },
    });
  };

  const filteredCountries = countries.filter(
    (country) =>
      country.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      country.dialCode.includes(searchTerm) ||
      country.code.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="relative">
      <div className="flex">
        {/* Country selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => !disabled && setIsDropdownOpen(!isDropdownOpen)}
            disabled={disabled}
            className={`flex items-center px-3 py-2 bg-gray-50 border border-r-0 border-gray-300 focus:outline-none focus:ring-1 focus:ring-green-500 focus:border-green-500 ${
              disabled ? "cursor-not-allowed opacity-60" : "hover:bg-gray-100"
            }`}
            style={{ borderRadius: "5px 0 0 5px" }}
          >
            <span className="text-xl mr-1">{selectedCountry.flag}</span>
            <span className="text-sm text-gray-700 mr-1">
              {selectedCountry.dialCode}
            </span>
            {!disabled && (
              <ChevronDownIcon
                className={`w-4 h-4 text-gray-500 transition-transform ${
                  isDropdownOpen ? "rotate-180" : ""
                }`}
              />
            )}
          </button>

          {/* Dropdown */}
          {isDropdownOpen && (
            <div
              className="absolute z-50 mt-1 w-64 bg-white border border-gray-200 shadow-lg max-h-60 overflow-hidden"
              style={{ borderRadius: "5px" }}
            >
              {/* Search input */}
              <div className="p-2 border-b border-gray-200">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search country..."
                  className="w-full px-2 py-1 text-sm border border-gray-300 focus:outline-none focus:ring-1 focus:ring-green-500 focus:border-green-500"
                  style={{ borderRadius: "3px" }}
                  autoFocus
                />
              </div>

              {/* Country list */}
              <div className="max-h-48 overflow-y-auto">
                {filteredCountries.length > 0 ? (
                  filteredCountries.map((country) => (
                    <button
                      key={country.code}
                      type="button"
                      onClick={() => handleCountrySelect(country)}
                      className={`w-full flex items-center px-3 py-2 text-left hover:bg-gray-100 ${
                        selectedCountry.code === country.code
                          ? "bg-green-50"
                          : ""
                      }`}
                    >
                      <span className="text-xl mr-2">{country.flag}</span>
                      <span className="flex-1 text-sm text-gray-900">
                        {country.name}
                      </span>
                      <span className="text-sm text-gray-500">
                        {country.dialCode}
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="px-3 py-2 text-sm text-gray-500">
                    No countries found
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Phone number input */}
        <input
          ref={inputRef}
          type="tel"
          id={id}
          name={name}
          value={localNumber}
          onChange={handleLocalNumberChange}
          required={required}
          disabled={disabled}
          placeholder={placeholder}
          className={`flex-1 px-3 py-2 bg-gray-50 border border-gray-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-green-500 focus:border-green-500 ${
            disabled ? "cursor-not-allowed opacity-60" : ""
          }`}
          style={{ borderRadius: "0 5px 5px 0" }}
        />
      </div>
    </div>
  );
}
