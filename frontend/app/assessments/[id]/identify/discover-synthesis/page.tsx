import { DiscoverSynthesisReview } from "@/components/identify/DiscoverSynthesisReview";

type DiscoverSynthesisPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function DiscoverSynthesisPage({
  params
}: DiscoverSynthesisPageProps) {
  const { id } = await params;

  return <DiscoverSynthesisReview assessmentId={id} />;
}
