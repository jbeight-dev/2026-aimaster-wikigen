export interface User {
  user_id: string;
  name: string;
}

export interface Space {
  space_id: string;
  name: string;
  description: string | null;
  owner_id: string;
  file_count: number;
  document_count: number;
  approved_count: number;
  created_at: string;
}

export type FileStatus = 'uploaded' | 'analyzing' | 'done' | 'analysis_failed' | 'upload_failed';

export interface UploadedFile {
  file_id: string;
  space_id: string;
  name: string;
  size_bytes: number;
  status: FileStatus;
  step_index: number;
  step_message: string | null;
  created_at: string;
}

export type DocumentStatus = 'pending' | 'approved' | 'rejected';

export interface DocumentTextSection {
  type: 'text';
  heading: string;
  paragraphs: string[];
}

export interface DocumentTagsSection {
  type: 'tags';
  heading: string;
  tags: string[];
}

export interface DocumentTableSection {
  type: 'table';
  heading: string;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface DocumentMarkdownSection {
  type: 'markdown';
  heading: string;
  content: string;
}

export type DocumentSection =
  | DocumentTextSection
  | DocumentTagsSection
  | DocumentTableSection
  | DocumentMarkdownSection;

export interface DocumentHistoryEntry {
  label: string;
  time: string;
}

export interface WikiDocument {
  document_id: string;
  file_id: string;
  space_id: string;
  title: string;
  status: DocumentStatus;
  version: number;
  reject_reason: string | null;
  flags: string[];
  sections: DocumentSection[];
  related_document_ids: string[];
  history: DocumentHistoryEntry[];
}

export interface VerifyFinding {
  claim: string;
  grounded: boolean;
  evidence: string | null;
  severity: 'low' | 'med' | 'high';
}

export interface VerifyValueChange {
  kind: 'number' | 'sql' | 'command' | 'config';
  original_value: string;
  changed_value: string;
  evidence: string | null;
}

export interface VerifyRelationSuggestion {
  action: 'keep' | 'prune' | 'add';
  type: string;
  target: string;
  confidence: number;
  rationale: string;
  status: string;
}

export interface VerificationReport {
  doc_id: string;
  verdict?: 'pass' | 'regenerate' | 'review';
  score?: number;
  attempt?: number;
  recommendation?: string;
  review_comment?: string;
  faithfulness: VerifyFinding[];
  completeness: string[];
  value_changes: VerifyValueChange[];
  schema_issues: string[];
  relations: VerifyRelationSuggestion[];
}

export interface ChatMessage {
  message_id: string;
  space_id: string;
  role: 'user' | 'assistant';
  text: string;
  source_document_ids: string[];
  created_at: string;
}

export interface ApiErrorBody {
  code: string;
  message: string;
}
