import { WhoMattersMap } from "@/components/identify/WhoMattersMap";
import { notFound } from "next/navigation";

type WhoMattersPageProps = {
  params: Promise<{
    id: string;
  }>;
};

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function WhoMattersPage({ params }: WhoMattersPageProps) {
  const { id } = await params;

  if (!uuidPattern.test(id)) {
    notFound();
  }

  return <WhoMattersMap assessmentId={id} />;
}
