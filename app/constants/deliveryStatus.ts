// Twilio Delivery Status constants
// These match the backend DeliveryStatus enum values
export enum DeliveryStatus {
  PENDING = "PENDING", // Initial state, not sent yet
  QUEUED = "QUEUED", // Twilio accepted, queuing
  SENDING = "SENDING", // Twilio sending to WhatsApp
  SENT = "SENT", // Sent to WhatsApp servers
  DELIVERED = "DELIVERED", // Delivered to device
  READ = "READ", // Customer read (if callbacks enabled)
  FAILED = "FAILED", // Permanent failure
  UNDELIVERED = "UNDELIVERED", // Temporary failure/expired
}

// Helper function to check if delivery failed
export const isDeliveryFailed = (status: string): boolean => {
  return (
    status === DeliveryStatus.FAILED || status === DeliveryStatus.UNDELIVERED
  );
};

// Helper function to check if delivery succeeded
export const isDeliverySuccessful = (status: string): boolean => {
  return status === DeliveryStatus.DELIVERED || status === DeliveryStatus.READ;
};
