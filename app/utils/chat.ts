export interface Message {
  id: number;
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
    if (!groups[key]) groups[key] = [];
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

const generateDummyMessages = (count = 100): Message[] => {
  const msgs: Message[] = [];
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth();

  // helper to push a message for a given date and minute offset
  let id = 1;
  function pushMsg(dayOffset: number, minuteOffset: number, isUser: boolean) {
    const dt = new Date(currentYear, currentMonth, today.getDate() - dayOffset);
    dt.setMinutes(dt.getMinutes() - minuteOffset);
    msgs.push({
      id: id++,
      name: isUser ? "You" : "Customer",
      text: isUser
        ? `User message #${id - 1} — sample text to simulate chat content.`
        : `Customer message #${id - 1} — ask question.`,
      sender: isUser ? "user" : "customer",
      timestamp: dt.toLocaleString(),
    });
  }

  // Create messages for: today (30 msgs), yesterday (30 msgs), and previous days within current month (remaining)
  const todayCount = Math.min(30, count);
  const yesterdayCount = Math.min(30, Math.max(0, count - todayCount));
  const remaining = Math.max(0, count - todayCount - yesterdayCount);

  // today messages
  for (let i = 0; i < todayCount; i++) {
    pushMsg(0, i * 5, i % 2 === 0);
  }

  // yesterday messages
  for (let i = 0; i < yesterdayCount; i++) {
    pushMsg(1, i * 7, i % 2 === 0);
  }

  // distribute remaining across previous days of the month (starting 2 days ago)
  let day = 2;
  let placed = 0;
  while (placed < remaining) {
    const perDay = 6; // up to 6 messages per older day
    for (let i = 0; i < perDay && placed < remaining; i++) {
      pushMsg(day, i * 10, placed % 2 === 0);
      placed++;
    }
    day++;
    // stop if we reach beginning of month
    if (day > 28) break;
  }

  return msgs;
};

export default {
  groupMessagesByDate,
  generateDummyMessages,
};
