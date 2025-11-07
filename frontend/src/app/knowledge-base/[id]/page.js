export const metadata = {
  title: "Document - AgriConnect",
  description: "Manage your document library of a knowledge base for AI-powered assistance",
};

export default function DocumentPageRoute({ params }) {
  const { id } = params;

  return (
    <div>
      <h1>DOCUMENT</h1>
      <p>Document ID: {id}</p>
    </div>
  );
}