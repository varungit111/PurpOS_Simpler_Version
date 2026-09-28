"use client";

import { sendActivityMessage } from "@/lib/conversation";
import { getStakeholders, type Stakeholder } from "@/lib/stakeholders";
import Link from "next/link";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

type EvidenceUpdate = {
  id: string;
  claim: string;
  summary: string | null;
};

type HotSeatConversationProps = {
  assessmentId: string;
};

type HotSeatMode = "setup" | "live" | "output";

type VoiceRecognitionStatus =
  | "idle"
  | "listening"
  | "processing"
  | "unavailable"
  | "denied"
  | "error";

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

type SpeechRecognitionResultItem = {
  transcript: string;
};

type SpeechRecognitionResult = {
  isFinal: boolean;
  [index: number]: SpeechRecognitionResultItem;
};

type SpeechRecognitionResultList = {
  length: number;
  [index: number]: SpeechRecognitionResult;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: SpeechRecognitionResultList;
};

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionInstance = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

type VoiceWindow = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

const activityId = "hot-seat";

export function HotSeatConversation({ assessmentId }: HotSeatConversationProps) {
  const [mode, setMode] = useState<HotSeatMode>("setup");
  const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "opening",
      role: "assistant",
      content:
        "Let's start with the people closest to the organisation. What should I understand about your team, customers or partners?"
    }
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ current: 0, total: 20 });
  const [activityStatus, setActivityStatus] = useState("not-started");
  const [evidenceUpdates, setEvidenceUpdates] = useState<EvidenceUpdate[]>([]);
  const [inviteLinkStatus, setInviteLinkStatus] = useState<string | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [speechRecognitionSupported, setSpeechRecognitionSupported] = useState(false);
  const [speechSynthesisSupported, setSpeechSynthesisSupported] = useState(false);
  const [recognitionStatus, setRecognitionStatus] =
    useState<VoiceRecognitionStatus>("unavailable");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const submittedFinalTranscriptRef = useRef<string | null>(null);
  const latestSpokenContentRef = useRef<string | null>(null);

  useEffect(() => {
    const voiceWindow = window as VoiceWindow;
    const recognitionSupported = Boolean(
      voiceWindow.SpeechRecognition ?? voiceWindow.webkitSpeechRecognition
    );
    const synthesisSupported = "speechSynthesis" in window;

    setSpeechRecognitionSupported(recognitionSupported);
    setSpeechSynthesisSupported(synthesisSupported);
    setRecognitionStatus(recognitionSupported ? "idle" : "unavailable");

    return () => {
      recognitionRef.current?.abort();
      if (synthesisSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    getStakeholders(assessmentId)
      .then((items) => {
        if (isMounted) {
          setStakeholders(items);
        }
      })
      .catch(() => {
        if (isMounted) {
          setStakeholders([]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [assessmentId]);

  const progressPercent = useMemo(() => {
    return Math.round((progress.current / progress.total) * 100);
  }, [progress]);

  const stopSpeech = useCallback(() => {
    if (!speechSynthesisSupported) {
      return;
    }
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [speechSynthesisSupported]);

  const speakAssistantResponse = useCallback(
    (content: string) => {
      if (!voiceEnabled || !speechSynthesisSupported || !content.trim()) {
        return;
      }
      if (latestSpokenContentRef.current === content) {
        return;
      }

      recognitionRef.current?.abort();
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(content);
      latestSpokenContentRef.current = content;
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      setIsSpeaking(true);
      window.speechSynthesis.speak(utterance);
    },
    [speechSynthesisSupported, voiceEnabled]
  );

  const submitMessage = useCallback(
    async (message: string) => {
      const trimmedInput = message.trim();
      if (!trimmedInput || isSending) {
        return;
      }

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmedInput
      };

      setMessages((current) => [...current, userMessage]);
      setInput("");
      setIsSending(true);
      setError(null);
      setRecognitionStatus((current) =>
        current === "listening" || current === "processing"
          ? "processing"
          : current
      );

      try {
        const response = await sendActivityMessage({
          sessionId: assessmentId,
          activityId,
          message: trimmedInput
        });
        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: response.assistant_message
        };
        setMessages((current) => [...current, assistantMessage]);
        setProgress(response.progress);
        setActivityStatus(response.activity_status);
        setEvidenceUpdates((current) => [
          ...current,
          ...response.evidence_updates.map((update) => ({
            id: update.id,
            claim: update.claim,
            summary: update.summary
          }))
        ]);
        speakAssistantResponse(response.assistant_message);
      } catch {
        setError("I couldn't send that Hot Seat answer. Please try again.");
      } finally {
        setIsSending(false);
        setRecognitionStatus((current) =>
          current === "processing" ? "idle" : current
        );
      }
    },
    [assessmentId, isSending, speakAssistantResponse]
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(input);
  }

  const stopListening = useCallback(() => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    setRecognitionStatus(speechRecognitionSupported ? "idle" : "unavailable");
  }, [speechRecognitionSupported]);

  const startListening = useCallback(() => {
    if (!voiceEnabled) {
      return;
    }
    if (!speechRecognitionSupported) {
      setRecognitionStatus("unavailable");
      setVoiceError("Voice input is unavailable in this browser.");
      return;
    }
    if (isSending) {
      return;
    }

    stopSpeech();
    recognitionRef.current?.abort();
    submittedFinalTranscriptRef.current = null;
    setVoiceError(null);

    const voiceWindow = window as VoiceWindow;
    const Recognition =
      voiceWindow.SpeechRecognition ?? voiceWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setRecognitionStatus("unavailable");
      setVoiceError("Voice input is unavailable in this browser.");
      return;
    }

    const recognition = new Recognition();
    recognitionRef.current = recognition;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onstart = () => setRecognitionStatus("listening");
    recognition.onend = () => {
      recognitionRef.current = null;
      setRecognitionStatus((current) =>
        current === "listening" ? "idle" : current
      );
    };
    recognition.onerror = (event) => {
      recognitionRef.current = null;
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setRecognitionStatus("denied");
        setVoiceError("Microphone permission was denied.");
        return;
      }
      if (event.error === "no-speech") {
        setRecognitionStatus("idle");
        setVoiceError("I didn't catch any speech. Try the microphone again.");
        return;
      }
      setRecognitionStatus("error");
      setVoiceError("Voice recognition stopped before it could capture an answer.");
    };
    recognition.onresult = (event) => {
      let finalTranscript = "";
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      const visibleTranscript = `${finalTranscript} ${interimTranscript}`.trim();
      if (visibleTranscript) {
        setInput(visibleTranscript);
      }

      const trimmedFinalTranscript = finalTranscript.trim();
      if (!trimmedFinalTranscript) {
        return;
      }
      if (submittedFinalTranscriptRef.current !== null) {
        return;
      }

      submittedFinalTranscriptRef.current = trimmedFinalTranscript;
      setInput(trimmedFinalTranscript);
      recognition.stop();
      void submitMessage(trimmedFinalTranscript);
    };

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setRecognitionStatus("error");
      setVoiceError("Voice recognition could not start. Please try again.");
    }
  }, [
    isSending,
    speechRecognitionSupported,
    stopSpeech,
    submitMessage,
    voiceEnabled
  ]);

  useEffect(() => {
    if (!voiceEnabled) {
      stopListening();
      stopSpeech();
      setVoiceError(null);
    }
  }, [stopListening, stopSpeech, voiceEnabled]);

  return (
    <div className="min-h-screen bg-[#f2f2f4] text-[#292735]">
      <IdentifyTopBar assessmentId={assessmentId} />
      {mode === "setup" ? (
        <HotSeatSetup
          assessmentId={assessmentId}
          inviteLinkStatus={inviteLinkStatus}
          onCopyInviteLink={handleCopyInviteLink}
          onStart={() => setMode("live")}
          stakeholders={stakeholders}
        />
      ) : null}
      {mode === "live" ? (
        <HotSeatLive
          activityStatus={activityStatus}
          error={error}
          input={input}
          isSending={isSending}
          messages={messages}
          onFinish={() => setMode("output")}
          onInput={setInput}
          onStartListening={startListening}
          onStopListening={stopListening}
          onStopSpeech={stopSpeech}
          onSubmit={handleSubmit}
          progressPercent={progressPercent}
          progress={progress}
          recognitionStatus={recognitionStatus}
          speechRecognitionSupported={speechRecognitionSupported}
          speechSynthesisSupported={speechSynthesisSupported}
          voiceEnabled={voiceEnabled}
          voiceError={voiceError}
          isSpeaking={isSpeaking}
          onVoiceEnabledChange={setVoiceEnabled}
        />
      ) : null}
      {mode === "output" ? (
        <HotSeatOutput
          assessmentId={assessmentId}
          evidenceUpdates={evidenceUpdates}
          onResume={() => setMode("live")}
          progressPercent={progressPercent}
          progress={progress}
        />
      ) : null}
    </div>
  );

  async function handleCopyInviteLink() {
    const inviteLink = `https://purpos.app/hotseat/${assessmentId.slice(0, 8)}`;

    try {
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(inviteLink);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = inviteLink;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setInviteLinkStatus("Invite link copied.");
    } catch {
      setInviteLinkStatus("Copy failed. Select the link and copy it manually.");
    }
  }
}

function HotSeatSetup({
  assessmentId,
  inviteLinkStatus,
  onCopyInviteLink,
  onStart,
  stakeholders
}: {
  assessmentId: string;
  inviteLinkStatus: string | null;
  onCopyInviteLink: () => void;
  onStart: () => void;
  stakeholders: Stakeholder[];
}) {
  const invitees = stakeholders.slice(0, 4);
  const inviteLink = `purpos.app/hotseat/${assessmentId.slice(0, 8)}`;
  return (
    <main className="px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-6xl">
        <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
          02 Listen - Hot Seat
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-normal">
          Let&apos;s hear it from real people.
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          A 5-minute interview: I ask, they talk, the existing engine turns
          useful answers into Identify evidence.
        </p>

        <div className="mt-7 grid gap-4 lg:grid-cols-[minmax(0,1fr)_1.2fr]">
          <article className="flex min-h-48 flex-col rounded-md border border-slate-200 bg-white p-6 shadow-sm">
            <span className="grid size-10 place-items-center rounded-md bg-slate-100 text-xl">
              ◉
            </span>
            <h2 className="mt-5 text-lg font-bold">Interview yourself</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Start with your own story. You can type here today; the
              conversation engine and follow-up behavior stay the same.
            </p>
            <div className="mt-auto flex items-center justify-between pt-6 text-sm">
              <span className="text-slate-500">~7 min - voice</span>
              <button
                className="rounded-md border border-slate-300 bg-white px-4 py-2 font-bold outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                onClick={onStart}
                type="button"
              >
                Start now
              </button>
            </div>
          </article>

          <article className="flex min-h-48 flex-col rounded-md border border-[#6f50b5] bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-md bg-[#eee6fb] text-[#6f50b5]">
                ↗
              </span>
              <span className="rounded bg-[#eee6fb] px-2 py-1 text-xs font-bold uppercase tracking-[0.18em] text-[#6f50b5]">
                Flagship - biggest payoff
              </span>
            </div>
            <h2 className="mt-5 text-lg font-bold">
              Invite your team and customers
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Share one link. I run a private 5-minute interview with each
              person and store evidence without changing the Hot Seat engine.
            </p>
            <div className="mt-4 flex rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
              <code className="min-w-0 flex-1 truncate px-2 py-1 text-slate-600">
                {inviteLink}
              </code>
              <button
                className="rounded-md bg-[#6f50b5] px-3 py-1 font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                onClick={onCopyInviteLink}
                type="button"
              >
                Copy link
              </button>
            </div>
            {inviteLinkStatus ? (
              <p className="mt-2 text-xs font-semibold text-[#6f50b5]">
                {inviteLinkStatus}
              </p>
            ) : null}
          </article>
        </div>

        <section className="mt-5 rounded-md border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-3 border-b border-slate-200 pb-3">
            <h2 className="text-sm font-bold">Invited so far</h2>
            <span className="text-xs text-slate-500">
              {invitees.length} people - {Math.min(2, invitees.length)} done
            </span>
          </div>
          <div className="mt-2 grid">
            {invitees.length === 0 ? (
              <p className="py-5 text-sm text-slate-600">
                Add stakeholders in Who Matters to seed invitees.
              </p>
            ) : (
              invitees.map((stakeholder, index) => (
                <div
                  className="flex items-center justify-between gap-4 border-b border-slate-100 py-3 last:border-b-0"
                  key={stakeholder.id}
                >
                  <div className="flex items-center gap-3">
                    <span className="size-7 rounded-full bg-slate-200" />
                    <div>
                      <p className="text-sm font-bold">{stakeholder.name}</p>
                      <p className="text-xs text-slate-500">
                        {stakeholder.groupType} - {stakeholder.relationship ?? "relationship pending"}
                      </p>
                    </div>
                  </div>
                  <span className="rounded-full bg-[#eee6fb] px-3 py-1 text-xs font-bold text-[#6f50b5]">
                    {index < 2 ? "Completed" : index === 2 ? "Opened" : "Sent"}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function HotSeatLive({
  activityStatus,
  error,
  input,
  isSpeaking,
  isSending,
  messages,
  onFinish,
  onInput,
  onStartListening,
  onStopListening,
  onStopSpeech,
  onSubmit,
  onVoiceEnabledChange,
  progress,
  progressPercent,
  recognitionStatus,
  speechRecognitionSupported,
  speechSynthesisSupported,
  voiceEnabled,
  voiceError
}: {
  activityStatus: string;
  error: string | null;
  input: string;
  isSpeaking: boolean;
  isSending: boolean;
  messages: ChatMessage[];
  onFinish: () => void;
  onInput: (value: string) => void;
  onStartListening: () => void;
  onStopListening: () => void;
  onStopSpeech: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onVoiceEnabledChange: (value: boolean) => void;
  progress: { current: number; total: number };
  progressPercent: number;
  recognitionStatus: VoiceRecognitionStatus;
  speechRecognitionSupported: boolean;
  speechSynthesisSupported: boolean;
  voiceEnabled: boolean;
  voiceError: string | null;
}) {
  const latestQuestion =
    [...messages].reverse().find((message) => message.role === "assistant")
      ?.content ?? "Tell me what matters most.";
  const transcript = messages
    .filter((message) => message.role === "user")
    .map((message) => message.content)
    .join(" ");
  const voiceStatusLabel = getVoiceStatusLabel({
    isSending,
    isSpeaking,
    recognitionStatus,
    speechRecognitionSupported,
    speechSynthesisSupported,
    voiceEnabled
  });
  const micDisabled =
    !voiceEnabled ||
    !speechRecognitionSupported ||
    isSending ||
    recognitionStatus === "processing" ||
    isSpeaking;
  const isListening = recognitionStatus === "listening";

  return (
    <main className="px-5 py-6 sm:px-8">
      <section className="mx-auto max-w-7xl">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold">
              <span className="mr-2 text-red-600">●</span>
              LIVE
            </span>
            <span className="size-8 rounded-full bg-slate-200" />
            <span className="text-sm font-bold">Hot Seat</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="font-mono text-slate-400">
              {String(Math.max(1, progress.current)).padStart(2, "0")}:00 / 07:00
            </span>
            <button
              className="rounded-md border border-slate-300 bg-white px-4 py-2 font-bold outline-none transition hover:border-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
              onClick={onFinish}
              type="button"
            >
              Finish
            </button>
          </div>
        </div>

        <section className="mt-5 grid min-h-[520px] place-items-center rounded-none border-4 border-[#6ea5ff] bg-white p-6">
          <div className="max-w-3xl text-center">
            <div className="mx-auto grid size-20 place-items-center rounded-full bg-[#6f50b5]">
              <span className="size-7 rounded-full bg-white" />
            </div>
            <p className="mt-5 text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
              PurpOS is asking - follow-up
            </p>
            <h1 className="mt-5 text-2xl font-bold leading-tight tracking-normal sm:text-4xl">
              {latestQuestion}
            </h1>
            <div className="mx-auto mt-7 flex h-12 max-w-xs items-center justify-center gap-1">
              {Array.from({ length: 24 }).map((_, index) => (
                <span
                  className="w-1 rounded-full bg-[#9f83dc]"
                  key={index}
                  style={{ height: `${12 + ((index * 7) % 34)}px` }}
                />
              ))}
            </div>
            <div className="mx-auto mt-5 flex max-w-2xl flex-wrap items-center justify-center gap-3 text-sm">
              <label className="inline-flex min-h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 font-bold outline-none transition focus-within:ring-2 focus-within:ring-[#6f50b5] focus-within:ring-offset-2">
                <input
                  checked={voiceEnabled}
                  className="size-4 accent-[#6f50b5]"
                  onChange={(event) => onVoiceEnabledChange(event.target.checked)}
                  type="checkbox"
                />
                Voice {voiceEnabled ? "On" : "Off"}
              </label>
              <span className="text-xs font-semibold text-slate-500">
                {voiceStatusLabel}
              </span>
              {isSpeaking ? (
                <button
                  className="min-h-10 rounded-md border border-slate-300 bg-white px-3 font-bold outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                  onClick={onStopSpeech}
                  type="button"
                >
                  Stop voice
                </button>
              ) : null}
            </div>
            <form className="mx-auto mt-5 flex max-w-2xl gap-3" onSubmit={onSubmit}>
              <label className="sr-only" htmlFor="hot-seat-message">
                Hot Seat answer
              </label>
              <button
                aria-label={isListening ? "Stop listening" : "Start voice input"}
                className="grid size-11 shrink-0 place-items-center rounded-md border border-slate-300 bg-white text-lg font-bold outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400 focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                disabled={!isListening && micDisabled}
                onClick={isListening ? onStopListening : onStartListening}
                title={isListening ? "Stop listening" : "Start voice input"}
                type="button"
              >
                {isListening ? "■" : "🎙"}
              </button>
              <input
                className="min-h-11 flex-1 rounded-md border border-slate-300 px-4 text-sm outline-none transition focus:border-[#6f50b5] focus:ring-2 focus:ring-[#6f50b5]/20"
                disabled={isSending}
                id="hot-seat-message"
                onChange={(event) => onInput(event.target.value)}
                placeholder="Type while the interview listens..."
                value={input}
              />
              <button
                className="rounded-md bg-[#6f50b5] px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                data-stage-mutation
                disabled={isSending || !input.trim()}
                type="submit"
              >
                Send
              </button>
            </form>
            {voiceError ? (
              <p className="mt-3 text-sm font-medium text-amber-700" role="status">
                {voiceError}
              </p>
            ) : null}
            {error ? (
              <p className="mt-3 text-sm font-medium text-red-700" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </section>

        <section className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
              Live transcript
            </p>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              {transcript || "Answers will appear here as the interview runs."}
            </p>
          </div>
          <div className="rounded-md border border-[#c9b9ef] bg-[#eee6fb] p-4">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
              I&apos;m noting
            </p>
            <ul className="mt-3 grid gap-2 text-sm">
              <li>Evidence areas: {progress.current}/{progress.total}</li>
              <li>Status: {activityStatus}</li>
              <li>Coverage: {progressPercent}%</li>
            </ul>
          </div>
        </section>
      </section>
    </main>
  );
}

function getVoiceStatusLabel({
  isSending,
  isSpeaking,
  recognitionStatus,
  speechRecognitionSupported,
  speechSynthesisSupported,
  voiceEnabled
}: {
  isSending: boolean;
  isSpeaking: boolean;
  recognitionStatus: VoiceRecognitionStatus;
  speechRecognitionSupported: boolean;
  speechSynthesisSupported: boolean;
  voiceEnabled: boolean;
}) {
  if (!voiceEnabled) {
    return "Typed Hot Seat is active.";
  }
  if (!speechRecognitionSupported && !speechSynthesisSupported) {
    return "Voice input and playback are unavailable in this browser.";
  }
  if (!speechRecognitionSupported) {
    return "Voice input is unavailable in this browser.";
  }
  if (!speechSynthesisSupported) {
    return "Voice playback is unavailable; typed responses still work.";
  }
  if (isSending || recognitionStatus === "processing") {
    return "Processing your answer.";
  }
  if (isSpeaking) {
    return "Reading the latest response.";
  }
  if (recognitionStatus === "listening") {
    return "Listening now.";
  }
  if (recognitionStatus === "denied") {
    return "Microphone permission denied.";
  }
  if (recognitionStatus === "error") {
    return "Voice recognition needs another try.";
  }
  return "Tap the microphone for one turn.";
}

function HotSeatOutput({
  assessmentId,
  evidenceUpdates,
  onResume,
  progress,
  progressPercent
}: {
  assessmentId: string;
  evidenceUpdates: EvidenceUpdate[];
  onResume: () => void;
  progress: { current: number; total: number };
  progressPercent: number;
}) {
  return (
    <main className="px-5 py-8 sm:px-8">
      <section className="mx-auto max-w-6xl">
        <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
          02 Listen - Hot Seat Output
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-normal">
          Here&apos;s what I heard.
        </h1>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          The interview output below is generated from the existing conversation
          engine&apos;s structured evidence updates.
        </p>

        <div className="mt-7 grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 pb-4">
              <h2 className="text-lg font-bold">Evidence captured</h2>
              <span className="rounded-full bg-[#eee6fb] px-3 py-1 text-xs font-bold text-[#6f50b5]">
                {evidenceUpdates.length} updates
              </span>
            </div>
            <div className="mt-4 grid gap-3">
              {evidenceUpdates.length === 0 ? (
                <p className="rounded-md border border-dashed border-slate-300 p-4 text-sm text-slate-600">
                  No structured evidence was created yet. Resume the interview
                  and answer with a little more detail.
                </p>
              ) : (
                evidenceUpdates.map((update) => (
                  <article
                    className="rounded-md border border-slate-200 bg-slate-50 p-4"
                    key={update.id}
                  >
                    <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#6f50b5]">
                      {update.summary ?? "Hot Seat"}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-slate-700">
                      {update.claim}
                    </p>
                  </article>
                ))
              )}
            </div>
          </section>

          <aside className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
              Coverage
            </p>
            <p className="mt-3 text-5xl font-bold tracking-normal">
              {progressPercent}%
            </p>
            <p className="mt-2 text-sm text-slate-600">
              {progress.current} of {progress.total} playbook areas touched by
              the interview context.
            </p>
            <div className="mt-5 h-1.5 rounded-full bg-slate-200">
              <div
                className="h-1.5 rounded-full bg-[#6f50b5]"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <div className="mt-7 grid gap-3">
              <button
                className="min-h-11 rounded-md border border-slate-300 bg-white px-4 text-sm font-bold outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                onClick={onResume}
                type="button"
              >
                Resume interview
              </button>
              <Link
                className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#6f50b5] px-4 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                href={`/assessments/${assessmentId}/identify/company-cards`}
              >
                Continue to Company Cards
              </Link>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

function IdentifyTopBar({ assessmentId }: { assessmentId: string }) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="flex min-h-16 items-center justify-between gap-4 px-5 sm:px-8">
        <Link
          className="flex items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
          href={`/assessments/${assessmentId}/identify`}
        >
          <span className="grid size-8 place-items-center rounded-md bg-[#6f50b5] text-sm font-bold text-white">
            P
          </span>
          <span className="text-base font-bold">PurpOS</span>
        </Link>
        <div className="hidden items-center gap-4 text-sm sm:flex">
          <span className="font-semibold tracking-[0.18em] text-slate-500">
            IDENTIFY
          </span>
          <span className="text-slate-400">01 Discover</span>
          <span className="font-semibold text-[#6f50b5]">02 Listen</span>
          <span className="text-slate-400">03 Understand</span>
        </div>
        <Link
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-[#292735] outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
          href={`/assessments/${assessmentId}/identify`}
        >
          Board
        </Link>
      </nav>
    </header>
  );
}
