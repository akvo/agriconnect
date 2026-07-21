"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { useRouter } from "next/navigation";
import api from "../../lib/api";
import knowledgeBaseApi from "../../lib/knowledgeBaseApi";
import HeaderNav from "../../components/HeaderNav";
import {
  PaperAirplaneIcon,
  ArrowPathIcon,
  BeakerIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  TrashIcon,
  DocumentTextIcon,
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
  const [documents, setDocuments] = useState([]);
  const [knowledgeBase, setKnowledgeBase] = useState(null);
  const [loadingDocs, setLoadingDocs] = useState(false);
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

  // Fetch documents when active knowledge base is available
  useEffect(() => {
    if (activeService?.active_knowledge_base_id) {
      fetchDocuments(activeService.active_knowledge_base_id);
    }
  }, [activeService?.active_knowledge_base_id]);

  const fetchDocuments = async (kbId) => {
    try {
      setLoadingDocs(true);
      const [kbDetails, docsResponse] = await Promise.all([
        knowledgeBaseApi.getById(kbId),
        knowledgeBaseApi.getDocumentList(kbId, 1, 100),
      ]);
      setKnowledgeBase(kbDetails);
      setDocuments(docsResponse.data || []);
    } catch (err) {
      console.error("Error fetching documents:", err);
    } finally {
      setLoadingDocs(false);
    }
  };

  // WebSocket setup
  useEffect(() => {
    if (!user) return;

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
    });

    newSocket.on("disconnect", () => {
      setIsConnected(false);
    });

    newSocket.on("playground_response", (data) => {
      // Debug: Log incoming WebSocket data
      console.log("[Playground WS] Received response:", {
        message_id: data.message_id,
        citations_count: data.citations?.length || 0,
        citations: data.citations,
      });

      // Use functional update to avoid stale state
      setMessages((prevMessages) => {
        const updated = prevMessages.map((msg) =>
          msg.id === data.message_id
            ? {
                ...msg,
                content: data.content,
                status: "completed",
                response_time_ms: data.response_time_ms,
                citations: data.citations || [],
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
  }, [user]);

  // Join playground room when session ID is available
  useEffect(() => {
    if (socket && isConnected && currentSessionId) {
      socket.emit("join_playground", { session_id: currentSessionId });
    }
  }, [socket, isConnected, currentSessionId]);

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

      // Join playground room IMMEDIATELY before state updates
      // This prevents race condition where callback arrives before useEffect runs
      const newSessionId = response.data.session_id;
      if (socket && isConnected && newSessionId && newSessionId !== currentSessionId) {
        socket.emit("join_playground", { session_id: newSessionId });
      }

      setMessages(newMessages);
      setCurrentSessionId(newSessionId);
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

  // Format citations like [citation:3] or [citation:1 2 3] into hoverable superscripts
  const formatCitations = (content, citations = []) => {
    if (!content) return content;

    // Debug: Log what's being passed to formatCitations
    if (content.includes("[citation:")) {
      console.log("[formatCitations] Content has citations, received:", {
        citationsLength: citations?.length || 0,
        citations: citations,
      });
    }

    // Match [citation:X] or [citation:X Y Z]
    const parts = content.split(/(\[citation:[^\]]+\])/g);

    return parts.map((part, index) => {
      const match = part.match(/\[citation:([^\]]+)\]/);
      if (match) {
        const citationNums = match[1].trim().split(/\s+/);
        return (
          <span key={index} className="inline-flex gap-0.5">
            {citationNums.map((num, i) => {
              // Citation numbers are 1-indexed, array is 0-indexed
              const citationIndex = parseInt(num) - 1;
              const citation = citations[citationIndex];
              const filename = citation?.document || `Source ${num}`;
              const page = citation?.page;
              const chunk = citation?.chunk || "";
              // Use single line tooltip - browsers don't render \n in title
              const preview = chunk
                ? chunk.substring(0, 150).replace(/\s+/g, " ").trim()
                : "";

              // Build tooltip based on what data is available
              let tooltip;
              if (citation) {
                if (preview) {
                  tooltip = `📄 ${filename}${page ? ` (p.${page})` : ""} — ${preview}${chunk.length > 150 ? "..." : ""}`;
                } else {
                  tooltip = `📄 ${filename}${page ? ` (p.${page})` : ""}`;
                }
              } else {
                tooltip = `Citation ${num} (no data available)`;
              }

              return (
                <sup
                  key={i}
                  className="text-blue-600 font-medium text-xs cursor-help hover:text-blue-800 hover:underline"
                  title={tooltip}
                >
                  [{num}]
                </sup>
              );
            })}
          </span>
        );
      }
      return part;
    });
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
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="text-gray-600">Service:</span>{" "}
                    <span className="font-medium">{activeService.service_name}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Status:</span>{" "}
                    {activeService.is_active ? (
                      <span className="text-green-600">Active</span>
                    ) : (
                      <span className="text-red-600">Inactive</span>
                    )}
                  </div>
                  <div>
                    <span className="text-gray-600">Socket:</span>{" "}
                    {isConnected ? (
                      <span className="text-green-600">Connected</span>
                    ) : (
                      <span className="text-gray-400">Disconnected</span>
                    )}
                  </div>
                  {activeService?.active_knowledge_base_id && (
                    <>
                      <div>
                        <span className="text-gray-600">Knowledge Base:</span>{" "}
                        <span className="font-medium">
                          {loadingDocs ? "Loading..." : knowledgeBase?.title || "-"}
                        </span>
                      </div>
                      <div>
                        <span className="text-gray-600">Documents:</span>
                        {loadingDocs ? (
                          <span className="text-gray-400 ml-1">Loading...</span>
                        ) : documents.length > 0 ? (
                          <ul className="mt-1 space-y-0.5">
                            {documents.map((doc) => (
                              <li key={doc.id} className="text-xs text-gray-500 truncate" title={doc.filename}>
                                • {doc.filename}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-gray-400 ml-1">No documents</span>
                        )}
                      </div>
                    </>
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
                              {formatCitations(msg.content, msg.citations)}
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
