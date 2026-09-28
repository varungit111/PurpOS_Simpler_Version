import { ListenSummaryReview } from "@/components/identify/ListenSummaryReview";

type ListenSummaryPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function ListenSummaryPage({
  params
}: ListenSummaryPageProps) {
  const { id } = await params;

  return <ListenSummaryReview assessmentId={id} />;
}
