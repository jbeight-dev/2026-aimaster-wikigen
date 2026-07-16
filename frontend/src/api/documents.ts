import { apiClient } from './client';
import type { DocumentSection, DocumentStatus, WikiDocument } from './types';

export function getDocument(documentId: string): Promise<{ document: WikiDocument }> {
  return apiClient.get(`/documents/${documentId}`);
}

export function listDocuments(
  spaceId: string,
  status?: DocumentStatus,
): Promise<{ items: WikiDocument[] }> {
  return apiClient.get(`/spaces/${spaceId}/documents`, { status });
}

export function approveDocument(documentId: string): Promise<{ document: WikiDocument }> {
  return apiClient.post(`/documents/${documentId}/approve`);
}

export function rejectDocument(
  documentId: string,
  reason: string,
): Promise<{ document: WikiDocument }> {
  return apiClient.post(`/documents/${documentId}/reject`, { reason: reason || undefined });
}

export function reopenDocument(documentId: string): Promise<{ document: WikiDocument }> {
  return apiClient.post(`/documents/${documentId}/reopen`);
}

export function updateDocument(
  documentId: string,
  sections: DocumentSection[],
): Promise<{ document: WikiDocument }> {
  return apiClient.patch(`/documents/${documentId}`, { sections });
}
