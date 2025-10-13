export const formatTime = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(iso);
  let hours = d.getHours();
  const minutes = d.getMinutes();
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;
  const mm = minutes < 10 ? `0${minutes}` : String(minutes);
  return `${hours}:${mm} ${ampm}`;
};

export const relativeDays = (iso: string) => {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  return Math.floor(diffMs / (24 * 60 * 60 * 1000));
};

export const formatResolved = (iso?: string | null) => {
  if (!iso) return null;
  const diffDays = relativeDays(iso as string);
  const timeStr = formatTime(iso as string);
  if (diffDays === 0) return `Today at ${timeStr}`;
  if (diffDays === 1) return `Yesterday at ${timeStr}`;
  return `${diffDays} days ago`;
};

export const formatDateLabel = (rawDate: string) => {
  // rawDate is from toDateString() or a fallback string; try to create Date
  const dt = new Date(rawDate);
  if (!isNaN(dt.getTime())) {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    if (dt.toDateString() === today.toDateString()) return "Today";
    if (dt.toDateString() === yesterday.toDateString()) return "Yesterday";
    // format as "October 8, 2025"
    const monthNames = [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ];
    return `${monthNames[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`;
  }
  return rawDate;
};

export const formatMessageTimestamp = (iso: string) => {
  const d = new Date(iso);
  if (isNaN(d.getTime())) {
    return iso; // Return original if invalid
  }

  const month = d.getMonth() + 1;
  const day = d.getDate();
  const year = d.getFullYear();
  let hours = d.getHours();
  const minutes = d.getMinutes();
  const seconds = d.getSeconds();
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12 || 12;

  const mm = minutes < 10 ? `0${minutes}` : String(minutes);
  const ss = seconds < 10 ? `0${seconds}` : String(seconds);

  return `${month}/${day}/${year}, ${hours}:${mm}:${ss} ${ampm}`;
};
