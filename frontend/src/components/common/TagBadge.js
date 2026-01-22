"use client";

import {
  BeakerIcon,
  BugAntIcon,
  SunIcon,
  ArchiveBoxIcon,
  CloudIcon,
  QuestionMarkCircleIcon,
} from "@heroicons/react/24/outline";

// Tag configuration with colors and icons
const TAG_CONFIG = {
  fertilizer: {
    label: "Fertilizer",
    bgColor: "bg-yellow-100",
    textColor: "text-yellow-800",
    borderColor: "border-yellow-300",
    icon: BeakerIcon,
  },
  pest: {
    label: "Pest",
    bgColor: "bg-red-100",
    textColor: "text-red-800",
    borderColor: "border-red-300",
    icon: BugAntIcon,
  },
  pre_planting: {
    label: "Pre-Planting",
    bgColor: "bg-blue-100",
    textColor: "text-blue-800",
    borderColor: "border-blue-300",
    icon: SunIcon,
  },
  harvesting: {
    label: "Harvesting",
    bgColor: "bg-green-100",
    textColor: "text-green-800",
    borderColor: "border-green-300",
    icon: ArchiveBoxIcon,
  },
  irrigation: {
    label: "Irrigation",
    bgColor: "bg-cyan-100",
    textColor: "text-cyan-800",
    borderColor: "border-cyan-300",
    icon: CloudIcon,
  },
  other: {
    label: "Other",
    bgColor: "bg-gray-100",
    textColor: "text-gray-800",
    borderColor: "border-gray-300",
    icon: QuestionMarkCircleIcon,
  },
};

export default function TagBadge({ tag, showIcon = true, size = "sm" }) {
  if (!tag) return null;

  const config = TAG_CONFIG[tag.toLowerCase()] || TAG_CONFIG.other;
  const Icon = config.icon;

  const sizeClasses = {
    xs: "px-2 py-0.5 text-xs",
    sm: "px-2.5 py-1 text-sm",
    md: "px-3 py-1.5 text-base",
  };

  const iconSizes = {
    xs: "w-3 h-3",
    sm: "w-4 h-4",
    md: "w-5 h-5",
  };

  return (
    <span
      className={`inline-flex items-center font-medium border ${config.bgColor} ${config.textColor} ${config.borderColor} ${sizeClasses[size]}`}
      style={{ borderRadius: "5px" }}
    >
      {showIcon && <Icon className={`${iconSizes[size]} mr-1.5`} />}
      {config.label}
    </span>
  );
}

// Export tag config for use in charts/analytics
export { TAG_CONFIG };
