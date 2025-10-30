/**
 * Alert Detail Modal Component
 * Shows comprehensive alert information with timeline, comments, and related alerts
 */
import { Alert } from '../types';
import { apiClient } from '../utils/apiClient';
import { formatTimestamp } from '../utils/formatting';

interface AlertHistory {
  id: number;
  from_status: string;
  to_status: string;
  username: string;
  notes: string;
  created_at: string;
}

interface AlertComment {
  id: number;
  username: string;
  comment: string;
  created_at: string;
}

export function createAlertDetailModal(alert: Alert, onClose: () => void): HTMLElement {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay alert-detail-modal';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-labelledby', 'alert-detail-title');
  modal.setAttribute('aria-modal', 'true');

  // Fetch additional data
  let history: AlertHistory[] = [];
  let comments: AlertComment[] = [];

  const fetchAlertDetails = async () => {
    try {
      // Fetch history
      const historyRes = await apiClient.get(`/alerts/${alert.id}/history`);
      history = historyRes.data.history || [];

      // Fetch comments
      const commentsRes = await apiClient.get(`/alerts/${alert.id}/comments`);
      comments = commentsRes.data.comments || [];

      // Re-render content with data
      renderContent();
    } catch (error) {
      console.error('Failed to fetch alert details:', error);
    }
  };

  const renderContent = () => {
    const content = document.createElement('div');
    content.className = 'modal-content alert-detail-content';

    content.innerHTML = `
      <div class="modal-header">
        <div class="header-title">
          <span class="material-symbols-outlined icon-large">security</span>
          <div>
            <h2 id="alert-detail-title">Alert Details</h2>
            <p class="alert-id-subtitle">ID: ${alert.id}</p>
          </div>
        </div>
        <button class="btn-icon close-modal-btn" aria-label="Close modal">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="modal-body">
        <!-- Alert Overview -->
        <section class="detail-section">
          <h3>
            <span class="material-symbols-outlined">info</span>
            Overview
          </h3>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">Severity</span>
              <span class="severity-badge severity-${alert.severity?.toLowerCase() || 'unknown'}">
                ${alert.severity || 'N/A'}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Priority</span>
              <span class="priority-badge priority-${alert.priority}">
                ${alert.priority.toUpperCase()}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Status</span>
              <span class="status-badge status-${alert.status}">
                ${alert.status.replace('_', ' ').toUpperCase()}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Attack Type</span>
              <span class="class-badge">${alert.className || 'Unknown'}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Confidence</span>
              <div class="confidence-display">
                <span class="confidence-percentage">${(alert.confidence * 100).toFixed(1)}%</span>
                <div class="confidence-bar-large">
                  <div class="confidence-fill" style="width: ${alert.confidence * 100}%"></div>
                </div>
              </div>
            </div>
            <div class="detail-item">
              <span class="detail-label">Timestamp</span>
              <span class="monospace">${formatTimestamp(alert.timestamp)}</span>
            </div>
          </div>
        </section>

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        <!-- Network Context -->
        <section class="detail-section">
          <h3>
            <span class="material-symbols-outlined">lan</span>
            Network Context
          </h3>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">Source IP</span>
              <code class="ip-address">${alert.srcIp || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Source Port</span>
              <code>${alert.srcPort || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Destination IP</span>
              <code class="ip-address">${alert.dstIp || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Destination Port</span>
              <code>${alert.dstPort || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Protocol</span>
              <code>${alert.protocol || 'N/A'}</code>
            </div>
          </div>
        </section>

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        <!-- Timeline -->
        <section class="detail-section">
          <h3>
            <span class="material-symbols-outlined">timeline</span>
            Status Timeline
          </h3>
          <div class="timeline">
            ${history.length > 0 ? history.map(h => `
              <div class="timeline-item">
                <div class="timeline-marker"></div>
                <div class="timeline-content">
                  <div class="timeline-header">
                    <span class="status-change">
                      ${h.from_status || 'NEW'} → <strong>${h.to_status}</strong>
                    </span>
                    <span class="timeline-time">${formatTimestamp(h.created_at)}</span>
                  </div>
                  <div class="timeline-details">
                    <span class="timeline-user">${h.username || 'System'}</span>
                    ${h.notes ? `<p class="timeline-notes">${h.notes}</p>` : ''}
                  </div>
                </div>
              </div>
            `).join('') : '<p class="empty-state-text">No status changes recorded</p>'}
          </div>
        </section>

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        <!-- Comments -->
        <section class="detail-section">
          <h3>
            <span class="material-symbols-outlined">comment</span>
            Comments (${comments.length})
          </h3>
          <div class="comments-list">
            ${comments.length > 0 ? comments.map(c => `
              <div class="comment-item">
                <div class="comment-header">
                  <span class="comment-author">${c.username || 'Unknown'}</span>
                  <span class="comment-time">${formatTimestamp(c.created_at)}</span>
                </div>
                <p class="comment-text">${escapeHtml(c.comment)}</p>
              </div>
            `).join('') : '<p class="empty-state-text">No comments yet</p>'}
          </div>
          
          <!-- Add Comment Form -->
          <div class="add-comment-form">
            <textarea 
              id="new-comment-input" 
              class="comment-input" 
              placeholder="Add a comment..."
              rows="3"
            ></textarea>
            <button class="btn btn-primary add-comment-btn" id="add-comment-btn">
              <span class="material-symbols-outlined">send</span>
              Add Comment
            </button>
          </div>
        </section>

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        <!-- Model Info -->
        <section class="detail-section">
          <h3>
            <span class="material-symbols-outlined">model_training</span>
            Model Information
          </h3>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">Model Version</span>
              <code>${alert.modelVersion || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Feature Version</span>
              <code>${alert.featureVersion || 'N/A'}</code>
            </div>
            <div class="detail-item">
              <span class="detail-label">Flow ID</span>
              <code class="flow-id">${alert.flowId || 'N/A'}</code>
            </div>
          </div>
        </section>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary close-modal-btn">Close</button>
        <button class="btn btn-primary export-alert-btn" id="export-alert-btn">
          <span class="material-symbols-outlined">download</span>
          Export as JSON
        </button>
      </div>
    `;

    // Clear and append
    modal.innerHTML = '';
    modal.appendChild(content);

    // Event listeners
    const closeButtons = modal.querySelectorAll('.close-modal-btn');
    closeButtons.forEach(btn => {
      btn.addEventListener('click', onClose);
    });

    // Add comment handler
    const addCommentBtn = modal.querySelector('#add-comment-btn');
    if (addCommentBtn) {
      addCommentBtn.addEventListener('click', async () => {
        const input = modal.querySelector('#new-comment-input') as HTMLTextAreaElement;
        const commentText = input.value.trim();
        
        if (!commentText) return;

        try {
          await apiClient.post(`/alerts/${alert.id}/comment`, {
            comment: commentText
          });
          
          input.value = '';
          // Refresh comments
          fetchAlertDetails();
        } catch (error) {
          console.error('Failed to add comment:', error);
          alert('Failed to add comment. Please try again.');
        }
      });
    }

    // Export handler
    const exportBtn = modal.querySelector('#export-alert-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        const dataStr = JSON.stringify(alert, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `alert_${alert.id}_${Date.now()}.json`;
        link.click();
        URL.revokeObjectURL(url);
      });
    }

    // Close on overlay click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        onClose();
      }
    });

    // Close on Escape
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        document.removeEventListener('keydown', handleEscape);
      }
    };
    document.addEventListener('keydown', handleEscape);
  };

  // Initial render with basic data
  renderContent();

  // Fetch full details
  fetchAlertDetails();

  return modal;
}

function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatTimestamp(timestamp: string | number): string {
  const date = new Date(typeof timestamp === 'string' ? timestamp : timestamp);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

