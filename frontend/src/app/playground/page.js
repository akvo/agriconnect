"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import api from "../../lib/api";
import HeaderNav from "../../components/HeaderNav";
import {
  PaperAirplaneIcon,
  ArrowPathIcon,
  BeakerIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { io } from "socket.io-client";

export default function PlaygroundPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  // State
  const [activeService, setActiveService] = useState(null);
  const [defaultPrompt, setDefaultPrompt] = useState("");
  const [customPrompt, setCustomPrompt] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [socket, setSocket] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef(null);

  // Redirect non-admins
  useEffect(() => {
    if (user && user.user_type !== "admin") {
      router.push("/");
      return;
    }
  }, [user, router]);

  // Fetch active service and default prompt
  useEffect(() => {
    if (!authLoading && user?.user_type === "admin") {
      fetchServiceInfo();
    }
  }, [authLoading, user]);

  const fetchServiceInfo = async () => {
    try {
      setIsLoading(true);
      const [serviceRes, promptRes] = await Promise.all([
        api.get("/admin/playground/active-service"),
        api.get("/admin/playground/default-prompt"),
      ]);
      setActiveService(serviceRes.data);
      setDefaultPrompt(promptRes.data.default_prompt || "");
    } catch (err) {
      console.error("Error fetching service info:", err);
      if (err.response?.status !== 404) {
        alert("Failed to fetch service configuration");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // WebSocket setup
  useEffect(() => {
    if (!currentSessionId || !user) return;

    const token = api.token;

    // Determine WebSocket URL based on environment
    // Local dev (no nginx): Backend runs on port 8000
    // Production (with nginx): Backend is proxied through same origin
    const isLocalDev = window.location.port === "3000";
    const wsUrl = isLocalDev ? "http://localhost:8000" : window.location.origin;

    const newSocket = io(wsUrl, {
      auth: { token },
      transports: ["websocket"],
      path: "/ws/socket.io/",
    });

    newSocket.on("connect", () => {
      setIsConnected(true);

      // Join playground session room
      if (currentSessionId) {
        newSocket.emit("join_playground", { session_id: currentSessionId });
      }
    });

    newSocket.on("disconnect", () => {
      setIsConnected(false);
    });

    newSocket.on("playground_response", (data) => {
      // Use functional update to avoid stale state
      setMessages((prevMessages) => {
        const updated = prevMessages.map((msg) =>
          msg.id === data.message_id
            ? {
                ...msg,
                content: data.content,
                status: "completed",
                response_time_ms: data.response_time_ms,
              }
            : msg
        );
        return updated;
      });
    });

    setSocket(newSocket);

    return () => {
      newSocket.close();
    };
  }, [currentSessionId, user]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isSending) return;

    try {
      setIsSending(true);
      const response = await api.post("/admin/playground/chat", {
        message: inputMessage,
        session_id: currentSessionId,
        custom_prompt: customPrompt || null,
      });

      // Add user message and assistant pending message
      const newMessages = [
        ...messages,
        response.data.user_message,
        response.data.assistant_message,
      ];

      console.log("=== SENDING MESSAGE ===");
      console.log("Current messages count:", messages.length);
      console.log("New messages count:", newMessages.length);
      console.log("User message ID:", response.data.user_message.id);
      console.log("Assistant message ID:", response.data.assistant_message.id);
      console.log("New messages:", newMessages);

      setMessages(newMessages);
      setCurrentSessionId(response.data.session_id);
      setInputMessage("");
    } catch (err) {
      console.error("Error sending message:", err);
      alert(err.response?.data?.detail || "Failed to send message");
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleSendMessage();
    }
  };

  const handleClearSession = () => {
    if (
      messages.length > 0 &&
      !confirm("Clear current conversation? This cannot be undone.")
    ) {
      return;
    }
    setMessages([]);
    setCurrentSessionId(null);
    setCustomPrompt("");
  };

  const handleResetPrompt = () => {
    setCustomPrompt(defaultPrompt);
  };

  const handleClearPrompt = () => {
    setCustomPrompt("");
  };

  // Don't render if not admin
  if (user && user.user_type !== "admin") {
    return null;
  }

  if (authLoading || isLoading) {
    return (
      <div className="min-h-screen bg-gradient-brand flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <ArrowPathIcon className="animate-spin h-16 w-16 text-primary-600 mx-auto mb-4" />
          <p className="text-secondary-700 font-medium">
            Loading playground...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-brand">
      <HeaderNav
        breadcrumbs={[
          { label: "Dashboard", path: "/" },
          { label: "Chat Playground" },
        ]}
      />

      <main className="max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Panel - Service Info & Prompt Override */}
          <div className="lg:col-span-3">
            <div
              className="bg-white shadow-lg p-6 mb-6"
              style={{ borderRadius: "5px" }}
            >
              <div className="flex items-center mb-4">
                <BeakerIcon className="h-6 w-6 text-primary-600 mr-2" />
                <h2 className="text-lg font-semibold">Active Service</h2>
              </div>

              {activeService ? (
                <div className="space-y-3">
                  <div>
                    <span className="text-sm text-gray-600">Service:</span>
                    <p className="font-medium">{activeService.service_name}</p>
                  </div>
                  <div>
                    <span className="text-sm text-gray-600">Status:</span>
                    <div className="flex items-center mt-1">
                      {activeService.is_active ? (
                        <>
                          <CheckCircleIcon className="h-5 w-5 text-green-600 mr-1" />
                          <span className="text-green-600 text-sm">Active</span>
                        </>
                      ) : (
                        <>
                          <XCircleIcon className="h-5 w-5 text-red-600 mr-1" />
                          <span className="text-red-600 text-sm">Inactive</span>
                        </>
                      )}
                    </div>
                  </div>
                  {isConnected && (
                    <div>
                      <span className="text-sm text-gray-600">WebSocket:</span>
                      <div className="flex items-center mt-1">
                        <div className="h-2 w-2 bg-green-500 rounded-full mr-2"></div>
                        <span className="text-green-600 text-sm">
                          Connected
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No active service configured
                </p>
              )}
            </div>

            <div
              className="bg-white shadow-lg p-6"
              style={{ borderRadius: "5px" }}
            >
              <h2 className="text-lg font-semibold mb-4">Custom Prompt</h2>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Override the default prompt here..."
                className="w-full h-48 p-3 border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none text-sm"
                style={{ borderRadius: "5px" }}
              />
              <div className="text-xs text-gray-500 mt-2 mb-4">
                {customPrompt.length} characters
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={handleResetPrompt}
                  disabled={!defaultPrompt}
                  className="flex-1 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ borderRadius: "5px" }}
                >
                  Use Default
                </button>
                <button
                  onClick={handleClearPrompt}
                  disabled={!customPrompt}
                  className="flex-1 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ borderRadius: "5px" }}
                >
                  Clear
                </button>
              </div>
            </div>
          </div>

          {/* Center Panel - Chat Interface */}
          <div className="lg:col-span-9">
            <div
              className="bg-white shadow-lg flex flex-col"
              style={{ borderRadius: "5px", height: "calc(100vh - 200px)" }}
            >
              {/* Header */}
              <div className="border-b border-gray-200 p-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Chat Playground</h2>
                  <p className="text-sm text-gray-600">
                    Test AI responses with custom prompts
                  </p>
                </div>
                <button
                  onClick={handleClearSession}
                  className="flex items-center px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                  style={{ borderRadius: "5px" }}
                >
                  <TrashIcon className="h-4 w-4 mr-1" />
                  Clear
                </button>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.length === 0 ? (
                  <div className="text-center text-gray-500 mt-12">
                    <BeakerIcon className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                    <p className="text-lg font-medium">Start a conversation</p>
                    <p className="text-sm mt-2">
                      Send a message to test the AI service
                    </p>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isUser = msg.role === "user" || msg.role === "USER";
                    return (
                      <div
                        key={msg.id}
                        className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-[70%] p-4 ${
                            isUser
                              ? "text-white"
                              : msg.status === "pending"
                                ? "bg-gray-100 text-gray-600"
                                : "bg-gray-100 text-gray-800"
                          }`}
                          style={{
                            borderRadius: "12px",
                            backgroundColor: isUser ? "#2563EB" : undefined,
                          }}
                        >
                          {msg.status === "pending" ? (
                            <div className="flex items-center">
                              <ArrowPathIcon className="animate-spin h-4 w-4 mr-2" />
                              <span className="text-sm">Thinking...</span>
                            </div>
                          ) : (
                            <div className="whitespace-pre-wrap">
                              {msg.content}
                            </div>
                          )}
                          <div className="flex items-center justify-between mt-2 text-xs opacity-75">
                            <span>
                              {new Date(msg.created_at).toLocaleTimeString()}
                            </span>
                            {msg.response_time_ms && (
                              <span className="flex items-center ml-4">
                                <ClockIcon className="h-3 w-3 mr-1" />
                                {(msg.response_time_ms / 1000).toFixed(2)}s
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="border-t border-gray-200 p-4">
                <div className="flex space-x-2">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Type your message... (Click Send or press Ctrl/Cmd + Enter)"
                    disabled={isSending || !activeService}
                    className="flex-1 p-3 border border-gray-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none text-gray-900 placeholder-gray-400"
                    style={{ borderRadius: "5px" }}
                    rows={3}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={
                      isSending || !inputMessage.trim() || !activeService
                    }
                    className="px-6 text-white disabled:cursor-not-allowed flex items-center justify-center gap-2 font-medium transition-all duration-200 hover:shadow-lg hover:scale-105 active:scale-95 cursor-pointer"
                    style={{
                      borderRadius: "5px",
                      backgroundColor:
                        isSending || !inputMessage.trim() || !activeService
                          ? "#9CA3AF"
                          : "#2563EB",
                    }}
                  >
                    {isSending ? (
                      <>
                        <ArrowPathIcon className="h-5 w-5 animate-spin" />
                        <span>Sending...</span>
                      </>
                    ) : (
                      <>
                        <PaperAirplaneIcon className="h-5 w-5" />
                        <span>Send</span>
                      </>
                    )}
                  </button>
                </div>
                {customPrompt && (
                  <div className="mt-2 text-xs text-primary-600 flex items-center">
                    <CheckCircleIcon className="h-4 w-4 mr-1" />
                    Custom prompt active
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
