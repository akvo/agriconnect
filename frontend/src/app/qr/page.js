import Image from "next/image";

export const metadata = {
  title: "WhatsApp QR Code - AgriConnect",
  description: "Scan to connect with AgriConnect on WhatsApp",
};

export default function QRPage() {
  return (
    <div className="min-h-screen bg-gradient-brand flex items-center justify-center px-4">
      <div className="max-w-md w-full text-center">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-secondary-900 mb-2">
            Connect with AgriConnect
          </h1>
          <p className="text-secondary-600 text-lg leading-relaxed">
            Scan the QR code below to start a conversation on WhatsApp
          </p>
        </div>

        <div className="bg-white p-6 shadow-lg inline-block" style={{ borderRadius: "12px" }}>
          <Image
            src="/wa-qr-code.png"
            alt="WhatsApp QR Code"
            width={256}
            height={256}
            priority
          />
        </div>

        <p className="mt-6 text-sm text-secondary-500">
          Open WhatsApp on your phone and scan this code to get started
        </p>

        <a
          href="https://wa.link/2ivyev"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 inline-flex items-center justify-center px-6 py-3 bg-green-600 text-white font-semibold transition-all duration-200 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
          style={{ borderRadius: "5px" }}
        >
          Open in WhatsApp
        </a>
      </div>
    </div>
  );
}
