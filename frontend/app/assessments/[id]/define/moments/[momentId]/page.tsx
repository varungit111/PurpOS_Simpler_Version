import { MomentDetail } from "@/components/define/MomentDetail";
import { notFound } from "next/navigation";

type PageProps = { params: Promise<{ id: string; momentId: string }> };
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function MomentPage({ params }: PageProps) {
  const { id, momentId } = await params;
  if (!uuidPattern.test(id) || !uuidPattern.test(momentId)) notFound();
  return <MomentDetail assessmentId={id} momentId={momentId} />;
}
