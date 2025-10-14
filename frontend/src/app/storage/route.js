import { NextResponse } from "next/server";

const BACKEND_URL = "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/storage`);
    const html = await response.text();

    return new NextResponse(html, {
      status: response.status,
      headers: {
        "Content-Type": "text/html",
      },
    });
  } catch (error) {
    console.error("Storage listing error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}
