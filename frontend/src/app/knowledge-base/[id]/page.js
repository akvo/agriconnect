import DocumentPage from "../../../components/document/DocumentPage";

export const metadata = {
  title: "Document - AgriConnect",
  description:
    "Manage your document library of a knowledge base for AI-powered assistance",
};

export default function DocumentPageRoute({ params }) {
  const { id } = params;

  return <DocumentPage kbId={id} />;
}
