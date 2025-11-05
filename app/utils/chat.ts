export interface Message {
  id: number;
  message_sid: string; // Twilio message SID or system-generated ID
  name: string; // sender's name
  text: string;
  sender: "user" | "customer";
  timestamp: string; // ISO string or formatted date
}

const groupMessagesByDate = (messages: Message[]) => {
  const groups: { [key: string]: Message[] } = {};
  messages.forEach((m) => {
    const dt = new Date(m.timestamp);
    const key = isNaN(dt.getTime())
      ? m.timestamp.split(" ")[0]
      : dt.toDateString();
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(m);
  });

  // Sort the date keys chronologically and sort messages within each group by timestamp
  // This ensures new messages appear in the correct chronological order
  return Object.keys(groups)
    .sort((a, b) => {
      const dateA = new Date(a);
      const dateB = new Date(b);
      // Handle invalid dates by treating them as strings
      if (isNaN(dateA.getTime()) || isNaN(dateB.getTime())) {
        return a.localeCompare(b);
      }
      return dateA.getTime() - dateB.getTime();
    })
    .map((k) => ({
      date: k,
      items: groups[k].sort((a, b) => {
        const timeA = new Date(a.timestamp);
        const timeB = new Date(b.timestamp);
        // Handle invalid timestamps by using ID as fallback
        if (isNaN(timeA.getTime()) || isNaN(timeB.getTime())) {
          return a.id - b.id;
        }
        return timeA.getTime() - timeB.getTime();
      }),
    }));
};

export default {
  groupMessagesByDate,
};
