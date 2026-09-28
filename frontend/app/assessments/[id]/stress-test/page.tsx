import { StressTestReview } from "@/components/stress-test/StressTestReview";
import { notFound } from "next/navigation";
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; if (!uuidPattern.test(id)) notFound(); return <StressTestReview assessmentId={id} />; }
