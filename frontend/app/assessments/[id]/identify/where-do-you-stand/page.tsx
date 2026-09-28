import { WhereDoYouStandReview } from "@/components/identify/WhereDoYouStandReview";
import { notFound } from "next/navigation";

type WhereDoYouStandPageProps = {
  params: Promise<{
    id: string;
  }>;
};

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function WhereDoYouStandPage({
  params
}: WhereDoYouStandPageProps) {
  const { id } = await params;

  if (!uuidPattern.test(id)) {
    notFound();
  }

  return <WhereDoYouStandReview assessmentId={id} />;
}
