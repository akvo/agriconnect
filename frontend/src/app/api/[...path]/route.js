import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://localhost:8000";

async function handler(request, { params }) {
  try {
    const { path } = await params;
    const pathString = Array.isArray(path) ? path.join("/") : path;
    const url = `${BACKEND_URL}/api/${pathString}`;

    // Get search params from the original request
    const searchParams = request.nextUrl.searchParams;
    const fullUrl = searchParams.toString() ? `${url}?${searchParams}` : url;

    // Forward headers (especially Authorization)
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      // Skip headers that shouldn't be forwarded
      if (
        !["host", "connection", "content-length"].includes(key.toLowerCase())
      ) {
        headers.set(key, value);
      }
    });

    // Get request body if present
    let body = null;
    const contentType = request.headers.get("content-type") || "";

    if (["POST", "PUT", "PATCH"].includes(request.method)) {
      if (contentType.includes("application/json")) {
        // Read JSON as string
        body = await request.text();
      } else {
        // Read binary-safe
        const buffer = await request.arrayBuffer();
        body = Buffer.from(buffer);
      }
    }

    // Make request to backend
    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
    });

    // Get response data
    const responseData = await response.text();

    // Create response with same status and headers
    const nextResponse = new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
    });

    // Forward response headers
    response.headers.forEach((value, key) => {
      nextResponse.headers.set(key, value);
    });

    return nextResponse;
  } catch (error) {
    console.error("API Proxy Error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
