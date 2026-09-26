import type { ApiClient } from '../api/client';

export interface PreviewTarget {
  show(blob: Blob): void;
  close(): void;
}

/** Native save dialogs/preview can implement this without changing UI components. */
export interface FilePresenter {
  save(blob: Blob, name: string): void | Promise<void>;
  preparePreview(): PreviewTarget;
}

export interface FileActions {
  save(blob: Blob, name: string): void | Promise<void>;
  downloadReport(reportId: string): Promise<void>;
  previewReport(reportId: string): Promise<void>;
  downloadJobOutput(jobId: string, outputName: string): Promise<void>;
}

export const browserFilePresenter: FilePresenter = {
  save(blob, name) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    try { anchor.click(); }
    finally { window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
  },
  preparePreview() {
    // Reserve the window during the user's click, before the authenticated fetch.
    const target = window.open('about:blank', '_blank');
    if (!target) throw new Error('Allow a popup for Scanner to preview this PDF, or use Download.');
    target.opener = null;
    let url: string | undefined;
    return {
      show(blob) {
        if (target.closed) throw new Error('The preview window was closed.');
        url = URL.createObjectURL(blob);
        target.location.replace(url);
        // The PDF viewer has its own loaded copy; do not retain the blob indefinitely.
        window.setTimeout(() => { if (url) URL.revokeObjectURL(url); }, 60000);
      },
      close() {
        target.close();
        if (url) URL.revokeObjectURL(url);
      }
    };
  }
};

export function createFileActions(api: ApiClient, presenter: FilePresenter): FileActions {
  const reportPath = (id: string, action: string) => `/api/v1/reports/${encodeURIComponent(id)}/${action}`;
  async function download(path: string) {
    const file = await api.requestFile(path);
    await presenter.save(file.blob, file.name);
  }
  return {
    save: (blob, name) => presenter.save(blob, name),
    downloadReport: (id) => download(reportPath(id, 'download')),
    downloadJobOutput: (jobId, outputName) => download(
      `/api/v1/jobs/${encodeURIComponent(jobId)}/outputs/${encodeURIComponent(outputName)}/download`
    ),
    async previewReport(id) {
      const target = presenter.preparePreview();
      try {
        const file = await api.requestFile(reportPath(id, 'view'));
        if (file.mediaType !== 'application/pdf') throw new Error('Only PDF reports can be previewed. Use Download for this file.');
        target.show(file.blob);
      } catch (error) {
        target.close();
        throw error;
      }
    }
  };
}
