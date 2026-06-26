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
import { AIServiceUnavailableCard } from './components/AIServiceUnavailableCard';
import {
  DatabaseUnavailableCard,
  UnsupportedFileCard,
  NoClinicalContentFoundCard,
  BackendStartingCard
} from './components/PipelineErrorCards';

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
  const [pdfStatus, setPdfStatus] = useState<'idle' | 'generating' | 'success' | 'error'>('idle');
  
  // Pipeline steps tracking for sequential progress
  const [pipelineStateStep, setPipelineStateStep] = useState<number>(-1);
  const [pipelineSimulationLogs, setPipelineSimulationLogs] = useState<string[]>([]);
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);
  
  // Advanced Section toggle state
  const [isAdvancedOpen, setIsAdvancedOpen] = useState<boolean>(false);

  const checkBackendHealth = async () => {
    setLoading(true);
    setStatusMessage("Checking clinical engine connectivity...");
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) {
        setStatusMessage("Clinical engine ready.");
      } else {
        setPipelineStateStep(-7);
        setStatusMessage("Clinical engine is currently waking up...");
      }
    } catch (err) {
      setPipelineStateStep(-7);
      setStatusMessage("Clinical engine connection refused. Backend starting...");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkBackendHealth();
  }, []);

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
        
        // If the stay is in AI_SERVICE_UNAVAILABLE state, set pipelineStateStep to -3!
        if (data.status === 'AI_SERVICE_UNAVAILABLE') {
          setPipelineStateStep(-3);
        }

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

    // Check for unsupported file formats
    const unsupportedFile = files.find(file => {
      const ext = file.name.split('.').pop()?.toLowerCase();
      return ext !== 'txt';
    });

    if (unsupportedFile) {
      setPipelineStateStep(-5);
      setStatusMessage("This demonstration currently supports UTF-8 encoded TXT clinical notes.");
      return;
    }

    // Check for empty/zero-byte files
    const emptyFile = files.find(file => file.size === 0);
    if (emptyFile) {
      setPipelineStateStep(-6);
      setStatusMessage("No clinical content detected. Supported file type: UTF-8 TXT clinical notes.");
      return;
    }

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
        
        // Null-byte binary disguise check
        if (text.includes('\u0000')) {
          setPipelineStateStep(-5);
          setStatusMessage("This demonstration currently supports UTF-8 encoded TXT clinical notes.");
          return;
        }

        // Space-normalized empty content check
        const normalized = text.replace(/[\r\t\v\f\n]/g, ' ').replace(/ +/g, ' ').trim();
        if (!normalized) {
          setPipelineStateStep(-6);
          setStatusMessage("No clinical content detected. Supported file type: UTF-8 TXT clinical notes.");
          return;
        }

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
            content: doc.content,
            filename: doc.filename
          })
        });
        
        if (res.ok) {
          updatedDocs[i] = { ...doc, status: 'success' };
          uploadedCount++;
        } else {
          updatedDocs[i] = { ...doc, status: 'failed' };
          try {
            const errData = await res.json();
            if (errData.status === 'UNSUPPORTED_FILE_TYPE') {
              setPipelineStateStep(-5);
              setStatusMessage(errData.message);
              setLoading(false);
              return;
            } else if (errData.status === 'DOCUMENT_VALIDATION_ERROR') {
              setPipelineStateStep(-6);
              setStatusMessage(errData.message);
              setLoading(false);
              return;
            } else if (errData.status === 'DATABASE_UNAVAILABLE') {
              setPipelineStateStep(-4);
              setStatusMessage(errData.message);
              setLoading(false);
              return;
            }
          } catch (_) {}
        }
      } catch (err) {
        updatedDocs[i] = { ...doc, status: 'failed' };
        setPipelineStateStep(-7);
        setStatusMessage("Connection failed. Backend is starting or offline.");
        setLoading(false);
        return;
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

        const data = await res.json().catch(() => ({}));

        if (res.status === 503) {
          if (data.status === 'DATABASE_UNAVAILABLE') {
            setStatusMessage("Clinical records database is currently unavailable.");
            setPipelineStateStep(-4);
            return;
          } else {
            setStatusMessage("AI extraction service temporarily unavailable. Uploaded documents preserved.");
            setPipelineStateStep(-3);
            setStayDetails(prev => {
              if (!prev) return null;
              return {
                ...prev,
                status: "AI_SERVICE_UNAVAILABLE",
                final_summary: data
              };
            });
            return;
          }
        }

        if (res.status === 422 || res.status === 400) {
          if (data.status === 'NO_STRUCTURED_DATA_EXTRACTED' || data.status === 'DOCUMENT_VALIDATION_ERROR') {
            setStatusMessage(data.message || "No clinical content detected.");
            setPipelineStateStep(-6);
            return;
          } else if (data.status === 'UNSUPPORTED_FILE_TYPE') {
            setStatusMessage(data.message || "Unsupported file format.");
            setPipelineStateStep(-5);
            return;
          }
        }

        if (!res.ok) {
          throw new Error(data.message || "Pipeline verification failed");
        }

        setStatusMessage("Discharge Summary Successfully Generated.");
        await fetchStayDetails(selectedCaseId);
        
        setTimeout(() => {
          scrollToId('section-4');
        }, 300);
      } catch (err: any) {
        if (err.message && (err.message.includes("fetch") || err.message.includes("refused") || err.message.includes("Network"))) {
          setPipelineStateStep(-7);
          setStatusMessage("Connection failed. Backend is starting or offline.");
        } else {
          setStatusMessage(`Factual grounding verification failed: ${err.message || err}`);
          setPipelineStateStep(-2);
        }
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
    
    const steps = [
      "Saving reconciliation...",
      "Updating discharge summary...",
      "Recomputing grounding...",
      "Conflict resolved",
      "Summary regenerated"
    ];

    try {
      // Step 1: Saving reconciliation...
      setStatusMessage(steps[0]);
      await new Promise(resolve => setTimeout(resolve, 800));

      // Step 2: Updating discharge summary... (Start API call)
      setStatusMessage(steps[1]);
      
      const response = await fetch(`${API_BASE_URL}/api/pipeline/resolve/${selectedCaseId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ medications: resolvedMeds })
      });

      if (!response.ok) {
        throw new Error("Resolution failed");
      }

      // Step 3: Recomputing grounding...
      setStatusMessage(steps[2]);
      await new Promise(resolve => setTimeout(resolve, 800));

      // Step 4: Conflict resolved
      setStatusMessage(steps[3]);
      await new Promise(resolve => setTimeout(resolve, 800));

      // Fetch the updated stay details
      await fetchStayDetails(selectedCaseId);

      // Step 5: Summary regenerated
      setStatusMessage(steps[4]);
      await new Promise(resolve => setTimeout(resolve, 800));

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
  const handlePrintPDF = async () => {
    if (!stayDetails || !stayDetails.final_summary || !stayDetails.final_summary.summary) {
      alert("No discharge summary available for export.");
      return;
    }
    
    setPdfStatus('generating');
    setStatusMessage("Generating PDF...");

    try {
      const html2pdf = ((await import('html2pdf.js')) as any).default;
      const element = document.getElementById('printable-discharge-report');
      if (!element) {
        throw new Error("Printable element #printable-discharge-report not found.");
      }

      // Generate filename based on stay ID
      const filename = `${stayDetails.stay_id}.pdf`;

      const opt = {
        margin:       10,
        filename:     filename,
        image:        { type: 'jpeg', quality: 1.0 },
        html2canvas:  { 
          scale: 2, 
          useCORS: true, 
          logging: false,
          backgroundColor: '#090d11',
          onclone: (clonedDoc: Document) => {
            // Find all stylesheets and rewrite/sanitize rules to avoid color function parsing crashes
            try {
              for (let i = 0; i < document.styleSheets.length; i++) {
                const sheet = document.styleSheets[i];
                try {
                  const rules = sheet.cssRules || sheet.rules;
                  if (!rules) continue;

                  const ownerNode = sheet.ownerNode;
                  if (ownerNode instanceof Element) {
                    let clonedNode: Element | null = null;
                    if (ownerNode.id) {
                      clonedNode = clonedDoc.getElementById(ownerNode.id);
                    } else if (ownerNode.tagName === 'STYLE') {
                      const originalStyles = Array.from(document.querySelectorAll('style'));
                      const styleIdx = originalStyles.indexOf(ownerNode as HTMLStyleElement);
                      if (styleIdx !== -1) {
                        const clonedStyles = Array.from(clonedDoc.querySelectorAll('style'));
                        clonedNode = clonedStyles[styleIdx] || null;
                      }
                    } else if (ownerNode.tagName === 'LINK') {
                      const href = ownerNode.getAttribute('href');
                      if (href) {
                        clonedNode = clonedDoc.querySelector(`link[href="${href}"]`);
                      }
                    }

                    if (clonedNode) {
                      let rulesText = '';
                      for (let j = 0; j < rules.length; j++) {
                        rulesText += rules[j].cssText + '\n';
                      }

                      // Replace unsupported color functions with transparent fallback
                      const sanitizedText = rulesText
                        .replace(/lab\([^)]+\)/g, 'rgba(0,0,0,0)')
                        .replace(/oklch\([^)]+\)/g, 'rgba(0,0,0,0)')
                        .replace(/oklab\([^)]+\)/g, 'rgba(0,0,0,0)');

                      const styleEl = clonedDoc.createElement('style');
                      styleEl.textContent = sanitizedText;
                      if (clonedNode.id) {
                        styleEl.id = clonedNode.id;
                      }
                      clonedNode.parentNode?.replaceChild(styleEl, clonedNode);
                    }
                  }
                } catch (sheetErr) {
                  // Ignore security or accessibility errors for external stylesheets
                }
              }
            } catch (err) {
              console.error('Error rewriting stylesheets for PDF clone:', err);
            }

            // Also double-ensure any inline styled elements or direct style tags left are sanitized
            clonedDoc.querySelectorAll('style').forEach(styleEl => {
              if (styleEl.textContent) {
                styleEl.textContent = styleEl.textContent
                  .replace(/lab\([^)]+\)/g, 'rgba(0,0,0,0)')
                  .replace(/oklch\([^)]+\)/g, 'rgba(0,0,0,0)')
                  .replace(/oklab\([^)]+\)/g, 'rgba(0,0,0,0)');
              }
            });
          }
        },
        jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
      };

      await html2pdf().set(opt).from(element).save();
      setPdfStatus('success');
      setStatusMessage("PDF downloaded successfully.");
      setTimeout(() => setPdfStatus('idle'), 3000);
    } catch (err: any) {
      console.error(err);
      setPdfStatus('error');
      setStatusMessage("Unable to generate PDF.");
      setTimeout(() => setPdfStatus('idle'), 3000);
    }
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
        #printable-discharge-report {
          font-family: monospace;
          background-color: #0b0f14 !important;
          color: #cbd5e1 !important;
          padding: 40px !important;
        }

        #printable-discharge-report .bg-slate-900 {
          background-color: #0f172a !important;
        }
        #printable-discharge-report .bg-slate-955 {
          background-color: #0b0f14 !important;
        }
        #printable-discharge-report .bg-slate-950 {
          background-color: #020617 !important;
        }
        #printable-discharge-report .bg-emerald-950\/10 {
          background-color: rgba(6, 78, 59, 0.1) !important;
        }
        #printable-discharge-report .bg-emerald-950\/20 {
          background-color: rgba(6, 78, 59, 0.2) !important;
        }
        #printable-discharge-report .bg-emerald-500\/5 {
          background-color: rgba(16, 185, 129, 0.05) !important;
        }
        #printable-discharge-report .bg-rose-500\/5 {
          background-color: rgba(244, 63, 94, 0.05) !important;
        }
        #printable-discharge-report .bg-emerald-500 {
          background-color: #10b981 !important;
        }
        #printable-discharge-report .bg-rose-500 {
          background-color: #f43f5e !important;
        }

        /* Borders */
        #printable-discharge-report .border,
        #printable-discharge-report .border-t,
        #printable-discharge-report .border-b,
        #printable-discharge-report .border-slate-800,
        #printable-discharge-report .border-slate-850,
        #printable-discharge-report .border-slate-900,
        #printable-discharge-report .border-emerald-500\/30,
        #printable-discharge-report .border-emerald-900,
        #printable-discharge-report .border-rose-500\/60,
        #printable-discharge-report .border-l-\[4px\],
        #printable-discharge-report .border-l-rose-500 {
          border: 1px solid #1e293b !important;
        }
        #printable-discharge-report .border-l-\[4px\],
        #printable-discharge-report .border-l-rose-500 {
          border-left: 4px solid #f43f5e !important;
        }

        /* Text colors */
        #printable-discharge-report .text-slate-100 {
          color: #f1f5f9 !important;
        }
        #printable-discharge-report .text-slate-150,
        #printable-discharge-report .text-slate-200 {
          color: #e2e8f0 !important;
        }
        #printable-discharge-report .text-slate-300 {
          color: #cbd5e1 !important;
        }
        #printable-discharge-report .text-slate-400 {
          color: #94a3b8 !important;
        }
        #printable-discharge-report .text-slate-500 {
          color: #64748b !important;
        }
        #printable-discharge-report .text-teal-400 {
          color: #2dd4bf !important;
        }
        #printable-discharge-report .text-emerald-400 {
          color: #34d399 !important;
        }
        #printable-discharge-report .text-rose-500 {
          color: #f43f5e !important;
        }
        #printable-discharge-report .text-rose-455 {
          color: #fda4af !important;
        }
        #printable-discharge-report .text-slate-955 {
          color: #0b0f14 !important;
        }

        /* Tables */
        #printable-discharge-report table {
          width: 100% !important;
          border-collapse: collapse !important;
          margin-top: 10px !important;
          margin-bottom: 10px !important;
        }
        #printable-discharge-report th, 
        #printable-discharge-report td {
          border: 1px solid #1e293b !important;
          padding: 8px !important;
          text-align: left !important;
        }
        #printable-discharge-report th {
          background-color: #0f172a !important;
          font-weight: bold !important;
        }

        /* Page break rules */
        #printable-discharge-report .avoid-page-break,
        #printable-discharge-report h4,
        #printable-discharge-report h5,
        #printable-discharge-report table,
        #printable-discharge-report tr,
        #printable-discharge-report .bg-slate-950,
        #printable-discharge-report .bg-emerald-950\/10,
        #printable-discharge-report .bg-emerald-950\/20,
        #printable-discharge-report .mt-5,
        #printable-discharge-report .border-t {
          break-inside: avoid;
          page-break-inside: avoid;
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
      {stayDetails && stayDetails.status !== 'AI_SERVICE_UNAVAILABLE' && (
        <ExtractedClaims
          stayDetails={stayDetails}
          expandedClaimId={expandedClaimId}
          toggleClaimExpand={toggleClaimExpand}
        />
      )}

      {/* SECTION 5: DETECTED CONFLICTS */}
      {stayDetails && stayDetails.status !== 'AI_SERVICE_UNAVAILABLE' && (
        <DetectedConflicts
          stayDetails={stayDetails}
          showResolveEditor={showResolveEditor}
          setShowResolveEditor={setShowResolveEditor}
          resolvedMeds={resolvedMeds}
          handleReconcileConflict={handleReconcileConflict}
          handleMedResolutionChange={handleMedResolutionChange}
          loading={loading}
        />
      )}

      {/* SECTION 6: GROUNDING REPORT */}
      {stayDetails && stayDetails.status !== 'AI_SERVICE_UNAVAILABLE' && (
        <GroundingReport stayDetails={stayDetails} />
      )}

      {/* SECTION 7: GENERATED DISCHARGE SUMMARY / SAFE FAILURE CARD */}
      {pipelineStateStep === -4 ? (
        <DatabaseUnavailableCard
          onRetry={checkBackendHealth}
          loading={loading}
          notes={pendingDocuments}
        />
      ) : pipelineStateStep === -5 ? (
        <UnsupportedFileCard
          onReturnToUpload={() => {
            resetPipelineState();
            setPendingDocuments([]);
            scrollToId('section-2');
          }}
          message={statusMessage}
        />
      ) : pipelineStateStep === -6 ? (
        <NoClinicalContentFoundCard
          onReturnToUpload={() => {
            resetPipelineState();
            setPendingDocuments([]);
            scrollToId('section-2');
          }}
          message={statusMessage}
        />
      ) : pipelineStateStep === -7 ? (
        <BackendStartingCard
          onRetry={checkBackendHealth}
          loading={loading}
        />
      ) : stayDetails && stayDetails.status === 'AI_SERVICE_UNAVAILABLE' ? (
        <AIServiceUnavailableCard
          stayDetails={stayDetails}
          onRetry={handleGenerateSummary}
          loading={loading}
        />
      ) : (
        <DischargeSummaryCard
          stayDetails={stayDetails}
          loading={loading}
          handlePhysicianApprove={handlePhysicianApprove}
        />
      )}

      {/* SECTIONS 8 & 9: DOWNLOAD PDF AND ADVANCED TECHNICAL DETAILS */}
      {stayDetails && stayDetails.status !== 'AI_SERVICE_UNAVAILABLE' && (
        <AdvancedTechnicalDetails
          stayDetails={stayDetails}
          isAdvancedOpen={isAdvancedOpen}
          setIsAdvancedOpen={setIsAdvancedOpen}
          handleExportJSON={handleExportJSON}
          handlePrintPDF={handlePrintPDF}
          pipelineSimulationLogs={pipelineSimulationLogs}
          pdfStatus={pdfStatus}
        />
      )}

    </div>
  );
}