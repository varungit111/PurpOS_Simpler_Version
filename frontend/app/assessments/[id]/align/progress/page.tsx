import { AlignmentProgress } from "@/components/alignment/AlignmentProgress";
import { notFound } from "next/navigation";

type PageProps = { params: Promise<{ id: string }> };
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function AlignmentProgressPage({ params }: PageProps) {
  const { id } = await params;
  if (!uuidPattern.test(id)) notFound();
  return <AlignmentProgress assessmentId={id} />;
}
