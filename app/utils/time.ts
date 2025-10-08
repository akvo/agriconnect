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
    // format dd/mm/yyyy
    const pad2 = (n: number) => (n < 10 ? `0${n}` : `${n}`);
    return `${pad2(dt.getDate())}/${pad2(
      dt.getMonth() + 1,
    )}/${dt.getFullYear()}`;
  }
  return rawDate;
};
