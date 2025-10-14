import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://localhost:8000";

async function handler(request, { params }) {
  try {
    const { path } = await params;
    const pathString = Array.isArray(path) ? path.join("/") : path;
    const url = `${BACKEND_URL}/storage/${pathString}`;

    // Get search params from the original request
    const searchParams = request.nextUrl.searchParams;
    const fullUrl = searchParams.toString() ? `${url}?${searchParams}` : url;

    // Forward headers (skip conditional headers to avoid 304 responses)
    const headers = new Headers();
    request.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase();
      if (
        ![
          "host",
          "connection",
          "content-length",
          "if-none-match",
          "if-modified-since",
        ].includes(lowerKey)
      ) {
        headers.set(key, value);
      }
    });

    // Make request to backend
    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
    });

    // Handle 304 Not Modified specially
    if (response.status === 304) {
      return new NextResponse(null, {
        status: 304,
      });
    }

    // Get response data
    const responseData = await response.arrayBuffer();

    // Create response with same status and headers
    const nextResponse = new NextResponse(responseData, {
      status: response.status,
      statusText: response.statusText,
    });

    // Forward response headers (especially content-type for static files)
    response.headers.forEach((value, key) => {
      nextResponse.headers.set(key, value);
    });

    return nextResponse;
  } catch (error) {
    console.error("Storage Proxy Error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}

export const GET = handler;
