// frontend/src/components/AutoPairForm.tsx
import React, { useState } from "react";
import { compareApi } from "../services/api";
import {
  DocumentPlusIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
} from "@heroicons/react/24/outline";

interface AutoPairFormProps {
  onClose: () => void;
}

const AutoPairForm: React.FC<AutoPairFormProps> = ({ onClose }) => {
  const [cradleId, setCradleId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!cradleId.trim()) {
      setError("Cradle ID is required");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const job = await compareApi.autoPairJob(cradleId.trim());
      setSuccess(`Job "${job.job_name}" created successfully!`);

      // Close modal after success
      setTimeout(() => {
        onClose();
        window.location.reload(); // Refresh to show new job
      }, 1500);
    } catch (error: any) {
      setError(error.message || "Failed to create auto-pair job");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label
          htmlFor="cradleId"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Cradle ID
        </label>
        <div className="relative">
          <input
            type="text"
            id="cradleId"
            value={cradleId}
            onChange={(e) => setCradleId(e.target.value)}
            className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
            placeholder="Enter Cradle ID (e.g., 123456)"
            disabled={loading}
          />
          <div className="absolute inset-y-0 right-0 flex items-center pr-3">
            <DocumentPlusIcon className="w-5 h-5 text-gray-400" />
          </div>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          This will automatically find and pair acceptance and emission files
          for the given Cradle ID.
        </p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4">
          <div className="flex items-center">
            <ExclamationCircleIcon className="w-5 h-5 text-red-400 mr-3" />
            <div className="text-sm text-red-700">{error}</div>
          </div>
        </div>
      )}

      {success && (
        <div className="rounded-lg bg-green-50 border border-green-200 p-4">
          <div className="flex items-center">
            <CheckCircleIcon className="w-5 h-5 text-green-400 mr-3" />
            <div className="text-sm text-green-700">{success}</div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
          disabled={loading}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={loading || !cradleId.trim()}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          {loading ? (
            <>
              <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
              Creating...
            </>
          ) : (
            <>
              <DocumentPlusIcon className="w-4 h-4 mr-2" />
              Create Job
            </>
          )}
        </button>
      </div>
    </form>
  );
};

export default AutoPairForm;
