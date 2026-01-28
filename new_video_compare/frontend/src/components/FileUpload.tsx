// frontend/src/components/FileUpload.tsx
import React, { useState, useCallback, useRef } from "react";
import {
  CloudArrowUpIcon,
  FilmIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";

interface UploadedFile {
  id: number;
  filename: string;
  file_type: string;
  duration: number | null;
  width: number | null;
  height: number | null;
}

interface FileUploadProps {
  onJobCreated: () => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onJobCreated }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [acceptanceFile, setAcceptanceFile] = useState<UploadedFile | null>(null);
  const [emissionFile, setEmissionFile] = useState<UploadedFile | null>(null);
  const [uploading, setUploading] = useState<"acceptance" | "emission" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobName, setJobName] = useState("");
  const [creatingJob, setCreatingJob] = useState(false);
  const [sensitivityLevel, setSensitivityLevel] = useState<"low" | "medium" | "high">("medium");

  const acceptanceInputRef = useRef<HTMLInputElement>(null);
  const emissionInputRef = useRef<HTMLInputElement>(null);

  const uploadFile = async (file: File, fileType: "acceptance" | "emission") => {
    setUploading(fileType);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);

    try {
      const response = await fetch(
        "http://localhost:8001/api/v1/files/files/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        console.error("Upload error:", errorData);
        throw new Error(`Upload failed: ${errorData?.detail || response.statusText}`);
      }

      const data = await response.json();
      console.log("Upload response:", data);
      
      // Backend returns file_id, not id!
      const uploadedFile: UploadedFile = {
        id: data.file_id,  // ← Fixed: was data.id
        filename: data.filename,
        file_type: fileType,
        duration: null,  // Not in upload response
        width: null,     // Not in upload response
        height: null,    // Not in upload response
      };

      console.log("Created uploadedFile:", uploadedFile);

      if (fileType === "acceptance") {
        setAcceptanceFile(uploadedFile);
      } else {
        setEmissionFile(uploadedFile);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(null);
    }
  };

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, fileType: "acceptance" | "emission") => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        uploadFile(files[0], fileType);
      }
    },
    []
  );

  const handleFileSelect = (
    e: React.ChangeEvent<HTMLInputElement>,
    fileType: "acceptance" | "emission"
  ) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      uploadFile(files[0], fileType);
    }
  };

  const createJob = async () => {
    if (!acceptanceFile || !emissionFile) {
      setError("Please upload both acceptance and emission files");
      return;
    }

    setCreatingJob(true);
    setError(null);

    const payload = {
      job_name: jobName || `Comparison ${new Date().toLocaleString()}`,
      acceptance_file_id: acceptanceFile.id,
      emission_file_id: emissionFile.id,
      comparison_type: "full",
      sensitivity_level: sensitivityLevel,
    };

    console.log("Creating job with payload:", payload);

    try {
      const response = await fetch("http://localhost:8001/api/v1/compare/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const errorDetail = errorData?.detail || response.statusText;
        console.error("Create job error:", errorData);
        throw new Error(`Failed to create job: ${JSON.stringify(errorDetail)}`);
      }

      // Reset form and close modal
      setAcceptanceFile(null);
      setEmissionFile(null);
      setJobName("");
      setIsOpen(false);
      onJobCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setCreatingJob(false);
    }
  };

  const resetForm = () => {
    setAcceptanceFile(null);
    setEmissionFile(null);
    setJobName("");
    setSensitivityLevel("medium");
    setError(null);
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const DropZone = ({
    fileType,
    file,
    inputRef,
  }: {
    fileType: "acceptance" | "emission";
    file: UploadedFile | null;
    inputRef: React.RefObject<HTMLInputElement | null>;
  }) => {
    const isAcceptance = fileType === "acceptance";
    const bgColor = isAcceptance ? "bg-green-50" : "bg-red-50";
    const borderColor = isAcceptance
      ? isDragging
        ? "border-green-500"
        : "border-green-300"
      : isDragging
      ? "border-red-500"
      : "border-red-300";
    const iconColor = isAcceptance ? "text-green-500" : "text-red-500";
    const label = isAcceptance ? "Acceptance Video" : "Emission Video";

    return (
      <div className="flex-1">
        <label className={`block text-sm font-medium mb-2 ${iconColor}`}>
          {label}
        </label>

        {file ? (
          <div className={`${bgColor} rounded-xl p-4 border-2 ${borderColor}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <CheckCircleIcon className={`w-8 h-8 ${iconColor}`} />
                <div>
                  <p className="font-medium text-gray-900 truncate max-w-[200px]">
                    {file.filename}
                  </p>
                  <p className="text-sm text-gray-500">
                    {file.width}x{file.height} • {formatDuration(file.duration)}
                  </p>
                </div>
              </div>
              <button
                onClick={() =>
                  isAcceptance ? setAcceptanceFile(null) : setEmissionFile(null)
                }
                className="p-2 hover:bg-white rounded-lg transition-colors"
              >
                <XCircleIcon className="w-5 h-5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>
          </div>
        ) : (
          <div
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, fileType)}
            onClick={() => inputRef.current?.click()}
            className={`
              ${bgColor} rounded-xl p-8 border-2 border-dashed ${borderColor}
              flex flex-col items-center justify-center cursor-pointer
              hover:border-opacity-100 transition-all min-h-[160px]
              ${uploading === fileType ? "opacity-50 pointer-events-none" : ""}
            `}
          >
            {uploading === fileType ? (
              <ArrowPathIcon className={`w-10 h-10 ${iconColor} animate-spin`} />
            ) : (
              <>
                <CloudArrowUpIcon className={`w-10 h-10 ${iconColor} mb-2`} />
                <p className="text-sm text-gray-600 text-center">
                  <span className="font-medium">Click to upload</span> or drag & drop
                </p>
                <p className="text-xs text-gray-400 mt-1">MP4, MOV, AVI, MKV</p>
              </>
            )}
          </div>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => handleFileSelect(e, fileType)}
        />
      </div>
    );
  };

  return (
    <>
      {/* Upload Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center px-4 py-2.5 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium rounded-xl hover:from-blue-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 shadow-lg shadow-blue-500/25 transition-all"
      >
        <PlusIcon className="w-5 h-5 mr-2" />
        New Comparison
      </button>

      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center">
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity"
              onClick={() => setIsOpen(false)}
            />

            {/* Modal Panel */}
            <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 text-left transform transition-all">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-blue-100 rounded-xl">
                    <FilmIcon className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-gray-900">
                      New Video Comparison
                    </h3>
                    <p className="text-sm text-gray-500">
                      Upload acceptance and emission videos to compare
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <XCircleIcon className="w-6 h-6 text-gray-400" />
                </button>
              </div>

              {/* Job Name */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Job Name (optional)
                </label>
                <input
                  type="text"
                  value={jobName}
                  onChange={(e) => setJobName(e.target.value)}
                  placeholder="e.g., Client XYZ - TV Spot"
                  className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              {/* Sensitivity Level */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Sensitivity Level
                </label>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setSensitivityLevel("low")}
                    className={`p-3 rounded-lg border-2 text-left transition-all ${
                      sensitivityLevel === "low"
                        ? "border-green-500 bg-green-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                      <span className="font-medium text-gray-900">Low</span>
                    </div>
                    <p className="text-xs text-gray-500">Quick check</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSensitivityLevel("medium")}
                    className={`p-3 rounded-lg border-2 text-left transition-all ${
                      sensitivityLevel === "medium"
                        ? "border-yellow-500 bg-yellow-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <span className="w-2 h-2 rounded-full bg-yellow-500 mr-2"></span>
                      <span className="font-medium text-gray-900">Medium</span>
                    </div>
                    <p className="text-xs text-gray-500">Recommended + OCR</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSensitivityLevel("high")}
                    className={`p-3 rounded-lg border-2 text-left transition-all ${
                      sensitivityLevel === "high"
                        ? "border-red-500 bg-red-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <span className="w-2 h-2 rounded-full bg-red-500 mr-2"></span>
                      <span className="font-medium text-gray-900">High</span>
                    </div>
                    <p className="text-xs text-gray-500">Critical QA</p>
                  </button>
                </div>
              </div>

              {/* Upload Areas */}
              <div className="flex space-x-4 mb-6">
                <DropZone
                  fileType="acceptance"
                  file={acceptanceFile}
                  inputRef={acceptanceInputRef}
                />
                <DropZone
                  fileType="emission"
                  file={emissionFile}
                  inputRef={emissionInputRef}
                />
              </div>

              {/* Error Message */}
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                  {error}
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-between">
                <button
                  onClick={resetForm}
                  className="px-4 py-2.5 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-colors"
                >
                  Reset
                </button>
                <div className="flex space-x-3">
                  <button
                    onClick={() => setIsOpen(false)}
                    className="px-4 py-2.5 border border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={createJob}
                    disabled={!acceptanceFile || !emissionFile || creatingJob}
                    className={`
                      px-6 py-2.5 rounded-xl font-medium transition-all
                      ${
                        acceptanceFile && emissionFile && !creatingJob
                          ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:from-blue-600 hover:to-blue-700 shadow-lg shadow-blue-500/25"
                          : "bg-gray-200 text-gray-400 cursor-not-allowed"
                      }
                    `}
                  >
                    {creatingJob ? (
                      <span className="flex items-center">
                        <ArrowPathIcon className="w-4 h-4 mr-2 animate-spin" />
                        Creating...
                      </span>
                    ) : (
                      "Start Comparison"
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default FileUpload;
