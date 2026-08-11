import { useState, useEffect } from "react";
import { ComparisonJob } from "../types";
import { compareApi } from "../services/api";

export function useRouting() {
  const [selectedJob, setSelectedJob] = useState<ComparisonJob | null>(null);

  useEffect(() => {
    const handleLocationChange = async () => {
      const path = window.location.pathname;
      const compareMatch = path.match(/^\/compare\/(\d+)$/);

      if (compareMatch) {
        const jobId = parseInt(compareMatch[1], 10);
        try {
          const job = await compareApi.getJob(jobId);
          setSelectedJob(job);
        } catch (error) {
          console.error("Failed to load job from URL", error);
          window.history.replaceState(null, "", "/");
          setSelectedJob(null);
        }
      } else {
        setSelectedJob(null);
      }
    };

    handleLocationChange();

    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, []);

  const handleSelectJob = (job: ComparisonJob | null) => {
    setSelectedJob(job);
    if (job) {
      window.history.pushState(null, "", `/compare/${job.id}`);
    } else {
      window.history.pushState(null, "", "/");
    }
  };

  return { selectedJob, handleSelectJob };
}
