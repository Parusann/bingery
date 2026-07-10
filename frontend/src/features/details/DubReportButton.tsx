import { useMemo, useState } from "react";
import { Button } from "@/design/Button";
import { Modal } from "@/design/Modal";
import { cn } from "@/lib/cn";
import { useAnimeEpisodes } from "@/hooks/useSchedule";
import { useCreateDubReport } from "@/hooks/useDubReports";
import { useAuth } from "@/stores/auth";

interface Props {
  animeId: number;
}

function toIsoZ(localDatetimeValue: string): string {
  // <input type="datetime-local"> gives "YYYY-MM-DDTHH:MM" with no timezone;
  // treat it as UTC and append :00Z so the backend accepts it.
  return `${localDatetimeValue}:00Z`;
}

// Shared field skin — matches design/Input's warm focus treatment.
const fieldClass = cn(
  "mt-1 block w-full rounded-lg px-3.5 py-2.5 text-sm",
  "bg-surface border border-border outline-none transition-colors",
  "placeholder:text-text-dim",
  "focus:border-amber/50 focus:ring-1 focus:ring-amber/35 focus:bg-amber/[0.03]"
);

export function DubReportButton({ animeId }: Props) {
  const user = useAuth((s) => s.user);
  const [open, setOpen] = useState(false);
  const [episodeId, setEpisodeId] = useState<number | "">("");
  const [airDate, setAirDate] = useState("");
  const [note, setNote] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const episodes = useAnimeEpisodes(animeId, open);
  const createReport = useCreateDubReport();

  const sortedEpisodes = useMemo(
    () =>
      [...(episodes.data?.episodes ?? [])].sort(
        (a, b) => a.episode_number - b.episode_number
      ),
    [episodes.data]
  );

  if (!user) return null;

  const reset = () => {
    setEpisodeId("");
    setAirDate("");
    setNote("");
    setSubmitError(null);
    setSubmitSuccess(false);
  };

  const close = () => {
    setOpen(false);
    reset();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(false);
    if (typeof episodeId !== "number") {
      setSubmitError("Pick an episode first.");
      return;
    }
    if (!airDate) {
      setSubmitError("Pick a date and time.");
      return;
    }
    try {
      await createReport.mutateAsync({
        episode_id: episodeId,
        air_date: toIsoZ(airDate),
        note: note.trim() || undefined,
      });
      setSubmitSuccess(true);
      setEpisodeId("");
      setAirDate("");
      setNote("");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Submission failed — try again.";
      setSubmitError(msg);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
      >
        Report missing dub date
      </Button>
      <Modal open={open} onClose={close} maxWidth="500px">
        <form onSubmit={submit} className="p-6 space-y-4">
          <header>
            <h2 className="font-display text-title">Report a dub air date</h2>
            <p className="text-text-muted text-sm mt-1">
              Tell us when a dubbed episode aired (or will air). Admins review
              submissions before they appear publicly.
            </p>
          </header>

          <label className="block text-sm">
            <span className="text-caption font-medium text-text-muted">
              Episode
            </span>
            <select
              value={episodeId}
              onChange={(e) =>
                setEpisodeId(e.target.value ? Number(e.target.value) : "")
              }
              className={fieldClass}
              disabled={episodes.isLoading}
              required
            >
              <option value="">
                {episodes.isLoading ? "Loading episodes…" : "— select episode —"}
              </option>
              {sortedEpisodes.map((ep) => (
                <option key={ep.id} value={ep.id}>
                  Episode {ep.episode_number}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-caption font-medium text-text-muted">
              Dub air date and time (UTC)
            </span>
            <input
              type="datetime-local"
              value={airDate}
              onChange={(e) => setAirDate(e.target.value)}
              className={cn(fieldClass, "tnum")}
              required
            />
          </label>

          <label className="block text-sm">
            <span className="text-caption font-medium text-text-muted">
              Note (optional)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={500}
              rows={3}
              placeholder="Where did you see this? Link to a tweet, trailer, etc."
              className={fieldClass}
            />
          </label>

          {submitError ? (
            <p className="text-danger text-sm" role="alert">
              {submitError}
            </p>
          ) : null}
          {submitSuccess ? (
            <p className="text-success text-sm" role="status">
              Thanks — your report is in the queue.
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="glass" onClick={close}>
              Close
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={createReport.isPending}
            >
              Submit
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
