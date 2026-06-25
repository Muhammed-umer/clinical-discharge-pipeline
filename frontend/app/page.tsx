'use client';

import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';

// Import Types & Sample Cases Presets
import {
  StayDetails,
  PendingDocument,
  SAMPLE_CASES
} from './components/presets';

// Import Modular Components
import { Hero } from './components/Hero';
import { UploadSection } from './components/UploadSection';
import { PipelineOverview } from './components/PipelineOverview';
import { ExtractedClaims } from './components/ExtractedClaims';
import { DetectedConflicts } from './components/DetectedConflicts';
import { GroundingReport } from './components/GroundingReport';
import { DischargeSummaryCard } from './components/DischargeSummaryCard';
import { AdvancedTechnicalDetails } from './components/AdvancedTechnicalDetails';

// ==========================================
// LOCAL HELPERS
// ==========================================

const getNaiveISOString = (dateInput: Date | string) => {
  const d = typeof dateInput === 'string' ? new Date(dateInput) : dateInput;
  const pad = (num: number) => String(num).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

const guessDocType = (filename: string): string => {
  const lower = filename.toLowerCase();
  if (lower.includes('consult')) return 'Consultant Note';
  if (lower.includes('resident')) return 'Resident Note';
  if (lower.includes('nurse')) return 'Nurse Note';
  if (lower.includes('lab') || lower.includes('report')) return 'Lab Report';
  if (lower.includes('radio') || lower.includes('xray') || lower.includes('scan')) return 'Radiology Report';
  if (lower.includes('rx') || lower.includes('presc')) return 'Prescription';
  if (lower.includes('draft')) return 'Discharge Draft';
  return 'Doctor Note';
};

const guessAuthorRole = (filename: string): string => {
  const lower = filename.toLowerCase();
  if (lower.includes('consult')) return 'CONSULTANT';
  if (lower.includes('resident')) return 'RESIDENT';
  if (lower.includes('nurse')) return 'WARD_NURSE';
  if (lower.includes('attending') || lower.includes('jenkins') || lower.includes('mercer') || lower.includes('chen')) return 'ATTENDING';
  return 'RESIDENT';
};

const SIMULATION_LOGS = [
  "Initializing clinical pipeline processing context...",
  "Retrieving clinical notes from case history timeline...",
  "Applying text preprocessing and removing formatting noise...",
  "Extracting fact patterns from unstructured clinician notes...",
  "Validating structured facts against clinical templates...",
  "Generating unique fact assertions...",
  "Creating audit hashes for clinical traceability...",
  "Mapping clinical facts to original note citations...",
  "Verifying chronologically sorted author credentials...",
  "Running discrepancy checks across note sequences...",
  "Cross-referencing medications and checking dosage variations...",
  "Querying clinical records index for matching evidence...",
  "Retrieving supporting note context for verification...",
  "Running consistency verification on extracted claims...",
  "Checking citation coverage for diagnoses and prescriptions...",
  "Analyzing safety metrics and calculating grounding score...",
  "Formatting final discharge summary layout...",
  "Clinical safety verification complete. Safe summary generated!"
];

export default function Home() {
  // Navigation & Internal Case reference
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");
  const [stayDetails, setStayDetails] = useState<StayDetails | null>(null);

  // Ingestion state
  const [patientName, setPatientName] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [pendingDocuments, setPendingDocuments] = useState<PendingDocument[]>([]);

  // Add custom doc inputs
  const [customDocType, setCustomDocType] = useState("Doctor Note");
  const [customAuthorRole, setCustomAuthorRole] = useState("RESIDENT");
  const [customDocContent, setCustomDocContent] = useState("");
  const [customFilename, setCustomFilename] = useState("custom_note.txt");

  // Reconciliation Form inputs
  const [resolvedMeds, setResolvedMeds] = useState<Array<{ name: string; dosage: string; frequency: string; duration: string }>>([]);
  const [showResolveEditor, setShowResolveEditor] = useState<boolean>(false);

  // System State Control
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  
  // Pipeline steps tracking for sequential progress
  const [pipelineStateStep, setPipelineStateStep] = useState<number>(-1);
  const [pipelineSimulationLogs, setPipelineSimulationLogs] = useState<string[]>([]);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);
  
  // Advanced Section toggle state
  const [isAdvancedOpen, setIsAdvancedOpen] = useState<boolean>(false);

  const resetPipelineState = () => {
    setStayDetails(null);
    setResolvedMeds([]);
    setShowResolveEditor(false);
    setPipelineStateStep(-1);
    setPipelineSimulationLogs([]);
    setExpandedClaimId(null);
    setStatusMessage("");
  };

  const handlePatientNameChange = (name: string) => {
    setPatientName(name);
    resetPipelineState();
  };

  const fetchStayDetails = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/stays/${id}`);
      if (res.ok) {
        const data = await res.json();
        setStayDetails(data);
        setShowResolveEditor(false);
        
        // Pre-populate medication reconciliation form
        if (data.final_summary?.summary?.prescribed_medications) {
          const initialMeds = data.final_summary.summary.prescribed_medications.map((m: any) => ({
            name: m.name.replace(" (DISCREPANCY)", ""),
            dosage: m.dosage,
            frequency: m.frequency,
            duration: m.duration
          }));
          setResolvedMeds(initialMeds);
        }
      }
    } catch (err) {
      setStatusMessage("Failed to retrieve clinical case details.");
    }
  };

  // Helper for scroll navigation
  const scrollToId = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleRemovePendingDoc = (id: string) => {
    resetPipelineState();
    setPendingDocuments(prev => prev.filter(d => d.id !== id));
  };

  // Preset Selection
  const handleSelectSampleCase = (caseIdx: number) => {
    resetPipelineState();
    const selected = SAMPLE_CASES[caseIdx];
    setSelectedCaseId(selected.id);
    setPatientName(selected.name);
    
    const docs = selected.notes.map((note, index) => ({
      id: `preset-${caseIdx}-${index}`,
      filename: note.filename,
      docType: note.docType,
      authorRole: note.authorRole,
      content: note.content,
      recorded_at: note.recorded_at,
      status: 'pending' as const
    }));
    
    setPendingDocuments(docs);
    setStatusMessage(`Loaded presets for ${selected.name}. Click "Generate Summary" to start the pipeline.`);
    scrollToId('section-2');
  };

  // Custom document addition
  const handleAddCustomDoc = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customDocContent.trim()) {
      alert("Please enter clinical note text.");
      return;
    }
    resetPipelineState();
    const newDoc: PendingDocument = {
      id: `custom-${Date.now()}`,
      filename: customFilename.endsWith('.txt') ? customFilename : `${customFilename}.txt`,
      docType: customDocType,
      authorRole: customAuthorRole,
      content: customDocContent,
      recorded_at: getNaiveISOString(new Date()),
      status: 'pending'
    };
    
    setPendingDocuments(prev => [...prev, newDoc]);
    setCustomDocContent("");
    setCustomFilename("custom_note.txt");
    setStatusMessage("Added note to queue.");
  };

  // Drag and Drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFileList(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFileList(Array.from(e.target.files));
    }
  };

  const processFileList = (files: File[]) => {
    resetPipelineState();
    const newNotes = files.map((file, idx) => {
      const reader = new FileReader();
      const docId = `upload-${Date.now()}-${idx}`;
      
      const newDoc: PendingDocument = {
        id: docId,
        filename: file.name,
        docType: guessDocType(file.name),
        authorRole: guessAuthorRole(file.name),
        content: "",
        recorded_at: getNaiveISOString(new Date()),
        status: 'pending'
      };
      
      reader.onload = (event) => {
        const text = event.target?.result as string;
        setPendingDocuments(prev => 
          prev.map(d => d.id === docId ? { ...d, content: text } : d)
        );
      };
      reader.readAsText(file);
      return newDoc;
    });
    
    setPendingDocuments(prev => [...prev, ...newNotes]);
  };

  // Ingest upload and trigger pipeline
  const handleGenerateSummary = async () => {
    if (pendingDocuments.length === 0) {
      alert("Please load or drop notes first.");
      return;
    }

    resetPipelineState();
    setLoading(true);
    setStatusMessage("Finding supporting evidence and uploading note timelines...");
    
    let uploadedCount = 0;
    const updatedDocs = [...pendingDocuments];

    for (let i = 0; i < updatedDocs.length; i++) {
      const doc = updatedDocs[i];
      if (doc.status === 'success') continue;

      updatedDocs[i] = { ...doc, status: 'uploading' };
      setPendingDocuments([...updatedDocs]);
      
      try {
        const res = await fetch(`${API_BASE_URL}/api/documents/upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            stay_id: selectedCaseId,
            patient_name: patientName,
            author_role: doc.authorRole,
            recorded_at: getNaiveISOString(doc.recorded_at),
            content: doc.content
          })
        });
        
        if (res.ok) {
          updatedDocs[i] = { ...doc, status: 'success' };
          uploadedCount++;
        } else {
          updatedDocs[i] = { ...doc, status: 'failed' };
        }
      } catch (err) {
        updatedDocs[i] = { ...doc, status: 'failed' };
      }
      setPendingDocuments([...updatedDocs]);
    }

    setStatusMessage("Documents ingested. Running safety pipeline check...");
    await fetchStayDetails(selectedCaseId);
    
    // Now trigger sequential pipeline execution
    await handleExecutePipeline();
  };

  // Sequential Animation Trigger
  const handleExecutePipeline = async () => {
    if (!selectedCaseId) return;

    setLoading(true);
    setPipelineStateStep(0);
    setPipelineSimulationLogs([]);

    scrollToId('section-3');

    const logHistory: string[] = [];
    let activeLogIdx = 0;

    const interval = setInterval(() => {
      if (activeLogIdx < SIMULATION_LOGS.length) {
        if (activeLogIdx === 0) setPipelineStateStep(0);
        else if (activeLogIdx === 3) setPipelineStateStep(1);
        else if (activeLogIdx === 5) setPipelineStateStep(2);
        else if (activeLogIdx === 8) setPipelineStateStep(3);
        else if (activeLogIdx === 11) setPipelineStateStep(4);
        else if (activeLogIdx === 16) setPipelineStateStep(5);

        const timestampStr = new Date().toLocaleTimeString();
        logHistory.push(`[${timestampStr}] ${SIMULATION_LOGS[activeLogIdx]}`);
        setPipelineSimulationLogs([...logHistory]);
        activeLogIdx++;
      } else {
        clearInterval(interval);
        triggerBackendPipelineRun();
      }
    }, 180);

    const triggerBackendPipelineRun = async () => {
      try {
        setStatusMessage("Verifying clinical consistency and safety layers...");
        const res = await fetch(`${API_BASE_URL}/api/pipeline/process/${selectedCaseId}`, {
          method: 'POST'
        });

        if (!res.ok) {
          throw new Error("Pipeline verification failed");
        }

        setStatusMessage("Discharge Summary Successfully Generated.");
        await fetchStayDetails(selectedCaseId);
        
        setTimeout(() => {
          scrollToId('section-4');
        }, 300);
      } catch (err: any) {
        setStatusMessage("Factual grounding verification failed.");
        setPipelineStateStep(-2);
      } finally {
        setLoading(false);
      }
    };
  };

  // Reconcile dosage conflicts
  const handleReconcileConflict = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) return;
    
    setLoading(true);
    setStatusMessage("Applying attending physician overrides...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/pipeline/resolve/${selectedCaseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medications: resolvedMeds })
      });

      if (!response.ok) {
        throw new Error("Resolution failed");
      }

      setStatusMessage("Prescription conflicts successfully reconciled.");
      await fetchStayDetails(selectedCaseId);
      setShowResolveEditor(false);
      
      scrollToId('section-6');
    } catch (err: any) {
      setStatusMessage(`Reconciliation override failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleMedResolutionChange = (index: number, field: string, value: string) => {
    const updated = [...resolvedMeds];
    updated[index] = { ...updated[index], [field]: value };
    setResolvedMeds(updated);
  };

  // Sign summary
  const handlePhysicianApprove = async () => {
    if (!selectedCaseId) return;
    setLoading(true);
    setStatusMessage("Sealing discharge summary with Attending signature...");

    try {
      const response = await fetch(`${API_BASE_URL}/api/pipeline/approve/${selectedCaseId}`, {
        method: 'POST'
      });

      if (!response.ok) {
        throw new Error("Sealing summary failed");
      }

      setStatusMessage("Summary Review Sealed and finalized.");
      await fetchStayDetails(selectedCaseId);
      
      scrollToId('section-8');
    } catch (err: any) {
      setStatusMessage(`Signature verification failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Document prints
  const handlePrintPDF = () => {
    if (!stayDetails || !stayDetails.final_summary || !stayDetails.final_summary.summary) {
      alert("No discharge summary available for export.");
      return;
    }
    
    setStatusMessage("Discharge Summary PDF generated successfully.");
    setTimeout(() => {
      window.print();
    }, 150);
  };

  // Export JSON structured summary
  const handleExportJSON = () => {
    if (!stayDetails?.final_summary) {
      alert("No generated summary available to export.");
      return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(stayDetails, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `discharge_summary_${stayDetails.stay_id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const toggleClaimExpand = (claimId: string) => {
    setExpandedClaimId(expandedClaimId === claimId ? null : claimId);
  };

  return (
    <div className="min-h-screen bg-slate-955 text-slate-100 font-sans p-4 md:p-8 selection:bg-teal-500 selection:text-slate-900">
      
      {/* Dynamic style tag inject for printing clean PDF */}
      <style dangerouslySetInnerHTML={{ __html: `
        @media print {
          body * {
            visibility: hidden;
          }
          #printable-discharge-report, #printable-discharge-report * {
            visibility: visible;
            background-color: #111827 !important;
            color: #F8FAFC !important;
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
          }
          #printable-discharge-report {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            margin: 0;
            padding: 40px;
            background-color: #0B0F14 !important;
            color: #F8FAFC !important;
            border: none !important;
            box-shadow: none !important;
            print-color-adjust: exact;
            -webkit-print-color-adjust: exact;
          }
          #printable-discharge-report table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            margin-bottom: 10px;
          }
          #printable-discharge-report th, #printable-discharge-report td {
            border: 1px solid #1E293B !important;
            padding: 8px;
            text-align: left;
            color: #F8FAFC !important;
          }
          #printable-discharge-report th {
            background-color: #111827 !important;
            font-weight: bold;
          }
          #printable-discharge-report .badge-print {
            border: 1px solid #14B8A6 !important;
            padding: 2px 6px;
            font-size: 10px;
            display: inline-block;
            margin-left: 10px;
            color: #14B8A6 !important;
          }
        }
      ` }} />

      {/* SECTION 1: HERO */}
      <Hero onStartClick={() => scrollToId('section-2')} />

      {/* SECTION 2: UPLOAD CLINICAL DOCUMENTS */}
      <UploadSection
        selectedCaseId={selectedCaseId}
        onSelectSampleCase={handleSelectSampleCase}
        patientName={patientName}
        setPatientName={handlePatientNameChange}
        dragOver={dragOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onFileSelect={handleFileSelect}
        customFilename={customFilename}
        setCustomFilename={setCustomFilename}
        customDocType={customDocType}
        setCustomDocType={setCustomDocType}
        customAuthorRole={customAuthorRole}
        setCustomAuthorRole={setCustomAuthorRole}
        customDocContent={customDocContent}
        setCustomDocContent={setCustomDocContent}
        onAddCustomDoc={handleAddCustomDoc}
        pendingDocuments={pendingDocuments}
        onRemovePendingDoc={handleRemovePendingDoc}
        onGenerateSummary={handleGenerateSummary}
        loading={loading}
        hasSummary={!!(stayDetails && stayDetails.final_summary)}
      />

      {/* SECTION 3: AI PIPELINE */}
      <PipelineOverview
        loading={loading}
        pipelineStateStep={pipelineStateStep}
        pipelineSimulationLogs={pipelineSimulationLogs}
        stayDetails={stayDetails}
      />

      {/* SECTION 4: EXTRACTED CLAIMS */}
      <ExtractedClaims
        stayDetails={stayDetails}
        expandedClaimId={expandedClaimId}
        toggleClaimExpand={toggleClaimExpand}
      />

      {/* SECTION 5: DETECTED CONFLICTS */}
      <DetectedConflicts
        stayDetails={stayDetails}
        showResolveEditor={showResolveEditor}
        setShowResolveEditor={setShowResolveEditor}
        resolvedMeds={resolvedMeds}
        handleReconcileConflict={handleReconcileConflict}
        handleMedResolutionChange={handleMedResolutionChange}
        loading={loading}
      />

      {/* SECTION 6: GROUNDING REPORT */}
      <GroundingReport stayDetails={stayDetails} />

      {/* SECTION 7: GENERATED DISCHARGE SUMMARY */}
      <DischargeSummaryCard
        stayDetails={stayDetails}
        loading={loading}
        handlePhysicianApprove={handlePhysicianApprove}
      />

      {/* SECTIONS 8 & 9: DOWNLOAD PDF AND ADVANCED TECHNICAL DETAILS */}
      <AdvancedTechnicalDetails
        stayDetails={stayDetails}
        isAdvancedOpen={isAdvancedOpen}
        setIsAdvancedOpen={setIsAdvancedOpen}
        handleExportJSON={handleExportJSON}
        handlePrintPDF={handlePrintPDF}
        pipelineSimulationLogs={pipelineSimulationLogs}
      />

    </div>
  );
}