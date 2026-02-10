// UserStats types and interfaces
export interface UserStats {
  id: number;
  farmersReachedWeek: number;
  farmersReachedMonth: number;
  farmersReachedAll: number;
  conversationsResolvedWeek: number;
  conversationsResolvedMonth: number;
  conversationsResolvedAll: number;
  messagesSentWeek: number;
  messagesSentMonth: number;
  messagesSentAll: number;
  updatedAt: string;
}

// API response shape from the backend
export interface UserStatsApiResponse {
  farmers_reached: {
    this_week: number;
    this_month: number;
    all_time: number;
  };
  conversations_resolved: {
    this_week: number;
    this_month: number;
    all_time: number;
  };
  messages_sent: {
    this_week: number;
    this_month: number;
    all_time: number;
  };
}

export interface CreateUserStatsData {
  farmersReachedWeek: number;
  farmersReachedMonth: number;
  farmersReachedAll: number;
  conversationsResolvedWeek: number;
  conversationsResolvedMonth: number;
  conversationsResolvedAll: number;
  messagesSentWeek: number;
  messagesSentMonth: number;
  messagesSentAll: number;
}
